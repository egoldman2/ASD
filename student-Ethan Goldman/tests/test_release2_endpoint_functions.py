"""Two assessed endpoint functions over real disposable HTTP/database services."""

import requests

from test_live_services import support_url


def test_customer_create_contract(support_stack):
    path = "/api/support/customer/tickets"
    endpoint = support_url(support_stack, path)
    headers = support_stack.origin_headers
    payload = {"subject": "Release 2 endpoint creation", "message": "Persist this original customer message."}
    assert requests.post(endpoint, json=payload, headers=headers, timeout=10).status_code == 401
    customer = support_stack.customer()
    assert customer.post(endpoint, json=payload, timeout=10).status_code == 403
    assert customer.post(endpoint, json=payload, headers={"Origin": "https://untrusted.example"}, timeout=10).status_code == 403
    for body in ([], {}, dict(payload, subject="bad"), dict(payload, subject="x" * 161),
                 dict(payload, message=""), dict(payload, message="x" * 2001)):
        assert customer.post(endpoint, json=body, headers=headers, timeout=10).status_code == 400
    created = customer.post(endpoint, json=dict(payload, customer_user_id="3",
                                               customer_name="Forged Name", customer_email="forged@example.test"),
                            headers=headers, timeout=10)
    assert created.status_code == 201
    ticket = created.json()["ticket"]
    persisted = requests.get(support_stack.database.url + f"/api/tickets/{ticket['id']}", timeout=10)
    assert persisted.status_code == 200
    stored = persisted.json()
    assert stored["subject"] == payload["subject"]
    assert stored["messages"][0]["message"] == payload["message"]
    assert stored["customer_user_id"] == "2"
    assert stored["customer_name_snapshot"] == "Demo Customer"
    assert stored["customer_email_snapshot"] == "customer@asd.local"


def test_admin_update_contract(support_stack):
    ticket_id = 2002
    endpoint = support_url(support_stack, f"/api/support/admin/tickets/{ticket_id}")
    database_endpoint = support_stack.database.url + f"/api/tickets/{ticket_id}"
    headers = support_stack.origin_headers
    updates = {"category": "account", "priority": "high", "status": "pending", "assigned_to": "Release 2 Staff"}
    original = requests.get(database_endpoint, timeout=10).json()
    assert requests.put(endpoint, json=updates, headers=headers, timeout=10).status_code == 401
    assert support_stack.customer().put(endpoint, json=updates, headers=headers, timeout=10).status_code == 403
    admin = support_stack.admin()
    assert admin.put(endpoint, json=updates, timeout=10).status_code == 403
    assert admin.put(endpoint, json=updates, headers={"Origin": "https://untrusted.example"}, timeout=10).status_code == 403
    for body in ([], {}, {"category": "unknown"}, {"priority": "bad"}, {"status": "invalid"}, {"assigned_to": "x" * 101}):
        assert admin.put(endpoint, json=body, headers=headers, timeout=10).status_code == 400
    missing = support_url(support_stack, "/api/support/admin/tickets/999999")
    assert admin.put(missing, json=updates, headers=headers, timeout=10).status_code == 404
    assert requests.get(database_endpoint, timeout=10).json() == original
    changed = admin.put(endpoint, json=updates, headers=headers, timeout=10)
    assert changed.status_code == 200
    persisted = requests.get(database_endpoint, timeout=10)
    assert persisted.status_code == 200
    stored = persisted.json()
    assert {field: stored[field] for field in updates} == updates
    assert stored["messages"] == original["messages"]
    assert stored["customer_user_id"] == original["customer_user_id"]
