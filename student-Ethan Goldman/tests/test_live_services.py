"""Real HTTP integration checks for Ethan Goldman's Release 0 services."""

from importlib import import_module
import hashlib
import json
import logging
import os
import re

import pytest
import requests

from conftest import LiveServer, TRUSTED_ORIGIN


def support_url(stack, path):
    return f"{stack.backend.url}{path}"


def test_live_auth_roles_and_ticket_ownership(support_stack):
    anonymous = requests.get(
        support_url(support_stack, "/api/support/customer/tickets"), timeout=10
    )
    assert anonymous.status_code == 401

    customer = support_stack.customer()
    own = customer.get(
        support_url(support_stack, "/api/support/customer/tickets"), timeout=10
    )
    assert own.status_code == 200
    assert [ticket["id"] for ticket in own.json()["tickets"]] == [2002]
    assert customer.get(
        support_url(support_stack, "/api/support/customer/tickets/2003"), timeout=10
    ).status_code == 404
    assert customer.get(
        support_url(support_stack, "/api/support/admin/tickets"), timeout=10
    ).status_code == 403

    admin = support_stack.admin()
    result = admin.get(
        support_url(support_stack, "/api/support/admin/tickets?search=2003"),
        timeout=10,
    )
    assert result.status_code == 200
    assert [ticket["id"] for ticket in result.json()["tickets"]] == [2003]


def test_live_customer_create_and_reply_use_verified_identity(support_stack):
    customer = support_stack.customer()
    created = customer.post(
        support_url(support_stack, "/api/support/customer/tickets"),
        headers=support_stack.origin_headers,
        json={
            "subject": "A real integrated support request",
            "message": "Please investigate this through the actual services.",
            "customer_user_id": "3",
            "customer_name": "Spoofed Name",
            "customer_email": "spoofed@example.test",
            "category": "payment",
            "priority": "urgent",
            "status": "solved",
            "assigned_to": "Attacker",
        },
        timeout=10,
    )
    assert created.status_code == 201
    ticket = created.json()["ticket"]
    assert ticket["customer_user_id"] == "2"
    assert ticket["customer_name_snapshot"] == "Demo Customer"
    assert ticket["customer_email_snapshot"] == "customer@asd.local"
    assert (ticket["category"], ticket["priority"], ticket["status"]) == (
        "unclassified",
        "unclassified",
        "needs_triage",
    )

    replied = customer.post(
        support_url(
            support_stack, f"/api/support/customer/tickets/{ticket['id']}/messages"
        ),
        headers=support_stack.origin_headers,
        json={"message": "This is my genuine follow-up.", "sender_role": "staff"},
        timeout=10,
    )
    assert replied.status_code == 201
    assert replied.json()["ticket"]["messages"][-1]["sender_role"] == "customer"

    other_customer = support_stack.customer("ava@example.test")
    assert other_customer.get(
        support_url(
            support_stack, f"/api/support/customer/tickets/{ticket['id']}"
        ),
        timeout=10,
    ).status_code == 404
    message_count = len(ticket["messages"]) + 1
    denied_reply = other_customer.post(
        support_url(
            support_stack, f"/api/support/customer/tickets/{ticket['id']}/messages"
        ),
        headers=support_stack.origin_headers,
        json={"message": "This reply must not be accepted."},
        timeout=10,
    )
    assert denied_reply.status_code == 404
    owner_view = customer.get(
        support_url(support_stack, f"/api/support/customer/tickets/{ticket['id']}"),
        timeout=10,
    ).json()["ticket"]
    assert len(owner_view["messages"]) == message_count


def test_live_admin_update_reply_and_delete(support_stack):
    customer = support_stack.customer()
    created = customer.post(
        support_url(support_stack, "/api/support/customer/tickets"),
        headers=support_stack.origin_headers,
        json={"subject": "Admin CRUD integration", "message": "Please triage this."},
        timeout=10,
    )
    ticket_id = created.json()["ticket"]["id"]
    admin = support_stack.admin()

    updated = admin.put(
        support_url(support_stack, f"/api/support/admin/tickets/{ticket_id}"),
        headers=support_stack.origin_headers,
        json={
            "category": "account",
            "priority": "high",
            "status": "open",
            "assigned_to": "Marketplace Administrator",
        },
        timeout=10,
    )
    assert updated.status_code == 200
    assert updated.json()["ticket"]["category"] == "account"

    applied = admin.put(
        support_url(support_stack, f"/api/support/admin/tickets/{ticket_id}"),
        headers=support_stack.origin_headers,
        json={"apply_ai_suggestions": {"category": "other", "priority": "medium"}},
        timeout=10,
    )
    assert applied.status_code == 200
    assert applied.json()["ticket"]["triage_applied_by"] == "1"

    reply = admin.post(
        support_url(
            support_stack, f"/api/support/admin/tickets/{ticket_id}/messages"
        ),
        headers=support_stack.origin_headers,
        json={"message": "A genuine staff response.", "sender_role": "customer"},
        timeout=10,
    )
    assert reply.status_code == 201
    assert reply.json()["ticket"]["messages"][-1]["sender_role"] == "staff"

    deleted = admin.delete(
        support_url(support_stack, f"/api/support/admin/tickets/{ticket_id}"),
        headers=support_stack.origin_headers,
        timeout=10,
    )
    assert deleted.status_code == 200
    assert admin.get(
        support_url(support_stack, f"/api/support/admin/tickets/{ticket_id}"),
        timeout=10,
    ).status_code == 404


def test_live_origin_and_validation_fail_closed(support_stack):
    customer = support_stack.customer()
    assert customer.post(
        support_url(support_stack, "/api/support/customer/tickets"),
        json={"subject": "Missing origin request", "message": "Blocked"},
        timeout=10,
    ).status_code == 403
    invalid = customer.post(
        support_url(support_stack, "/api/support/customer/tickets"),
        headers={"Origin": TRUSTED_ORIGIN},
        json={"subject": "bad", "message": ""},
        timeout=10,
    )
    assert invalid.status_code == 400


def test_live_database_outage_returns_503(auth_services):
    support_app = import_module("student-Ethan Goldman.support_backend.app")
    application = support_app.create_app(
        {
            "AUTH_SERVICE_URL": auth_services.backend.url,
            "AUTH_TIMEOUT_SECONDS": 2,
            "SUPPORT_DATABASE_API_URL": "http://127.0.0.1:1",
            "SUPPORT_DATABASE_TIMEOUT": 0.2,
            "SUPPORT_FRONTEND_ORIGIN": TRUSTED_ORIGIN,
        }
    )
    server = LiveServer(application)
    try:
        customer = auth_services.login(
            "customer@asd.local", "CustomerPass!2026"
        )
        response = customer.get(
            f"{server.url}/api/support/customer/tickets", timeout=10
        )
        assert response.status_code == 503

        fragment = customer.get(
            f"{server.url}/api/support/ui/customer/tickets",
            headers={"HX-Request": "true"},
            timeout=10,
        )
        assert fragment.status_code == 503
        assert 'data-status="503"' in fragment.text
        assert 'id="ticket-list-region"' in fragment.text
    finally:
        server.close()


def test_live_htmx_customer_workflow_and_escaped_fragments(support_stack):
    entry = requests.get(
        support_url(support_stack, "/api/support/ui/entry"),
        headers={"HX-Request": "true"},
        timeout=10,
    )
    assert entry.status_code == 200
    assert entry.headers["HX-Redirect"].startswith("http://localhost:8003/index.html?")
    page_entry = requests.get(
        support_url(support_stack, "/api/support/ui/entry"),
        allow_redirects=False,
        timeout=10,
    )
    assert page_entry.status_code == 302
    assert page_entry.headers["Location"].startswith("http://localhost:8003/index.html?")

    anonymous = requests.get(
        support_url(support_stack, "/api/support/ui/customer/dashboard"),
        headers={"HX-Request": "true"},
        timeout=10,
    )
    assert anonymous.status_code == 401
    assert 'data-status="401"' in anonymous.text

    customer = support_stack.customer()
    customer_entry = customer.get(
        support_url(support_stack, "/api/support/ui/entry"),
        headers={"HX-Request": "true"},
        timeout=10,
    )
    assert customer_entry.status_code == 200
    assert customer_entry.headers["HX-Redirect"] == "/customer.html"
    customer_page_entry = customer.get(
        support_url(support_stack, "/api/support/ui/entry"),
        allow_redirects=False,
        timeout=10,
    )
    assert customer_page_entry.status_code == 302
    assert customer_page_entry.headers["Location"] == "/customer.html"
    assert customer.get(
        support_url(support_stack, "/api/support/ui/access/customer"), timeout=10
    ).status_code == 204
    assert customer.get(
        support_url(support_stack, "/api/support/ui/access/admin"), timeout=10
    ).status_code == 403
    forbidden = customer.get(
        support_url(support_stack, "/api/support/ui/admin/tickets"),
        headers={"HX-Request": "true"},
        timeout=10,
    )
    assert forbidden.status_code == 403
    assert 'data-status="403"' in forbidden.text
    dashboard = customer.get(
        support_url(support_stack, "/api/support/ui/customer/dashboard"),
        headers={"HX-Request": "true"},
        timeout=10,
    )
    assert dashboard.status_code == 200
    assert 'hx-post="/api/support/ui/customer/tickets"' in dashboard.text
    assert 'hx-get="/api/support/ui/customer/tickets"' in dashboard.text
    message_tag = re.search(r'<textarea id="ticket-message"[^>]*>', dashboard.text)
    assert message_tag is not None
    assert 'maxlength="2000"' in message_tag.group()
    assert "minlength=" not in message_tag.group()

    lower_bound = customer.post(
        support_url(support_stack, "/api/support/ui/customer/tickets"),
        headers=support_stack.htmx_headers,
        data={"subject": "One-character message", "message": "x"},
        timeout=10,
    )
    assert lower_bound.status_code == 201
    assert "Support ticket created." in lower_bound.text

    hostile_subject = "<script>alert('ticket')</script>"
    hostile_message = "Please render <script>alert('message')</script> as text."
    created = customer.post(
        support_url(support_stack, "/api/support/ui/customer/tickets"),
        headers=support_stack.htmx_headers,
        data={"subject": hostile_subject, "message": hostile_message},
        timeout=10,
    )
    assert created.status_code == 201
    assert created.headers["HX-Trigger"] == "supportTicketsChanged"

    records = customer.get(
        support_url(support_stack, "/api/support/customer/tickets"), timeout=10
    ).json()["tickets"]
    ticket_id = next(ticket["id"] for ticket in records if ticket["subject"] == hostile_subject)
    ticket_list = customer.get(
        support_url(support_stack, "/api/support/ui/customer/tickets"),
        headers={"HX-Request": "true"},
        timeout=10,
    )
    assert "<script>alert('ticket')</script>" not in ticket_list.text
    assert "&lt;script&gt;alert" in ticket_list.text
    assert f'hx-get="/api/support/ui/customer/tickets/{ticket_id}"' in ticket_list.text

    detail = customer.get(
        support_url(support_stack, f"/api/support/ui/customer/tickets/{ticket_id}"),
        headers={"HX-Request": "true"},
        timeout=10,
    )
    assert detail.status_code == 200
    assert "<script>alert('message')</script>" not in detail.text
    assert "&lt;script&gt;alert" in detail.text
    assert f'hx-post="/api/support/ui/customer/tickets/{ticket_id}/messages"' in detail.text
    assert 'hx-get="/api/support/ui/customer/ticket-detail"' in detail.text

    closed = customer.get(
        support_url(support_stack, "/api/support/ui/customer/ticket-detail"),
        headers={"HX-Request": "true"},
        timeout=10,
    )
    assert closed.status_code == 200
    assert 'id="ticket-detail-region"' in closed.text
    assert hostile_subject not in closed.text

    invalid = customer.post(
        support_url(
            support_stack, f"/api/support/ui/customer/tickets/{ticket_id}/messages"
        ),
        headers=support_stack.htmx_headers,
        data={"message": "   "},
        timeout=10,
    )
    assert invalid.status_code == 400
    assert "Message is required." in invalid.text

    replied = customer.post(
        support_url(
            support_stack, f"/api/support/ui/customer/tickets/{ticket_id}/messages"
        ),
        headers=support_stack.htmx_headers,
        data={"message": "A real HTMX customer reply."},
        timeout=10,
    )
    assert replied.status_code == 201
    assert "A real HTMX customer reply." in replied.text

    other_customer = support_stack.customer("ava@example.test")
    denied = other_customer.get(
        support_url(support_stack, f"/api/support/ui/customer/tickets/{ticket_id}"),
        headers={"HX-Request": "true"},
        timeout=10,
    )
    assert denied.status_code == 404
    assert 'data-status="404"' in denied.text


def test_live_htmx_admin_workflow(support_stack):
    customer = support_stack.customer()
    created = customer.post(
        support_url(support_stack, "/api/support/customer/tickets"),
        headers=support_stack.origin_headers,
        json={"subject": "HTMX admin integration", "message": "Exercise every real route."},
        timeout=10,
    )
    ticket_id = created.json()["ticket"]["id"]
    admin = support_stack.admin()
    admin_entry = admin.get(
        support_url(support_stack, "/api/support/ui/entry"),
        headers={"HX-Request": "true"},
        timeout=10,
    )
    assert admin_entry.status_code == 200
    assert admin_entry.headers["HX-Redirect"] == "/staff.html"
    assert admin.get(
        support_url(support_stack, "/api/support/ui/access/admin"), timeout=10
    ).status_code == 204
    assert admin.get(
        support_url(support_stack, "/api/support/ui/access/customer"), timeout=10
    ).status_code == 403

    queue = admin.get(
        support_url(
            support_stack, "/api/support/ui/admin/tickets?search=HTMX+admin"
        ),
        headers={"HX-Request": "true"},
        timeout=10,
    )
    assert queue.status_code == 200
    assert f"staff-ticket.html?ticket={ticket_id}" in queue.text
    assert 'hx-get="/api/support/ui/admin/tickets"' in queue.text

    detail = admin.get(
        support_url(support_stack, f"/api/support/ui/admin/tickets/{ticket_id}"),
        headers={"HX-Request": "true"},
        timeout=10,
    )
    assert detail.status_code == 200
    assert f'hx-put="/api/support/ui/admin/tickets/{ticket_id}"' in detail.text
    assert f'hx-delete="/api/support/ui/admin/tickets/{ticket_id}"' in detail.text
    assert f'hx-post="/api/support/ui/admin/tickets/{ticket_id}/ai-analysis"' in detail.text

    updated = admin.put(
        support_url(support_stack, f"/api/support/ui/admin/tickets/{ticket_id}"),
        headers=support_stack.htmx_headers,
        data={
            "category": "account",
            "priority": "high",
            "status": "open",
            "assigned_to": "Marketplace Administrator",
        },
        timeout=10,
    )
    assert updated.status_code == 200
    assert "Marketplace Administrator" in updated.text

    assigned_queue = admin.get(
        support_url(
            support_stack,
            "/api/support/ui/admin/tickets?assigned_to=Marketplace+Administrator",
        ),
        headers={"HX-Request": "true"},
        timeout=10,
    )
    assert assigned_queue.status_code == 200
    assert f"staff-ticket.html?ticket={ticket_id}" in assigned_queue.text
    assert 'value="Marketplace Administrator"' in assigned_queue.text

    applied = admin.put(
        support_url(support_stack, f"/api/support/ui/admin/tickets/{ticket_id}"),
        headers=support_stack.htmx_headers,
        data={"apply_ai_suggestions": "1", "category": "other", "priority": "medium"},
        timeout=10,
    )
    assert applied.status_code == 200
    stored = admin.get(
        support_url(support_stack, f"/api/support/admin/tickets/{ticket_id}"), timeout=10
    ).json()["ticket"]
    assert stored["triage_applied_by"] == "1"

    invalid_reply = admin.post(
        support_url(
            support_stack, f"/api/support/ui/admin/tickets/{ticket_id}/messages"
        ),
        headers=support_stack.htmx_headers,
        data={"message": "\t"},
        timeout=10,
    )
    assert invalid_reply.status_code == 400
    assert "Message is required." in invalid_reply.text

    reply = admin.post(
        support_url(
            support_stack, f"/api/support/ui/admin/tickets/{ticket_id}/messages"
        ),
        headers=support_stack.htmx_headers,
        data={"message": "A real HTMX staff reply."},
        timeout=10,
    )
    assert reply.status_code == 201
    assert "A real HTMX staff reply." in reply.text

    deleted = admin.delete(
        support_url(support_stack, f"/api/support/ui/admin/tickets/{ticket_id}"),
        headers=support_stack.htmx_headers,
        timeout=10,
    )
    assert deleted.status_code == 204
    assert deleted.headers["HX-Redirect"] == "/staff.html"


def test_live_auth_service_outage_returns_503():
    support_app = import_module("student-Ethan Goldman.support_backend.app")
    application = support_app.create_app(
        {
            "AUTH_SERVICE_URL": "http://127.0.0.1:1",
            "AUTH_TIMEOUT_SECONDS": 0.2,
            "SUPPORT_DATABASE_API_URL": "http://127.0.0.1:1",
            "SUPPORT_DATABASE_TIMEOUT": 0.2,
            "SUPPORT_FRONTEND_ORIGIN": TRUSTED_ORIGIN,
        }
    )
    server = LiveServer(application)
    try:
        session = requests.Session()
        session.cookies.set("ethan_session", "unverifiable-session")
        response = session.get(
            f"{server.url}/api/support/ui/customer/dashboard",
            headers={"HX-Request": "true"},
            timeout=10,
        )
        assert response.status_code == 503
        assert 'data-status="503"' in response.text
    finally:
        server.close()


def test_live_htmx_ai_outage_returns_safe_503_fragment(support_stack):
    """Exercise the authenticated route against a genuine failed TCP connection."""

    previous_url = os.environ.get("OLLAMA_URL")
    previous_timeout = os.environ.get("OLLAMA_TIMEOUT_SECONDS")
    os.environ["OLLAMA_URL"] = "http://127.0.0.1:1"
    os.environ["OLLAMA_TIMEOUT_SECONDS"] = "0.2"
    try:
        response = support_stack.admin().post(
            support_url(
                support_stack,
                "/api/support/ui/admin/tickets/2002/ai-analysis",
            ),
            headers=support_stack.htmx_headers,
            timeout=10,
        )
    finally:
        if previous_url is None:
            os.environ.pop("OLLAMA_URL", None)
        else:
            os.environ["OLLAMA_URL"] = previous_url
        if previous_timeout is None:
            os.environ.pop("OLLAMA_TIMEOUT_SECONDS", None)
        else:
            os.environ["OLLAMA_TIMEOUT_SECONDS"] = previous_timeout

    assert response.status_code == 503
    assert 'id="ai-panel"' in response.text
    assert "The AI assistant is currently unavailable." in response.text
    assert "<script" not in response.text


def test_live_ollama_analysis_and_workflow_logs(support_stack, caplog):
    """Run only against a real installed model; never substitute a fake client."""

    if os.getenv("RUN_LIVE_AI") != "1":
        pytest.skip("Set RUN_LIVE_AI=1 when a real Ollama model is available.")
    ai = import_module("student-Ethan Goldman.support_backend.ai")
    ollama_url = os.getenv("OLLAMA_URL", ai.DEFAULT_OLLAMA_URL).rstrip("/")
    model = os.getenv("OLLAMA_MODEL", ai.DEFAULT_OLLAMA_MODEL)
    try:
        tags = requests.get(f"{ollama_url}/api/tags", timeout=5)
        tags.raise_for_status()
    except requests.RequestException as exc:
        pytest.fail(f"RUN_LIVE_AI=1 but real Ollama is unavailable: {exc}")
    installed = {entry.get("name") for entry in tags.json().get("models", [])}
    if not any(name == model or name == f"{model}:latest" for name in installed):
        pytest.fail(f"RUN_LIVE_AI=1 but the real model is not installed: {model}")

    admin = support_stack.admin()
    endpoint = support_url(support_stack, "/api/support/admin/tickets/2002")
    before = admin.get(endpoint, timeout=10).json()["ticket"]
    before_hash = hashlib.sha256(support_stack.database_path.read_bytes()).hexdigest()
    assert ai.LOGGER.isEnabledFor(logging.INFO)
    response = admin.post(
        f"{endpoint}/ai-analysis",
        headers={**support_stack.origin_headers, "X-Correlation-ID": "a"},
        timeout=180,
    )
    assert response.status_code == 200, response.text
    result = response.json()
    analysis = result["analysis"]
    assert result["model"] == model
    assert result["correlation_id"] == "a"
    assert response.headers["X-Correlation-ID"] == "a"
    assert ai.validate_output(
        json.dumps(analysis),
        allowed_sources=("subject", "message-1", "message-2", "message-3"),
    ) == analysis
    assert "draft_response" not in analysis
    assert 1 <= len(analysis["suggested_steps"]) <= ai.MAX_SUGGESTED_STEPS
    assert set(analysis["suggested_steps"]).issubset(
        ai.CATEGORY_STEPS[analysis["category"]]
    )
    assert result["suggested_steps"] == [
        {"code": code, "label": ai.STEP_LABELS[code]}
        for code in analysis["suggested_steps"]
    ]
    after = admin.get(endpoint, timeout=10).json()["ticket"]
    after_hash = hashlib.sha256(support_stack.database_path.read_bytes()).hexdigest()
    assert after == before
    assert after_hash == before_hash

    workflow_records = [
        json.loads(record.getMessage())
        for record in caplog.records
        if '"event":"support_ai_workflow"' in record.getMessage()
    ]
    if result["retry_used"]:
        expected = [
            ("Plan", "pending", False),
            ("Act", "requested", False),
            ("Observe", "invalid", False),
            ("Adapt", "correction_retry", True),
            ("Act", "requested", True),
            ("Observe", "valid", True),
            ("Adapt", "accepted", True),
        ]
    else:
        expected = [
            ("Plan", "pending", False),
            ("Act", "requested", False),
            ("Observe", "valid", False),
            ("Adapt", "accepted", False),
        ]
    assert [
        (record["stage"], record["validation"], record["retry_used"])
        for record in workflow_records
    ] == expected
    assert {record["correlation_id"] for record in workflow_records} == {"a"}
    log_text = "\n".join(json.dumps(record) for record in workflow_records)
    for private_value in (
        "Demo Customer",
        "customer@asd.local",
        "My tracking page",
        "checked with my neighbours",
    ):
        assert private_value not in log_text
