"""Bounded, read-only runtime validation for the shared Multi-Agent Server."""

from __future__ import annotations

import os
import re
from urllib.parse import urlsplit

from mcp_validation import (
    ProbeConfigurationError,
    bounded_timeout,
    local_url,
    public_evidence,
    read_json,
)
from shared.feature_flags import feature_enabled


WORKFLOW_STATES = {
    "awaiting_human_review",
    "accepted",
    "partially_accepted",
    "rejected",
}


def _agent_summary(workflow, required_agents):
    summaries = {}
    for agent in required_agents:
        result = workflow.get(f"{agent}_result")
        if not isinstance(result, dict):
            summaries[agent] = {"present": False, "completed": False}
            continue
        evidence_ids = result.get("evidence_ids", [])
        summaries[agent] = {
            "present": True,
            "completed": result.get("status") == "completed",
            "agent": result.get("agent"),
            "model": result.get("model"),
            "evidence_ids": evidence_ids if isinstance(evidence_ids, list) else [],
            "human_approval_required": result.get("human_approval_required"),
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


def probe_runtime(config):
    """Read health and the latest workflow without creating or changing records."""

    if not feature_enabled() or not feature_enabled("MULTI_AGENT_ENABLED"):
        raise ProbeConfigurationError(
            "AI_MODE_ENABLED or MULTI_AGENT_ENABLED disables live validation."
        )
    rules = config.get("multi_agent_rules", {})
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
    }
    if not runtime["available"]:
        return public_evidence(runtime)

    latest_status, latest = read_json(
        "GET", url + "/api/workflows/latest", timeout=timeout
    )
    runtime["latest_status"] = latest_status
    if latest_status == 404:
        runtime["latest_skip_reason"] = "No workflow has been recorded yet."
        return public_evidence(runtime)
    if latest_status != 200:
        runtime["latest_error"] = "Latest workflow endpoint did not return HTTP 200."
        return public_evidence(runtime)

    summary = _workflow_summary(latest, required_agents)
    runtime["latest_workflow_available"] = True
    runtime["latest_workflow"] = summary
    agents = summary["agents"]
    runtime["three_agents_completed"] = all(
        agents.get(agent, {}).get("completed") is True
        and agents.get(agent, {}).get("agent") == agent
        for agent in required_agents
    )
    runtime["human_review_recorded"] = (
        isinstance(summary.get("human_review"), dict)
        and summary["human_review"].get("decision")
        in {"accept", "partially_accept", "reject"}
    )
    runtime["latest_workflow_verified"] = (
        isinstance(summary.get("workflow_id"), str)
        and bool(summary["workflow_id"])
        and isinstance(summary.get("feature"), str)
        and bool(summary["feature"])
        and summary.get("status") in WORKFLOW_STATES
        and summary.get("evidence_count", 0) > 0
        and runtime["three_agents_completed"]
    )
    return public_evidence(runtime)
