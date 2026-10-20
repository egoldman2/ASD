"""Accounts boundary tests: real shared client, no model or database mutation."""

from copy import deepcopy
import importlib.util
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest
import requests

from shared.multi_agent_client import MultiAgentClient, MultiAgentClientSettings


BASE = "/api/admin/multi-agent/workflows"


@pytest.fixture
def setup(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "backend" / "app.py"
    spec = importlib.util.spec_from_file_location("ethan_loyalty_workflow_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.config.update(TESTING=True, SECRET_KEY="workflow-test-key")
    monkeypatch.setenv("AI_MODE_ENABLED", "true")
    monkeypatch.setenv("MULTI_AGENT_ENABLED", "true")
    db_calls, http_calls, records = [], [], {}

    def database(path, method="GET", payload=None):
        db_calls.append((path, method, payload))
        assert method == "GET", "Workflow must never mutate customer data"
        if path == "/internal/users/1":
            return {"user": {"id": 1, "role": "admin", "is_active": 1,
                "full_name": "Private admin", "email": "admin@private.test"}}
        if path == "/internal/users/2":
            return {"user": {"id": 2, "role": "customer", "password_hash": "private-hash",
                "email": "private@example.test", "full_name": "Private customer"}}
        if path == "/internal/loyalty/2":
            return {"loyalty": {"points_balance": 720, "email": "private@example.test"}}
        if path == "/internal/loyalty/2/transactions?limit=5":
            return {"count": 1, "transactions": [{"id": 5, "user_id": 2,
                "points_change": 720, "reason": "Test credit", "created_at": "2026-10-20T10:00:00+11:00",
                "created_by": 1}]}
        raise HTTPError("http://database", 404, "Not found", {}, None)

    class Response:
        status_code = 200
        def __init__(self, payload): self.payload = payload
        def json(self): return deepcopy(self.payload)

    def http(**kwargs):
        http_calls.append(deepcopy(kwargs))
        suffix = kwargs["url"].split("http://test-server", 1)[1]
        body = kwargs.get("json")
        if suffix == "/api/workflows" and kwargs["method"] == "POST":
            record = {"workflow_id": "workflow-1", "timestamp": "2026-10-20T10:00:00+11:00",
                "status": "awaiting_human_review", "request": body, "human_review": None}
            for agent, key in (("planner", "plan"), ("worker", "output"), ("reviewer", "review")):
                record[f"{agent}_result"] = {"agent": agent, "status": "completed", "model": "test-model",
                    key: f"{agent} evidence-based result", "human_approval_required": True,
                    "evidence_ids": [body["evidence"][0]["evidence_id"]]}
            records["workflow-1"] = record
            return Response(record)
        if suffix == "/api/workflows":
            return Response({"workflows": list(records.values())})
        if suffix.endswith("/review"):
            record = records["workflow-1"]
            record["human_review"] = {**body, "reviewed_at": "2026-10-20T10:10:00+11:00"}
            record["status"] = {"accept": "accepted", "partially_accept": "partially_accepted", "reject": "rejected"}[body["decision"]]
            return Response(record)
        return Response(records["workflow-1"])

    monkeypatch.setattr(module, "database_request", database)
    monkeypatch.setattr(module, "loyalty_workflow_client", lambda: MultiAgentClient(
        "customer_loyalty", MultiAgentClientSettings(True, "http://test-server", 300), http_request=http))
    client = module.app.test_client()
    with client.session_transaction() as current:
        current["user"] = {"id": 1, "role": "admin"}
    return module, client, db_calls, http_calls, records


def create(setup):
    response = setup[1].post(BASE, json={"user_id": 2})
    assert response.status_code == 201, response.get_json()
    return response.get_json()


@pytest.mark.parametrize("role,status", [(None, 401), ("customer", 403)])
@pytest.mark.parametrize("method,path,body", [
    ("POST", BASE, {"user_id": 2}), ("GET", BASE + "?user_id=2", None),
    ("GET", BASE + "/workflow-1", None),
    ("POST", BASE + "/workflow-1/review", {"decision": "accept", "reason": "Checked"}),
])
def test_every_route_is_admin_only(setup, role, status, method, path, body):
    _, client, db, http, _ = setup
    with client.session_transaction() as current:
        current.clear()
        if role: current["user"] = {"id": 1, "role": role}
    assert client.open(path, method=method, json=body).status_code == status
    assert not http and not db


@pytest.mark.parametrize("flag", ["AI_MODE_ENABLED", "MULTI_AGENT_ENABLED"])
@pytest.mark.parametrize("method,path,body", [
    ("POST", BASE, {"user_id": 2}), ("GET", BASE + "?user_id=2", None),
    ("GET", BASE + "/workflow-1", None),
    ("POST", BASE + "/workflow-1/review", {"decision": "accept", "reason": "Checked"}),
])
def test_disabled_mode_never_calls_host(setup, monkeypatch, flag, method, path, body):
    monkeypatch.setenv(flag, "false")
    assert setup[1].open(path, method=method, json=body).status_code == 503
    assert not setup[3]


@pytest.mark.parametrize("body", [None, [], {}, {"user_id": True}, {"user_id": "2"},
    {"user_id": -1}, {"user_id": 2147483648}, {"user_id": 2, "evidence": []}])
def test_invalid_or_forged_creation(setup, body):
    assert setup[1].post(BASE, json=body).status_code == 400
    assert not setup[3]


def test_create_uses_only_backend_read_only_evidence(setup):
    record = create(setup)
    assert record["request"]["evidence"][0]["data"]["points_balance"] == 720
    assert record["status"] == "awaiting_human_review"
    sent = str(setup[3])
    for private in ("private@example.test", "private-hash", "Private customer", "admin@private.test", "created_by", "Cookie"):
        assert private not in sent
    assert all(call[1] == "GET" for call in setup[2])


@pytest.mark.parametrize("decision,status", [("accept", "accepted"), ("partially_accept", "partially_accepted"), ("reject", "rejected")])
def test_human_decision_and_duplicate_protection(setup, decision, status):
    create(setup)
    response = setup[1].post(BASE + "/workflow-1/review", json={"decision": decision, "reason": " Checked evidence "})
    assert response.status_code == 200
    assert response.json["status"] == status
    assert response.json["human_review"]["reviewed_by"] == "admin:1"
    assert response.json["human_review"]["reason"] == "Checked evidence"
    repeated = setup[1].post(BASE + "/workflow-1/review", json={"decision": "accept", "reason": "Again"})
    assert repeated.status_code == 409
    assert all(call[1] == "GET" for call in setup[2])


@pytest.mark.parametrize("body", [{}, {"decision": [], "reason": "ok"}, {"decision": "accept", "reason": " "},
    {"decision": "accept", "reason": "x" * 2001}, {"decision": "accept", "reason": "ok", "reviewed_by": "forged"}])
def test_invalid_or_forged_reviewer(setup, body):
    assert setup[1].post(BASE + "/workflow-1/review", json=body).status_code == 400
    assert not setup[3]


def test_history_filters_customer_and_survives_new_browser_session(setup):
    create(setup)
    assert setup[1].get(BASE + "?user_id=2").json["count"] == 1
    assert setup[1].get(BASE + "?user_id=3").json["count"] == 0
    assert setup[1].get(BASE + "/workflow-1").status_code == 200


@pytest.mark.parametrize("field,value", [("planner_result", {}), ("human_review", {}), ("status", "accepted"), ("request", {})])
def test_rejects_malformed_host_records(setup, field, value):
    create(setup)
    setup[4]["workflow-1"][field] = value
    assert setup[1].get(BASE + "/workflow-1").status_code == 502


def test_other_feature_is_not_exposed(setup):
    create(setup)
    setup[4]["workflow-1"]["request"]["feature"] = "inventory"
    assert setup[1].get(BASE + "/workflow-1").status_code == 404
    assert setup[1].get(BASE + "?user_id=2").json["count"] == 0


@pytest.mark.parametrize("exception,status", [(requests.Timeout(), 504), (requests.ConnectionError(), 503)])
def test_service_failure_is_retryable(setup, monkeypatch, exception, status):
    def fail(**kwargs): raise exception
    monkeypatch.setattr(setup[0], "loyalty_workflow_client", lambda: MultiAgentClient(
        "customer_loyalty", MultiAgentClientSettings(True, "http://test-server", 300), http_request=fail))
    assert setup[1].post(BASE, json={"user_id": 2}).status_code == status


def test_missing_customer_does_not_call_host(setup):
    assert setup[1].post(BASE, json={"user_id": 999}).status_code == 404
    assert not setup[3]


def test_database_outage_does_not_start_workflow(setup, monkeypatch):
    original = setup[0].database_request
    def fail(path, **kwargs):
        if path == "/internal/users/1": return original(path, **kwargs)
        raise URLError("offline")
    monkeypatch.setattr(setup[0], "database_request", fail)
    assert setup[1].post(BASE, json={"user_id": 2}).status_code == 503
    assert not setup[3]


@pytest.mark.parametrize("points,tier,next_tier,remaining", [(0, "Bronze", "Silver", 500),
    (499, "Bronze", "Silver", 1), (500, "Silver", "Gold", 500),
    (720, "Silver", "Gold", 280), (999, "Silver", "Gold", 1), (1000, "Gold", None, 0)])
def test_rule_based_progress_is_independent_of_ai(setup, points, tier, next_tier, remaining):
    assert setup[0].loyalty_workflow_progress(points) == {
        "tier": tier, "next_tier": next_tier, "points_to_next_tier": remaining}


def test_host_cannot_forge_verified_progress(setup):
    create(setup)
    setup[4]["workflow-1"]["request"]["evidence"][0]["data"]["verified_progress"]["tier"] = "Bronze"
    assert setup[1].get(BASE + "/workflow-1").status_code == 502


def test_unknown_host_fields_are_removed(setup):
    create(setup)
    record = setup[4]["workflow-1"]
    record["secret"] = "not-approved"
    record["worker_result"]["secret"] = "not-approved"
    result = setup[1].get(BASE + "/workflow-1")
    assert result.status_code == 200
    assert "not-approved" not in result.get_data(as_text=True)


@pytest.mark.parametrize("bad", [-1, True, "720", None])
def test_bad_database_balance_is_rejected(setup, monkeypatch, bad):
    original = setup[0].database_request
    def database(path, **kwargs):
        if path == "/internal/loyalty/2": return {"loyalty": {"points_balance": bad}}
        return original(path, **kwargs)
    monkeypatch.setattr(setup[0], "database_request", database)
    assert setup[1].post(BASE, json={"user_id": 2}).status_code == 502
    assert not setup[3]
