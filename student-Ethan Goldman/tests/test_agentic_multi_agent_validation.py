"""Read-only review of real HTTP/store fixture workflows, without live models/humans."""

from copy import deepcopy
import json

import pytest
import requests

from test_goldman_agentic_review import load_agentic_loop
from test_support_multi_agent_routes import multi_agent_host  # noqa: F401


@pytest.fixture
def observed(multi_agent_host, tmp_path, monkeypatch):
    runner = load_agentic_loop("support_multi_agent_review")
    import multi_agent_validation as validation

    monkeypatch.delenv("MULTI_AGENT_REVIEW_WORKFLOW_ID", raising=False)
    payload = {
        "feature": "customer_support",
        "user_request": "Review fixture ticket 42.",
        "evidence": [
            {
                "evidence_id": "support-ticket-42",
                "data": {"id": 42},
                "source": {
                    "service": "customer-support-database",
                    "endpoint": "/api/tool-data/tickets/42?message_limit=20",
                    "retrieved_at": "2026-10-17T00:00:00+00:00",
                },
            }
        ],
    }
    response = requests.post(
        multi_agent_host.host.url + "/api/workflows", json=payload, timeout=5
    )
    assert response.status_code == 201, response.text
    workflow = response.json()
    config, _ = runner.load_feature("student-Ethan Goldman")
    config["multi_agent_workflow_id"] = workflow["workflow_id"]
    config["multi_agent_rules"]["log_files"] = {
        "history": "history.jsonl",
        "audit": "audit.jsonl",
    }

    def review(decision="reject"):
        response = requests.post(
            multi_agent_host.host.url
            + "/api/workflows/"
            + workflow["workflow_id"]
            + "/review",
            json={
                "decision": decision,
                "reason": "Synthetic fixture decision only.",
                "reviewed_by": "fixture-reviewer",
            },
            timeout=5,
        )
        assert response.status_code == 200
        return response.json()

    return runner, validation, config, workflow, review, tmp_path, multi_agent_host


@pytest.mark.parametrize("decision", ["accept", "partially_accept", "reject"])
def test_selected_workflow_matches_persisted_chain_and_decision(observed, decision):
    runner, validation, config, workflow, review, root, host = observed
    reviewed = review(decision)
    before = {path.name: path.read_bytes() for path in root.glob("*.jsonl")}
    runtime = validation.probe_runtime(config, project_root=root)
    assert runtime["selection"] == "selected"
    assert runtime["latest_workflow"]["workflow_id"] == workflow["workflow_id"]
    assert runtime["latest_workflow"]["human_review"]["decision"] == decision
    for field in (
        "scope_verified",
        "three_agents_completed",
        "evidence_ids_verified",
        "history_verified",
        "audit_chain_verified",
        "latest_workflow_verified",
        "human_review_recorded",
        "review_evidence_complete",
    ):
        assert runtime[field], (field, runtime)
    assert runtime["human_review_approved"] == (decision == "accept")
    assert before == {path.name: path.read_bytes() for path in root.glob("*.jsonl")}
    assert len(host.calls) == 1
    assert reviewed["worker_result"] == workflow["worker_result"]
    digest = runner._runtime_review_summary("multi-agent", runtime)
    assert (
        digest["audit_chain_verified"]
        and digest["expected_feature"] == "customer_support"
    )


def test_shared_latest_mode_remains_available(observed):
    runner, validation, config, workflow, review, root, _ = observed
    review()
    shared, _ = runner.load_feature("shared")
    shared["multi_agent_rules"]["log_files"] = config["multi_agent_rules"]["log_files"]
    runtime = validation.probe_runtime(shared, project_root=root)
    assert runtime["selection"] == "latest" and runtime["review_evidence_complete"]
    assert runtime["latest_workflow"]["workflow_id"] == workflow["workflow_id"]


def test_awaiting_decision_is_not_approved_or_complete(observed):
    _, validation, config, _, _, root, _ = observed
    runtime = validation.probe_runtime(config, project_root=root)
    assert runtime["latest_workflow_verified"] and runtime["three_agents_completed"]
    assert (
        not runtime["human_review_recorded"] and not runtime["review_evidence_complete"]
    )


@pytest.mark.parametrize(
    "change",
    [
        "feature",
        "id",
        "incomplete",
        "evidence",
        "model",
        "approval",
        "timestamp",
        "decision",
        "reason",
        "review_time",
    ],
)
def test_mismatched_or_incomplete_workflow_cannot_pass(observed, monkeypatch, change):
    _, validation, config, _, review, root, _ = observed
    workflow = review()
    if change == "feature":
        workflow["request"]["feature"] = "product_catalogue"
    elif change == "id":
        workflow["workflow_id"] = "different-workflow"
    elif change == "incomplete":
        workflow["worker_result"]["status"] = "running"
    elif change == "evidence":
        workflow["reviewer_result"]["evidence_ids"] = ["different-evidence"]
    elif change == "model":
        workflow["planner_result"]["model"] = ""
    elif change == "approval":
        workflow["reviewer_result"]["human_approval_required"] = False
    elif change == "timestamp":
        workflow["timestamp"] = "invalid"
    elif change == "decision":
        workflow["status"] = "accepted"
    elif change == "reason":
        workflow["human_review"]["reason"] = ""
    else:
        workflow["human_review"]["reviewed_at"] = "2000-01-01T00:00:00+00:00"
    original = validation.read_json
    monkeypatch.setattr(
        validation,
        "read_json",
        lambda method, url, **kw: (
            (200, deepcopy(workflow))
            if "/api/workflows/" in url
            else original(method, url, **kw)
        ),
    )
    runtime = validation.probe_runtime(config, project_root=root)
    assert (
        not runtime["latest_workflow_verified"] and not runtime["human_review_recorded"]
    )


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "malformed",
        "duplicate",
        "wrong_history",
        "order",
        "evidence",
        "model",
        "reviewer",
        "missing_review",
        "extra_event",
        "timestamp",
    ],
)
def test_missing_or_mismatched_logs_are_visible(observed, monkeypatch, change):
    _, validation, config, _, review, root, _ = observed
    workflow = review()
    path = root / (
        "history.jsonl" if change in {"duplicate", "wrong_history"} else "audit.jsonl"
    )
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if change == "missing":
        path.unlink()
    elif change == "malformed":
        path.write_text("{invalid\n")
    else:
        if change == "duplicate":
            rows += rows
        elif change == "wrong_history":
            rows[0]["worker_result"]["output"] = "Altered fixture output"
        elif change == "order":
            rows[0]["participating_agents"] = ["worker", "planner", "reviewer"]
        elif change == "evidence":
            rows[0]["evidence_ids"] = ["other-evidence"]
        elif change == "model":
            rows[0]["models"]["planner"] = "different-model"
        elif change == "reviewer":
            rows[1]["reviewed_by"] = "different-human"
        elif change == "missing_review":
            rows.pop()
        elif change == "extra_event":
            rows.append(rows[-1])
        else:
            rows[0]["timestamp"] = "2000-01-01T00:00:00+00:00"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    # Keep HTTP truthful while inspecting damaged local copies.
    original = validation.read_json
    monkeypatch.setattr(
        validation,
        "read_json",
        lambda method, url, **kw: (
            (200, deepcopy(workflow))
            if "/api/workflows/" in url
            else original(method, url, **kw)
        ),
    )
    runtime = validation.probe_runtime(config, project_root=root)
    assert (
        not runtime["review_evidence_complete"]
        and not runtime["latest_workflow_verified"]
    )
    assert not runtime["human_review_recorded"]
    if change in {"missing", "malformed"}:
        assert "error" in runtime["logs"]["audit"]


@pytest.mark.parametrize(
    "selection", ["", "../escape", "x?feature=other", "x/y", "x" * 161]
)
def test_support_requires_safe_explicit_selection(observed, selection):
    _, validation, config, _, _, root, _ = observed
    config["multi_agent_workflow_id"] = selection
    with pytest.raises(validation.ProbeConfigurationError):
        validation.probe_runtime(config, project_root=root)


@pytest.mark.parametrize(
    "path", ["../outside.jsonl", "/outside.jsonl", "link.jsonl", "oversized.jsonl"]
)
def test_log_reads_are_confined_and_bounded(observed, path):
    _, validation, config, _, review, root, _ = observed
    review()
    (root / "link.jsonl").symlink_to(root.parent / "outside.jsonl")
    (root / "oversized.jsonl").write_bytes(b" " * (2 * 1024 * 1024 + 1))
    config["multi_agent_rules"]["log_files"]["audit"] = path
    runtime = validation.probe_runtime(config, project_root=root)
    assert "error" in runtime["logs"]["audit"]
    assert not runtime["review_evidence_complete"]


def test_support_does_not_fall_back_to_global_catalogue_latest(observed, monkeypatch):
    _, validation, config, workflow, review, root, host = observed
    review()
    monkeypatch.setenv("MULTI_AGENT_REVIEW_WORKFLOW_ID", "missing-support-workflow")
    runtime = validation.probe_runtime(config, project_root=root)
    assert runtime["latest_status"] == 404 and not runtime["latest_workflow_available"]
    assert len(host.calls) == 1 and workflow["request"]["feature"] == "customer_support"


def test_registration_disabled_runtime_and_unsupported_claims(observed, monkeypatch):
    runner, _, config, _, _, _, _ = observed
    monkeypatch.setenv("MULTI_AGENT_ENABLED", "false")
    evidence = runner.collect_multi_agent_evidence(config)
    assert not evidence["runtime"]["attempted"]
    assert all(evidence["verified_checks"]["source_checks"].values())
    assert evidence["verified_checks"]["present_files"] == len(
        config["multi-agent_files"]
    )
    candidate = "Planner Worker Reviewer. Selected workflow verified. Audit verified. Human approved. Release approved."
    issues = runner._deterministic_issues("multi-agent", evidence, candidate)
    assert any("logs" in issue for issue in issues)
    assert any("approval" in issue for issue in issues)
    fallback = runner._grounded_fallback("multi-agent", evidence, issues, config)
    assert "complete review evidence: False" in fallback
    assert "release approval" in fallback


def test_uuid_and_digest_provenance_survive_phone_redaction(monkeypatch):
    runner = load_agentic_loop("multi_agent_provenance")
    from multi_agent_validation import public_runtime

    monkeypatch.setenv("AI_MODE_ENABLED", "true")
    monkeypatch.setenv("MULTI_AGENT_ENABLED", "true")

    workflow_id = "bf2f47de-5037-4980-b9c2-123929b0472e"
    digest = "1234567890" * 6 + "abcd"
    runtime = public_runtime(
        {
            "selected_workflow_id": workflow_id,
            "latest_workflow": {"workflow_id": workflow_id},
            "logs": {"history": {"sha256": digest}},
            "message": "Private fixture text",
            "reviewed_by": "private@example.test",
        }
    )
    assert (
        runtime["selected_workflow_id"]
        == runtime["latest_workflow"]["workflow_id"]
        == workflow_id
    )
    assert runtime["logs"]["history"]["sha256"] == digest
    assert (
        "private@example.test" not in json.dumps(runtime)
        and runtime["message"] == "<redacted>"
    )
    config, _ = runner.load_feature("student-Ethan Goldman")
    evidence = runner.collect_multi_agent_evidence(
        config, runtime_probe=lambda _: runtime
    )
    assert evidence["runtime"]["selected_workflow_id"] == workflow_id


def test_review_http_rejects_nonlocal_urls_and_redirected_model(monkeypatch):
    runner = load_agentic_loop("multi_agent_http_boundary")
    monkeypatch.setenv("AI_MODE_ENABLED", "true")
    calls = []

    class Response:
        status_code = 302
        headers = {"Content-Type": "text/html"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def raise_for_status(self):
            pass

        def iter_content(self, size):
            yield b"redirect"

    def response(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(runner.requests, "get", response)
    monkeypatch.setattr(runner.requests, "post", response)
    evidence = runner.collect_endpoint_evidence(
        {
            "endpoints": [
                {"name": "Invalid", "url": "file:///outside.json"},
                {"name": "Redirect", "url": "http://localhost:5004/health"},
            ]
        }
    )
    assert evidence["endpoints"][0]["error"] == "ProbeConfigurationError"
    assert evidence["endpoints"][1]["status"] == 302
    assert len(calls) == 1 and calls[0][1]["allow_redirects"] is False
    monkeypatch.setattr(runner, "OLLAMA_URL", "http://127.0.0.1:11434")
    with pytest.raises(runner.OllamaError, match="HTTP 200"):
        runner._call_ollama("Review collected evidence.")
    assert calls[-1][1]["allow_redirects"] is False


def test_quoted_schema_identifier_is_data_and_database_stays_read_only(tmp_path):
    import sqlite3

    runner = load_agentic_loop("multi_agent_quoted_identifier")
    runner.PROJECT_ROOT = tmp_path
    path = tmp_path / "fixture.db"
    name = 'fixture"; DROP TABLE other; --'
    with sqlite3.connect(path) as connection:
        connection.execute(
            f"CREATE TABLE {runner._quoted_identifier(name)} (id INTEGER)"
        )
        connection.execute(f"INSERT INTO {runner._quoted_identifier(name)} VALUES (1)")  # noqa: S608 - Exercise the identifier quoting boundary with a hostile fixture name.
        connection.execute("CREATE TABLE other (id INTEGER)")
    before = path.read_bytes()
    evidence = runner.collect_database_evidence({"database": "fixture.db"})
    assert (
        evidence["tables"][name]["record_count"] == 1 and "other" in evidence["tables"]
    )
    assert path.read_bytes() == before
