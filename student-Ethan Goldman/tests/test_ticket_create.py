from importlib import import_module
import sqlite3


VALID_TICKET = {
    "customer_name": "Jamie Parker",
    "customer_email": "jamie.parker@example.com",
    "subject": "Unable to update delivery address",
    "message": "Please update the delivery address before my order is dispatched.",
    "category": "delivery",
    "priority": "high",
}


def test_json_creates_open_ticket_with_initial_message(client):
    response = client.post("/api/support-tickets", json=VALID_TICKET)

    assert response.status_code == 201
    ticket = response.json["ticket"]
    assert ticket["status"] == "open"
    assert ticket["assigned_to"] is None
    assert ticket["created_at"] == ticket["updated_at"]
    assert ticket["message_count"] == 1
    assert ticket["messages"][0]["sender_role"] == "customer"
    assert ticket["messages"][0]["message"] == VALID_TICKET["message"]

    queue = client.get("/api/support-tickets").json
    assert queue["count"] == 13
    assert queue["tickets"][0]["id"] == ticket["id"]


def test_ticket_creation_rejects_invalid_fields(client):
    invalid_cases = (
        ({**VALID_TICKET, "customer_name": "J"}, "Name must be"),
        ({**VALID_TICKET, "customer_email": "not-an-email"}, "valid email"),
        ({**VALID_TICKET, "subject": "Help"}, "Subject must be"),
        ({**VALID_TICKET, "message": "Too short"}, "Message must be"),
        ({**VALID_TICKET, "category": "shipping"}, "valid category"),
        ({**VALID_TICKET, "priority": "critical"}, "valid priority"),
    )

    for ticket, expected_error in invalid_cases:
        response = client.post("/api/support-tickets", json=ticket)
        assert response.status_code == 400
        assert expected_error in response.json["error"]

    assert client.get("/api/support-tickets").json["count"] == 12


def test_customer_htmx_creation_returns_ticket_notice(client):
    response = client.post(
        "/support-ui/customer/tickets",
        data=VALID_TICKET,
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 201
    assert b"was created" in response.data
    assert b"jamie.parker@example.com" in response.data


def test_customer_htmx_creation_renders_validation_notice(client):
    response = client.post(
        "/support-ui/customer/tickets",
        data={**VALID_TICKET, "message": ""},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 400
    assert b"Message must be between 10 and 2000 characters" in response.data
    assert b"formNotice--error" in response.data


def test_ticket_creation_database_failure_returns_safe_error(client, monkeypatch):
    ticket_model = import_module(
        "student-Ethan Goldman.backend.models.ticket_model"
    )

    def raise_database_error(*args):
        raise sqlite3.DatabaseError("database unavailable")

    monkeypatch.setattr(ticket_model, "create_ticket", raise_database_error)
    response = client.post("/api/support-tickets", json=VALID_TICKET)

    assert response.status_code == 500
    assert response.json == {"error": "Unable to create the support ticket."}
