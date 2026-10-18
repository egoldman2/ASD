"""Bounded, read-only runtime validation for the shared Multi-Agent Server."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from urllib.parse import quote, urlsplit

from mcp_validation import (
    ProbeConfigurationError,
    bounded_timeout,
    local_url,
    public_evidence,
    read_json,
)
from shared.feature_flags import feature_enabled
from multi_agent_server.contracts import Feature, HumanReviewRequest, WorkflowRequest


WORKFLOW_STATES = {
    "awaiting_human_review",
    "accepted",
    "partially_accepted",
    "rejected",
}
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DECISION_STATES = {
    "accept": "accepted",
    "partially_accept": "partially_accepted",
    "reject": "rejected",
}


def public_runtime(runtime):
    result = public_evidence(runtime)
    # Numeric UUID segments and hashes are provenance, not phone numbers.
    for source, target, key in (
        (runtime, result, "selected_workflow_id"),
        (
            runtime.get("latest_workflow", {}),
            result.get("latest_workflow", {}),
            "workflow_id",
        ),
    ):
        value = source.get(key)
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,160}", value):
            target[key] = value
    for role, metadata in runtime.get("logs", {}).items():
        digest = metadata.get("sha256", "")
        if re.fullmatch(r"[a-f0-9]{64}", digest):
            result["logs"][role]["sha256"] = digest
    return result


def _timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.utcoffset() is not None else None
    except (AttributeError, TypeError, ValueError):
        return None


def _log_rows(relative_path, root):
    if not isinstance(relative_path, str) or Path(relative_path).is_absolute():
        raise ProbeConfigurationError("Workflow logs must use project-relative paths.")
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ProbeConfigurationError("Workflow logs must remain inside the project.")
    if not path.is_file():
        raise ValueError("Workflow log must be a regular file.")
    with path.open("rb") as stream:
        raw = stream.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Workflow log exceeds its size limit.")
    lines = raw.splitlines()
    if len(lines) > 5000:
        raise ValueError("Workflow log exceeds its record limit.")
    rows = [json.loads(line) for line in lines]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("Workflow logs must contain JSON objects.")
    return rows, {
        "path": relative_path,
        "sha256": sha256(raw).hexdigest(),
        "records": len(rows),
    }


def _verify_logs(workflow, rules, root):
    result = {
        "history_verified": False,
        "audit_chain_verified": False,
        "human_review_recorded": False,
        "human_review_approved": False,
        "logs": {},
    }
    files = rules.get("log_files", {})
    if not isinstance(files, dict):
        raise ProbeConfigurationError("Configure history and audit log paths.")
    for role in ("history", "audit"):
        try:
            rows, metadata = _log_rows(files.get(role), root)
            result["logs"][role] = metadata
            result[role + "_rows"] = [
                row for row in rows if row.get("workflow_id") == workflow["workflow_id"]
            ]
        except (OSError, ValueError, TypeError) as exc:
            result["logs"][role] = {"error": type(exc).__name__}
    history = result.pop("history_rows", [])
    audit = result.pop("audit_rows", [])
    result["history_verified"] = history == [workflow]
    request = workflow["request"]
    agents = rules["required_agents"]
    evidence_ids = [item["evidence_id"] for item in request["evidence"]]
    completed = audit[0] if audit else {}
    result["audit_chain_verified"] = all(
        (
            completed.get("event") == "workflow_completed",
            completed.get("timestamp") == workflow.get("timestamp"),
            completed.get("feature") == request.get("feature"),
            completed.get("participating_agents") == agents,
            completed.get("evidence_ids") == evidence_ids,
            type(completed.get("evidence_count")) is int
            and completed["evidence_count"] == len(evidence_ids),
            completed.get("models")
            == {agent: workflow[f"{agent}_result"].get("model") for agent in agents},
            completed.get("status") == "awaiting_human_review",
        )
    )
    review = workflow.get("human_review")
    if review is None:
        result["audit_chain_verified"] &= len(audit) == 1
        return result
    try:
        human = HumanReviewRequest.from_dict(review)
        reviewed_at = _timestamp(review.get("reviewed_at"))
        valid_review = bool(
            reviewed_at and reviewed_at >= _timestamp(workflow.get("timestamp"))
        )
        valid_review &= workflow.get("status") == DECISION_STATES[human.decision.value]
    except (ValueError, TypeError):
        valid_review = False
    event = audit[1] if len(audit) == 2 else {}
    result["human_review_recorded"] = bool(
        valid_review
        and result["history_verified"]
        and result["audit_chain_verified"]
        and event.get("event") == "human_review_recorded"
        and event.get("timestamp") == review.get("reviewed_at")
        and event.get("decision") == review.get("decision")
        and event.get("reviewed_by") == review.get("reviewed_by")
        and event.get("status") == workflow.get("status")
    )
    result["audit_chain_verified"] &= result["human_review_recorded"]
    result["human_review_approved"] = (
        result["human_review_recorded"] and review.get("decision") == "accept"
    )
    return result


def _agent_summary(workflow, required_agents):
    summaries = {}
    for agent in required_agents:
        result = workflow.get(f"{agent}_result")
        if not isinstance(result, dict):
            summaries[agent] = {"present": False, "completed": False}
            continue
        evidence_ids = result.get("evidence_ids", [])
        output = result.get(
            {"planner": "plan", "worker": "output", "reviewer": "review"}.get(agent)
        )
        summaries[agent] = {
            "present": True,
            "completed": result.get("status") == "completed",
            "agent": result.get("agent"),
            "model": result.get("model"),
            "evidence_ids": evidence_ids if isinstance(evidence_ids, list) else [],
            "human_approval_required": result.get("human_approval_required"),
            "output_present": isinstance(output, str) and bool(output.strip()),
        }
    return summaries


def _workflow_summary(workflow, required_agents):
    if not isinstance(workflow, dict):
        raise ValueError("Invalid Multi-Agent workflow response.")
    request_payload = workflow.get("request")
    request_payload = request_payload if isinstance(request_payload, dict) else {}
    human_review = workflow.get("human_review")
    human_review = human_review if isinstance(human_review, dict) else None
    return {
        "workflow_id": workflow.get("workflow_id"),
        "feature": request_payload.get("feature"),
        "status": workflow.get("status"),
        "timestamp": workflow.get("timestamp"),
        "evidence_count": len(request_payload.get("evidence", []))
        if isinstance(request_payload.get("evidence"), list)
        else 0,
        "agents": _agent_summary(workflow, required_agents),
        "human_review": None
        if human_review is None
        else {
            "decision": human_review.get("decision"),
            "reviewed_at": human_review.get("reviewed_at"),
            "reviewed_by": human_review.get("reviewed_by"),
        },
    }


def probe_runtime(config, *, project_root=PROJECT_ROOT):
    """Read one selected (or shared latest) workflow and its local persisted logs."""

    if not feature_enabled() or not feature_enabled("MULTI_AGENT_ENABLED"):
        raise ProbeConfigurationError(
            "AI_MODE_ENABLED or MULTI_AGENT_ENABLED disables live validation."
        )
    rules = config.get("multi_agent_rules", {})
    if not isinstance(rules, dict):
        raise ProbeConfigurationError("Configure Multi-Agent validation rules.")
    required_agents = rules.get("required_agents", [])
    if (
        not isinstance(required_agents, list)
        or not required_agents
        or len(required_agents) > 10
        or any(
            not isinstance(agent, str)
            or not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", agent)
            for agent in required_agents
        )
        or len(set(required_agents)) != len(required_agents)
    ):
        raise ProbeConfigurationError("Configure a bounded unique agent list.")
    workflow_id = os.getenv(
        "MULTI_AGENT_REVIEW_WORKFLOW_ID", config.get("multi_agent_workflow_id", "")
    )
    if (
        not isinstance(workflow_id, str)
        or (workflow_id and not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", workflow_id))
        or (rules.get("require_selected_workflow") and not workflow_id)
    ):
        raise ProbeConfigurationError(
            "Configure the selected workflow ID before support review."
        )
    expected_feature = rules.get("expected_feature")
    if expected_feature is not None and expected_feature not in {
        feature.value for feature in Feature
    }:
        raise ProbeConfigurationError("Configure a supported expected feature.")

    url = local_url(
        os.getenv(
            "MULTI_AGENT_SERVER_URL",
            config.get("multi_agent_server_url", "http://127.0.0.1:5004"),
        )
    )
    if urlsplit(url).path not in {"", "/"}:
        raise ProbeConfigurationError(
            "Multi-Agent URL must identify the local service root."
        )
    timeout = bounded_timeout(config.get("multi_agent_timeout_seconds", 10), 30)
    health_status, health = read_json("GET", url + "/health", timeout=timeout)
    if not isinstance(health, dict):
        raise ValueError("Invalid Multi-Agent health response.")

    runtime = {
        "available": health_status == 200
        and health.get("status") == "ok"
        and health.get("service") == "asd-marketplace-multi-agent",
        "health_status": health_status,
        "health": {
            "status": health.get("status"),
            "service": health.get("service"),
        },
        "latest_workflow_available": False,
        "latest_workflow_verified": False,
        "three_agents_completed": False,
        "human_review_recorded": False,
        "selection": "selected" if workflow_id else "latest",
        "selected_workflow_id": workflow_id or None,
        "expected_feature": expected_feature,
        "history_verified": False,
        "audit_chain_verified": False,
        "human_review_approved": False,
    }
    if not runtime["available"]:
        return public_runtime(runtime)

    latest_status, latest = read_json(
        "GET",
        url
        + "/api/workflows/"
        + (quote(workflow_id, safe="") if workflow_id else "latest"),
        timeout=timeout,
    )
    runtime["latest_status"] = latest_status
    if latest_status == 404:
        runtime["latest_skip_reason"] = "No workflow has been recorded yet."
        return public_runtime(runtime)
    if latest_status != 200:
        runtime["latest_error"] = "Latest workflow endpoint did not return HTTP 200."
        return public_runtime(runtime)

    summary = _workflow_summary(latest, required_agents)
    runtime["latest_workflow_available"] = True
    runtime["latest_workflow"] = summary
    agents = summary["agents"]
    runtime["three_agents_completed"] = all(
        agents.get(agent, {}).get("completed") is True
        and agents.get(agent, {}).get("agent") == agent
        and isinstance(agents[agent].get("model"), str)
        and bool(agents[agent]["model"].strip())
        and agents[agent].get("human_approval_required") is True
        and agents[agent].get("output_present") is True
        for agent in required_agents
    )
    try:
        validated = WorkflowRequest.from_dict(latest.get("request"))
        evidence_ids = [item.evidence_id for item in validated.evidence]
        runtime["evidence_ids_verified"] = all(
            agents[agent].get("evidence_ids") == evidence_ids
            for agent in required_agents
        )
        runtime["evidence_ids_verified"] &= (
            latest.get("planner_result", {}).get("objective") == validated.user_request
        )
        runtime["evidence_ids_verified"] &= latest.get("worker_result", {}).get(
            "evidence_count"
        ) == len(evidence_ids)
    except (ValueError, TypeError, KeyError):
        runtime["evidence_ids_verified"] = False
    runtime["scope_verified"] = (
        not workflow_id or summary["workflow_id"] == workflow_id
    ) and (expected_feature is None or summary["feature"] == expected_feature)
    runtime["latest_workflow_verified"] = (
        isinstance(summary.get("workflow_id"), str)
        and bool(summary["workflow_id"])
        and isinstance(summary.get("feature"), str)
        and bool(summary["feature"])
        and summary.get("status") in WORKFLOW_STATES
        and summary.get("evidence_count", 0) > 0
        and runtime["three_agents_completed"]
        and runtime["evidence_ids_verified"]
        and runtime["scope_verified"]
        and _timestamp(summary.get("timestamp")) is not None
        and (
            (latest.get("human_review") is None)
            == (summary.get("status") == "awaiting_human_review")
        )
    )
    if runtime["latest_workflow_verified"]:
        runtime.update(_verify_logs(latest, rules, Path(project_root)))
        runtime["latest_workflow_verified"] &= (
            runtime["history_verified"] and runtime["audit_chain_verified"]
        )
    runtime["review_evidence_complete"] = (
        runtime["latest_workflow_verified"] and runtime["human_review_recorded"]
    )
    return public_runtime(runtime)
