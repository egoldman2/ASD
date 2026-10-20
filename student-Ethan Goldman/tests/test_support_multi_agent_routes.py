"""Real support/auth/database/host HTTP with fixture agents, never live model proof."""

from hashlib import sha256
from importlib import import_module
from itertools import count
import json
from pathlib import Path
from types import SimpleNamespace

from flask import request
import pytest
import requests

from conftest import LiveServer
from test_mcp_tools import seed_ticket


@pytest.fixture
def multi_agent_host(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[2] / "ai-services")
    )
    from multi_agent_server.app import create_app
    from multi_agent_server.agents.planner_agent import PlannerResult
    from multi_agent_server.agents.worker_agent import WorkerResult
    from multi_agent_server.agents.reviewer_agent import ReviewerResult
    from multi_agent_server.coordinator import WorkflowCoordinator
    from multi_agent_server.workflow_store import WorkflowStore

    monkeypatch.setenv("AI_MODE_ENABLED", "true")
    monkeypatch.setenv("MULTI_AGENT_ENABLED", "true")
    store = WorkflowStore(tmp_path / "history.jsonl", tmp_path / "audit.jsonl")
    calls = []

    def common(workflow):
        return {
            "status": "completed",
            "model": "fixture-model",
            "evidence_ids": tuple(item.evidence_id for item in workflow.evidence),
            "human_approval_required": True,
            "elapsed_ms": 0,
        }

    def plan(workflow):
        calls.append(workflow.to_dict())
        return PlannerResult(
            agent="planner",
            objective=workflow.user_request,
            plan="Review the supplied ticket only.",
            **common(workflow),
        )

    workflow_ids = count(1)
    coordinator = WorkflowCoordinator(
        SimpleNamespace(plan=plan),
        SimpleNamespace(
            execute=lambda workflow, _plan: WorkerResult(
                agent="worker",
                output="Fixture proposed reply; do not post it.",
                evidence_count=len(workflow.evidence),
                **common(workflow),
            )
        ),
        SimpleNamespace(
            review=lambda workflow, _plan, _work: ReviewerResult(
                agent="reviewer",
                review="Fixture review; human decision required.",
                **common(workflow),
            )
        ),
        store,
        id_factory=lambda: f"00000412-0000-4000-8000-{next(workflow_ids):012x}",
    )
    app = create_app(coordinator=coordinator)

    @app.before_request
    def no_customer_credentials():
        assert not request.headers.get("Cookie") and not request.headers.get(
            "Authorization"
        )

    host = LiveServer(app)
    monkeypatch.setenv("MULTI_AGENT_SERVER_URL", host.url)
    try:
        yield SimpleNamespace(host=host, calls=calls, store=store)
    finally:
        host.close()


def endpoint(stack, ticket_id=2002, suffix=""):
    return f"{stack.backend.url}/api/support/admin/multi-agent/tickets/{ticket_id}/workflows{suffix}"


def test_create_redacts_bounded_snapshot_and_leaves_tickets_unchanged(
    support_stack, multi_agent_host
):
    ticket_id = seed_ticket(support_stack, messages=25)
    admin = support_stack.admin()
    before = sha256(support_stack.database_path.read_bytes()).hexdigest()
    response = admin.post(
        endpoint(support_stack, ticket_id),
        json={
            "question": "Review Jane Hidden's email jane.private@example.test and phone 0412 345 678."
        },
        headers=support_stack.origin_headers,
        timeout=10,
    )
    assert response.status_code == 201, response.text
    result = response.json()
    assert (
        result["status"] == "awaiting_human_review" and result["human_review"] is None
    )
    assert [
        result[f"{agent}_result"]["agent"]
        for agent in ("planner", "worker", "reviewer")
    ] == ["planner", "worker", "reviewer"]
    assert len(multi_agent_host.calls) == 1
    payload = multi_agent_host.calls[0]
    evidence = payload["evidence"][0]
    assert payload["feature"] == "customer_support"
    assert evidence["evidence_id"] == f"support-ticket-{ticket_id}"
    assert (
        evidence["source"]["endpoint"]
        == f"/api/tool-data/tickets/{ticket_id}?message_limit=20"
    )
    assert evidence["source"]["retrieved_at"].endswith("Z")
    data = evidence["data"]
    assert len(data["messages"]) == 20 and data["message_limit"] == 20
    assert data["message_count"] == 26 and data["messages_truncated"] is True
    assert data["messages"][0]["message"].startswith("Message 005")
    for private in (
        "Jane Hidden",
        "jane.private",
        "0412 345 678",
        "0412345678",
        "customer_user_id",
        "author_name",
        "customer_email_snapshot",
        admin.cookies.get("ethan_session"),
    ):
        assert private not in json.dumps(payload) + response.text
    # Phone fragments belong to customer content, not opaque IDs or timestamps.
    assert "0412" not in payload["user_request"] + json.dumps(data)
    assert result["workflow_id"].startswith("00000412-")
    assert "do not invent refund promises" in payload["user_request"]
    workflow_id = result["workflow_id"]
    assert (
        admin.get(
            endpoint(support_stack, ticket_id, "/" + workflow_id), timeout=10
        ).json()
        == result
    )
    assert admin.get(endpoint(support_stack, ticket_id), timeout=10).json() == {
        "count": 1,
        "workflows": [result],
    }
    assert sha256(support_stack.database_path.read_bytes()).hexdigest() == before
    assert len(multi_agent_host.store.list_audit_events()) == 1


def test_default_request_empty_history_and_missing_ticket(
    support_stack, multi_agent_host
):
    admin = support_stack.admin()
    assert admin.get(endpoint(support_stack), timeout=10).json() == {
        "count": 0,
        "workflows": [],
    }
    result = admin.post(
        endpoint(support_stack),
        json={},
        headers=support_stack.origin_headers,
        timeout=10,
    )
    assert result.status_code == 201
    assert "identify missing information" in multi_agent_host.calls[0]["user_request"]
    for method in ("get", "post"):
        response = getattr(admin, method)(
            endpoint(support_stack, 999999),
            **({"json": {}} if method == "post" else {}),
            headers=support_stack.origin_headers,
            timeout=10,
        )
        assert response.status_code == 404
    assert (
        admin.get(endpoint(support_stack, suffix="/missing"), timeout=10).status_code
        == 404
    )
    assert len(multi_agent_host.calls) == 1


def test_ticket_and_feature_histories_are_not_exposed(support_stack, multi_agent_host):
    admin = support_stack.admin()
    result = admin.post(
        endpoint(support_stack),
        json={},
        headers=support_stack.origin_headers,
        timeout=10,
    ).json()
    workflow_id = result["workflow_id"]
    assert (
        admin.get(
            endpoint(support_stack, 2003, "/" + workflow_id), timeout=10
        ).status_code
        == 404
    )
    assert (
        admin.get(endpoint(support_stack, 2003), timeout=10).json()["workflows"] == []
    )
    payload = dict(multi_agent_host.calls[0], feature="product_catalogue")
    other = requests.post(
        multi_agent_host.host.url + "/api/workflows", json=payload, timeout=10
    ).json()
    assert (
        admin.get(
            endpoint(support_stack, suffix="/" + other["workflow_id"]), timeout=10
        ).status_code
        == 404
    )
    assert admin.get(endpoint(support_stack), timeout=10).json()["count"] == 1


def test_auth_origin_and_invalid_payload_never_run_agents(
    support_stack, multi_agent_host
):
    url = endpoint(support_stack)
    headers = support_stack.origin_headers
    assert requests.post(url, json={}, headers=headers, timeout=10).status_code == 401
    assert requests.get(url, timeout=10).status_code == 401
    customer = support_stack.customer()
    assert customer.post(url, json={}, headers=headers, timeout=10).status_code == 403
    assert customer.get(url, timeout=10).status_code == 403
    admin = support_stack.admin()
    assert admin.post(url, json={}, timeout=10).status_code == 403
    for payload in (
        [],
        {"question": ""},
        {"question": 1},
        {"question": "x" * 1001},
        {"question": "test", "feature": "inventory"},
        {"evidence": []},
        {"reviewed_by": "forged"},
        {"url": "http://example.test"},
    ):
        assert (
            admin.post(url, json=payload, headers=headers, timeout=10).status_code
            == 400
        )
    assert (
        admin.post(url, data="not json", headers=headers, timeout=10).status_code == 400
    )
    assert admin.get(url, params={"ticket_id": 2003}, timeout=10).status_code == 400
    assert multi_agent_host.calls == []


@pytest.mark.parametrize("flag", ["AI_MODE_ENABLED", "MULTI_AGENT_ENABLED"])
def test_disabled_paths_do_not_read_evidence_or_contact_host(
    support_stack, monkeypatch, flag
):
    monkeypatch.setenv("AI_MODE_ENABLED", "true")
    monkeypatch.setenv("MULTI_AGENT_ENABLED", "true")
    monkeypatch.setenv(flag, "false")
    db_module = import_module("student-Ethan Goldman.support_backend.db_client")
    monkeypatch.setattr(
        db_module.SupportDatabaseClient,
        "get_ticket_context",
        lambda *args, **kwargs: pytest.fail("disabled evidence read"),
    )
    admin = support_stack.admin()
    for suffix, method in (
        ("", "post"),
        ("", "get"),
        ("/one", "get"),
        ("/one/review", "post"),
    ):
        response = getattr(admin, method)(
            endpoint(support_stack, suffix=suffix),
            **({"json": {}} if method == "post" else {}),
            headers=support_stack.origin_headers,
            timeout=10,
        )
        assert (
            response.status_code == 503
            and response.json()["error"]["code"] == "MULTI_AGENT_DISABLED"
        )
    assert (
        admin.get(
            support_stack.backend.url + "/api/support/admin/tickets", timeout=10
        ).status_code
        == 200
    )


@pytest.mark.parametrize("status", [502, 503, 504])
def test_upstream_failure_statuses_are_preserved(support_stack, monkeypatch, status):
    from shared.multi_agent_client import MultiAgentClient, MultiAgentClientError

    monkeypatch.setenv("AI_MODE_ENABLED", "true")
    monkeypatch.setenv("MULTI_AGENT_ENABLED", "true")

    def fail(*args, **kwargs):
        raise MultiAgentClientError("Safe fixture failure.", status_code=status)

    monkeypatch.setattr(MultiAgentClient, "create_workflow", fail)
    admin = support_stack.admin()
    response = admin.post(
        endpoint(support_stack),
        json={},
        headers=support_stack.origin_headers,
        timeout=10,
    )
    assert (
        response.status_code == status
        and response.json()["error"]["message"] == "Safe fixture failure."
    )


@pytest.mark.parametrize("context", [{"id": 2003}, {"id": 2002}])
def test_invalid_database_evidence_is_bad_gateway_before_agents(
    support_stack, multi_agent_host, monkeypatch, context
):
    module = import_module("student-Ethan Goldman.support_backend.db_client")
    monkeypatch.setattr(
        module.SupportDatabaseClient,
        "get_ticket_context",
        lambda *args, **kwargs: context,
    )
    admin = support_stack.admin()
    response = admin.post(
        endpoint(support_stack),
        json={},
        headers=support_stack.origin_headers,
        timeout=10,
    )
    assert response.status_code == 502
    assert multi_agent_host.calls == []


def test_creation_rejects_wrong_ticket_returned_by_upstream(
    support_stack, multi_agent_host, monkeypatch
):
    from shared.multi_agent_client import MultiAgentClient

    create = MultiAgentClient.create_workflow

    def wrong_ticket(self, payload):
        result = create(self, payload)
        result["request"]["evidence"][0]["data"]["id"] = 2003
        return result

    monkeypatch.setattr(MultiAgentClient, "create_workflow", wrong_ticket)
    admin = support_stack.admin()
    response = admin.post(
        endpoint(support_stack),
        json={},
        headers=support_stack.origin_headers,
        timeout=10,
    )
    assert response.status_code == 502


@pytest.mark.parametrize(
    "decision,status",
    [
        ("accept", "accepted"),
        ("partially_accept", "partially_accepted"),
        ("reject", "rejected"),
    ],
)
def test_human_decision_is_scoped_single_and_never_mutates_ticket(
    support_stack, multi_agent_host, decision, status
):
    admin = support_stack.admin()
    before = sha256(support_stack.database_path.read_bytes()).hexdigest()
    created = admin.post(
        endpoint(support_stack),
        json={},
        headers=support_stack.origin_headers,
        timeout=10,
    ).json()
    url = endpoint(support_stack, suffix="/" + created["workflow_id"] + "/review")
    response = admin.post(
        url,
        json={
            "decision": decision,
            "reason": "Fixture: verify order details before replying.",
        },
        headers=support_stack.origin_headers,
        timeout=10,
    )
    assert response.status_code == 200, response.text
    reviewed = response.json()
    assert reviewed["status"] == status
    assert reviewed["human_review"]["decision"] == decision
    assert reviewed["human_review"]["reviewed_by"] == "user:1"
    assert reviewed["human_review"]["reviewed_at"]
    for agent in ("planner", "worker", "reviewer"):
        assert reviewed[f"{agent}_result"] == created[f"{agent}_result"]
    assert (
        admin.post(
            url,
            json={"decision": decision, "reason": "Fixture duplicate"},
            headers=support_stack.origin_headers,
            timeout=10,
        ).status_code
        == 409
    )
    assert (
        admin.get(
            endpoint(support_stack, suffix="/" + created["workflow_id"]), timeout=10
        ).json()
        == reviewed
    )
    audit = multi_agent_host.store.list_audit_events()
    assert [item["event"] for item in audit] == [
        "workflow_completed",
        "human_review_recorded",
    ]
    assert audit[-1]["decision"] == decision and audit[-1]["reviewed_by"] == "user:1"
    assert sha256(support_stack.database_path.read_bytes()).hexdigest() == before


def test_invalid_or_unauthorized_decisions_leave_audit_unchanged(
    support_stack, multi_agent_host
):
    admin = support_stack.admin()
    created = admin.post(
        endpoint(support_stack),
        json={},
        headers=support_stack.origin_headers,
        timeout=10,
    ).json()
    suffix = "/" + created["workflow_id"] + "/review"
    url = endpoint(support_stack, suffix=suffix)
    payload = {"decision": "accept", "reason": "Fixture review."}
    assert (
        requests.post(
            url, json=payload, headers=support_stack.origin_headers, timeout=10
        ).status_code
        == 401
    )
    assert (
        support_stack.customer()
        .post(url, json=payload, headers=support_stack.origin_headers, timeout=10)
        .status_code
        == 403
    )
    assert admin.post(url, json=payload, timeout=10).status_code == 403
    for body in (
        {},
        [],
        {"decision": "accept"},
        {"decision": "maybe", "reason": "Fixture"},
        {"decision": [], "reason": "Fixture"},
        {"decision": "accept", "reason": " "},
        {"decision": "accept", "reason": "x" * 2001},
        {"decision": "accept", "reason": True},
        dict(payload, reviewed_by="forged"),
        dict(payload, feature="inventory"),
    ):
        assert (
            admin.post(
                url, json=body, headers=support_stack.origin_headers, timeout=10
            ).status_code
            == 400
        )
    assert (
        admin.post(
            endpoint(support_stack, 2003, suffix),
            json=payload,
            headers=support_stack.origin_headers,
            timeout=10,
        ).status_code
        == 404
    )
    assert (
        admin.post(
            endpoint(support_stack, suffix="/missing/review"),
            json=payload,
            headers=support_stack.origin_headers,
            timeout=10,
        ).status_code
        == 404
    )
    other = requests.post(
        multi_agent_host.host.url + "/api/workflows",
        json=dict(multi_agent_host.calls[0], feature="inventory"),
        timeout=10,
    ).json()
    assert (
        admin.post(
            endpoint(support_stack, suffix="/" + other["workflow_id"] + "/review"),
            json=payload,
            headers=support_stack.origin_headers,
            timeout=10,
        ).status_code
        == 404
    )
    assert all(
        item["event"] == "workflow_completed"
        for item in multi_agent_host.store.list_audit_events()
    )


def test_review_reason_is_redacted_before_history(support_stack, multi_agent_host):
    ticket_id = seed_ticket(support_stack)
    admin = support_stack.admin()
    created = admin.post(
        endpoint(support_stack, ticket_id),
        json={},
        headers=support_stack.origin_headers,
        timeout=10,
    ).json()
    response = admin.post(
        endpoint(support_stack, ticket_id, "/" + created["workflow_id"] + "/review"),
        json={
            "decision": "partially_accept",
            "reason": "Fixture: ask Jane Hidden at jane.private@example.test, 0412 345 678, to clarify.",
        },
        headers=support_stack.origin_headers,
        timeout=10,
    )
    assert response.status_code == 200
    history = multi_agent_host.store.history_path.read_text()
    for private in ("Jane Hidden", "jane.private", "0412 345 678", "0412345678"):
        assert private not in response.text + history
    assert "0412" not in response.json()["human_review"]["reason"]
    assert "0412" not in multi_agent_host.store.get_workflow(created["workflow_id"])["human_review"]["reason"]


def test_review_outage_leaves_workflow_pending(
    support_stack, multi_agent_host, monkeypatch
):
    from shared.multi_agent_client import MultiAgentClient, MultiAgentClientError

    admin = support_stack.admin()
    created = admin.post(
        endpoint(support_stack),
        json={},
        headers=support_stack.origin_headers,
        timeout=10,
    ).json()

    def unavailable(*args, **kwargs):
        raise MultiAgentClientError(
            "The Multi-Agent server is unavailable.", status_code=503
        )

    monkeypatch.setattr(MultiAgentClient, "submit_human_review", unavailable)
    response = admin.post(
        endpoint(support_stack, suffix="/" + created["workflow_id"] + "/review"),
        json={"decision": "accept", "reason": "Fixture review."},
        headers=support_stack.origin_headers,
        timeout=10,
    )
    assert response.status_code == 503
    stored = multi_agent_host.store.get_workflow(created["workflow_id"])
    assert (
        stored["status"] == "awaiting_human_review" and stored["human_review"] is None
    )
    assert len(multi_agent_host.store.list_audit_events()) == 1


def test_invalid_review_context_fails_before_decision(
    support_stack, multi_agent_host, monkeypatch
):
    admin = support_stack.admin()
    created = admin.post(
        endpoint(support_stack),
        json={},
        headers=support_stack.origin_headers,
        timeout=10,
    ).json()
    db = import_module("student-Ethan Goldman.support_backend.db_client")
    monkeypatch.setattr(
        db.SupportDatabaseClient,
        "get_ticket_context",
        lambda *args, **kwargs: {"id": 2002, "messages": ["invalid message"]},
    )
    response = admin.post(
        endpoint(support_stack, suffix="/" + created["workflow_id"] + "/review"),
        json={"decision": "accept", "reason": "Fixture decision."},
        headers=support_stack.origin_headers,
        timeout=10,
    )
    assert response.status_code == 502
    assert len(multi_agent_host.store.list_audit_events()) == 1
