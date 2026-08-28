from importlib import import_module
import sqlite3


VALID_UPDATE = {
    "category": "return",
    "priority": "urgent",
    "status": "pending",
    "assigned_to": "Jordan Lee",
}


def test_json_updates_ticket_management_fields(client):
    before = client.get("/api/support-tickets/1011").json["ticket"]

    response = client.put("/api/support-tickets/1011", json=VALID_UPDATE)

    assert response.status_code == 200
    ticket = response.json["ticket"]
    assert ticket["category"] == "return"
    assert ticket["priority"] == "urgent"
    assert ticket["status"] == "pending"
    assert ticket["assigned_to"] == "Jordan Lee"
    assert ticket["updated_at"] > before["updated_at"]
    assert ticket["messages"] == before["messages"]


def test_json_update_can_clear_assignee(client):
    response = client.put(
        "/api/support-tickets/1011",
        json={**VALID_UPDATE, "assigned_to": "  "},
    )

    assert response.status_code == 200
    assert response.json["ticket"]["assigned_to"] is None


def test_ticket_update_rejects_invalid_fields_without_changing_ticket(client):
    before = client.get("/api/support-tickets/1011").json["ticket"]
    invalid_cases = (
        ({**VALID_UPDATE, "category": "shipping"}, "valid category"),
        ({**VALID_UPDATE, "priority": "critical"}, "valid priority"),
        ({**VALID_UPDATE, "status": "closed"}, "valid status"),
        ({**VALID_UPDATE, "assigned_to": "A"}, "Assigned staff"),
    )

    for update, expected_error in invalid_cases:
        response = client.put("/api/support-tickets/1011", json=update)
        assert response.status_code == 400
        assert expected_error in response.json["error"]

    after = client.get("/api/support-tickets/1011").json["ticket"]
    assert after == before


def test_missing_ticket_update_returns_not_found(client):
    response = client.put("/api/support-tickets/9999", json=VALID_UPDATE)

    assert response.status_code == 404
    assert response.json == {"error": "Support ticket not found."}


def test_staff_htmx_update_renders_updated_ticket(client):
    response = client.put(
        "/support-ui/staff/tickets/1011",
        data=VALID_UPDATE,
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert b"Ticket details updated" in response.data
    assert b'value="return" selected' in response.data
    assert b'value="urgent" selected' in response.data
    assert b'value="pending" selected' in response.data
    assert b'value="Jordan Lee"' in response.data


def test_staff_htmx_update_renders_validation_error_with_ticket(client):
    response = client.put(
        "/support-ui/staff/tickets/1011",
        data={**VALID_UPDATE, "status": "closed"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 400
    assert b"Select a valid status" in response.data
    assert b"Parcel marked delivered but not received" in response.data


def test_ticket_update_database_failure_returns_safe_error(client, monkeypatch):
    ticket_model = import_module(
        "student-Ethan Goldman.backend.models.ticket_model"
    )

    def raise_database_error(*args):
        raise sqlite3.DatabaseError("database unavailable")

    monkeypatch.setattr(ticket_model, "update_ticket", raise_database_error)
    response = client.put("/api/support-tickets/1011", json=VALID_UPDATE)

    assert response.status_code == 500
    assert response.json == {"error": "Unable to update the support ticket."}
