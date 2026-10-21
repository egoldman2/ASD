"""HTMX workflow integration with disposable services and synthetic agents."""

from hashlib import sha256
from importlib import import_module
import json

import pytest
import requests

from conftest import LiveServer
from test_mcp_tools import seed_ticket
from test_support_multi_agent_routes import multi_agent_host


def url(stack, suffix="", ticket_id=2002):
    return f"{stack.backend.url}/api/support/ui/admin/multi-agent/tickets/{ticket_id}/workflows{suffix}"


def create(stack, host, admin):
    response = admin.post(url(stack), data={"question": "Fixture: propose a reply and action."},
                          headers=stack.htmx_headers, timeout=10)
    assert response.status_code == 201, response.text
    return host.store.list_workflows()[-1], response


def test_ticket_panel_loads_history_and_displays_escaped_outputs(support_stack, multi_agent_host):
    admin = support_stack.admin()
    detail = admin.get(support_stack.backend.url + "/api/support/ui/admin/tickets/2002", timeout=10)
    assert detail.status_code == 200 and 'id="multi-agent-panel"' in detail.text
    assert 'hx-get="/api/support/ui/admin/multi-agent/tickets/2002/workflows"' in detail.text
    initial = admin.get(url(support_stack), timeout=10)
    assert initial.status_code == 200 and "No workflows have been recorded" in initial.text
    before = sha256(support_stack.database_path.read_bytes()).hexdigest()
    record, response = create(support_stack, multi_agent_host, admin)
    for label in ("Planner", "Worker", "Reviewer", "awaiting human review", "Evidence captured:",
                  "Reason and any corrections", "Acceptance records your decision only"):
        assert label in response.text
    assert 'name="question"' in response.text and 'maxlength="1000"' in response.text
    assert 'maxlength="2000"' in response.text and 'hx-disabled-elt="find button"' in response.text
    assert 'hx-sync="#multi-agent-panel:drop"' in response.text
    assert '"timeout":380000' in response.text
    hostile = '<script>alert("fixture")</script>'
    for agent, field in (("planner", "plan"), ("worker", "output"), ("reviewer", "review")):
        record[f"{agent}_result"][field] = hostile
    record["request"]["user_request"] = hostile
    multi_agent_host.store.history_path.write_text(json.dumps(record) + "\n")
    selected = admin.get(url(support_stack), params={"workflow_id": record["workflow_id"]}, timeout=10)
    assert selected.status_code == 200 and "&lt;script&gt;" in selected.text
    assert "<script>" not in selected.text and multi_agent_host.host.url not in selected.text
    assert sha256(support_stack.database_path.read_bytes()).hexdigest() == before


def test_panel_shows_truncation_without_private_ticket_data(support_stack, multi_agent_host):
    ticket_id = seed_ticket(support_stack, messages=25)
    response = support_stack.admin().post(url(support_stack, ticket_id=ticket_id),
                                         data={"question": "Fixture: review recorded messages; contact phone 0412 345 678."},
                                         headers=support_stack.htmx_headers, timeout=10)
    assert response.status_code == 201
    assert "20 of 26 messages included" in response.text
    assert "Conversation truncated to the latest 20 messages" in response.text
    for private in ("Jane Hidden", "jane.private", "0412 345 678", "0412345678"):
        assert private not in response.text
    assert "[phone removed]" in response.text


@pytest.mark.parametrize("decision,status", [
    ("accept", "accepted"), ("partially_accept", "partially accepted"), ("reject", "rejected"),
])
def test_staff_records_one_decision_and_reloads_history_after_backend_restart(support_stack, multi_agent_host, decision, status):
    admin = support_stack.admin()
    before = sha256(support_stack.database_path.read_bytes()).hexdigest()
    record, _ = create(support_stack, multi_agent_host, admin)
    review_url = url(support_stack, "/" + record["workflow_id"] + "/review")
    response = admin.post(review_url, data={"decision": decision, "reason": "Fixture correction: verify the order first."},
                          headers=support_stack.htmx_headers, timeout=10)
    assert response.status_code == 200, response.text
    assert f"<strong>{status}</strong>" in response.text and "Human decision:" in response.text
    assert "Fixture correction: verify the order first." in response.text and "user:1" in response.text
    assert 'name="reason"' not in response.text
    duplicate = admin.post(review_url, data={"decision": decision, "reason": "Fixture duplicate."},
                           headers=support_stack.htmx_headers, timeout=10)
    assert duplicate.status_code == 409
    assert duplicate.headers["HX-Retarget"] == "#multi-agent-feedback"
    assert duplicate.headers["HX-Reswap"] == "innerHTML" and "<form" not in duplicate.text
    create(support_stack, multi_agent_host, admin)
    app_module = import_module("student-Ethan Goldman.support_backend.app")
    replacement = LiveServer(app_module.create_app(dict(support_stack.backend.server.app.config)))
    try:
        reloaded = admin.get(url(support_stack).replace(support_stack.backend.url, replacement.url),
                             params={"workflow_id": record["workflow_id"]}, timeout=10)
        assert reloaded.status_code == 200 and f"<strong>{status}</strong>" in reloaded.text
        assert reloaded.text.count("<option") == 2
        assert "Fixture correction: verify the order first." in reloaded.text
    finally:
        replacement.close()
    assert len([event for event in multi_agent_host.store.list_audit_events() if event["event"] == "human_review_recorded"]) == 1
    assert sha256(support_stack.database_path.read_bytes()).hexdigest() == before


def test_invalid_or_denied_forms_never_run_agents_and_preserve_inputs(support_stack, multi_agent_host):
    endpoint = url(support_stack)
    headers = support_stack.htmx_headers
    for method in ("get", "post"):
        response = getattr(requests, method)(endpoint, headers=headers, timeout=10)
        assert response.status_code == 401
        assert response.headers["HX-Retarget"] == "#multi-agent-feedback"
    customer = support_stack.customer()
    assert customer.get(endpoint, timeout=10).status_code == 403
    assert customer.post(endpoint, data={}, headers=headers, timeout=10).status_code == 403
    admin = support_stack.admin()
    untrusted = admin.post(endpoint, data={"question": "Fixture"}, timeout=10)
    assert untrusted.status_code == 403 and untrusted.headers["HX-Retarget"] == "#multi-agent-feedback"
    assert not untrusted.headers["Content-Type"].startswith("application/json")
    for payload in ({"question": ""}, {"question": "x" * 1001}, {"question": "Fixture", "feature": "inventory"},
                    [("question", "one"), ("question", "two")]):
        response = admin.post(endpoint, data=payload, headers=headers, timeout=10)
        assert response.status_code == 400
        assert response.headers["HX-Retarget"] == "#multi-agent-feedback"
        assert response.headers["HX-Reswap"] == "innerHTML" and "<form" not in response.text
    assert admin.get(endpoint, params=[("workflow_id", "one"), ("workflow_id", "two")], timeout=10).status_code == 400
    for payload in ({"json": {"feature": "inventory", "evidence": []}}, {"data": "not a form"}):
        response = admin.post(endpoint, headers=headers, timeout=10, **payload)
        assert response.status_code == 400 and response.headers["HX-Retarget"] == "#multi-agent-feedback"
    assert admin.get(url(support_stack, ticket_id=999999), timeout=10).status_code == 404
    assert multi_agent_host.calls == []


def test_review_validation_and_wrong_ticket_do_not_change_audit(support_stack, multi_agent_host):
    admin = support_stack.admin()
    record, _ = create(support_stack, multi_agent_host, admin)
    suffix = "/" + record["workflow_id"] + "/review"
    for payload in ({"decision": "accept", "reason": ""}, {"decision": "reject", "reason": "x" * 2001},
                    {"decision": "accept", "reason": "Fixture", "reviewed_by": "forged"}):
        response = admin.post(url(support_stack, suffix), data=payload,
                              headers=support_stack.htmx_headers, timeout=10)
        assert response.status_code == 400
        assert response.headers["HX-Retarget"] == "#multi-agent-feedback" and "<textarea" not in response.text
    response = admin.post(url(support_stack, suffix, ticket_id=2003), data={"decision": "accept", "reason": "Fixture"},
                          headers=support_stack.htmx_headers, timeout=10)
    assert response.status_code == 404
    assert admin.get(url(support_stack, ticket_id=2003), params={"workflow_id": record["workflow_id"]}, timeout=10).status_code == 404
    assert len(multi_agent_host.store.list_audit_events()) == 1


@pytest.mark.parametrize("flag", ["AI_MODE_ENABLED", "MULTI_AGENT_ENABLED"])
def test_disabled_panel_does_not_contact_model_and_leaves_ticket_controls(support_stack, monkeypatch, flag):
    from shared.multi_agent_client import MultiAgentClient
    monkeypatch.setenv("AI_MODE_ENABLED", "true")
    monkeypatch.setenv("MULTI_AGENT_ENABLED", "true")
    monkeypatch.setenv(flag, "false")
    monkeypatch.setattr(MultiAgentClient, "list_workflows", lambda *args: pytest.fail("disabled host access"))
    admin = support_stack.admin()
    for method in ("get", "post"):
        response = getattr(admin, method)(url(support_stack), data={}, headers=support_stack.htmx_headers, timeout=10)
        assert response.status_code == 503
        assert response.headers["HX-Retarget"] == "#multi-agent-feedback" and "disabled" in response.text
    detail = admin.get(support_stack.backend.url + "/api/support/ui/admin/tickets/2002", timeout=10)
    assert detail.status_code == 200 and "Send reply" in detail.text and "Save changes" in detail.text


@pytest.mark.parametrize("status", [502, 503, 504])
def test_upstream_failure_stays_in_feedback_region(support_stack, monkeypatch, status):
    from shared.multi_agent_client import MultiAgentClient, MultiAgentClientError
    monkeypatch.setenv("AI_MODE_ENABLED", "true")
    monkeypatch.setenv("MULTI_AGENT_ENABLED", "true")

    def fail(*args):
        raise MultiAgentClientError("Fixture outage <script>unsafe</script>", status_code=status)

    monkeypatch.setattr(MultiAgentClient, "list_workflows", fail)
    response = support_stack.admin().get(url(support_stack), timeout=10)
    assert response.status_code == status and response.headers["HX-Retarget"] == "#multi-agent-feedback"
    assert "<script>" not in response.text and "&lt;script&gt;" in response.text
