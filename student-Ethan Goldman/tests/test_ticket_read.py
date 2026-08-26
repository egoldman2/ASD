from importlib import import_module
import sqlite3


def test_list_support_tickets_json(client):
    response = client.get("/api/support-tickets")

    assert response.status_code == 200
    assert response.json["count"] == 12
    assert response.json["status_counts"] == {
        "open": 5,
        "pending": 3,
        "solved": 4,
    }
    assert response.json["tickets"][0]["id"] == 1012


def test_get_support_ticket_json(client):
    response = client.get("/api/support-tickets/1011")

    assert response.status_code == 200
    assert response.json["ticket"]["customer_name"] == "Oliver Jones"
    assert response.json["ticket"]["status"] == "open"
    assert response.json["ticket"]["message_count"] == 5
    assert [message["sender_role"] for message in response.json["ticket"]["messages"]] == [
        "customer",
        "staff",
        "customer",
        "staff",
        "customer",
    ]


def test_case_insensitive_ticket_search(client):
    response = client.get("/api/support-tickets?search=DELIVERED")

    assert response.status_code == 200
    assert response.json["count"] == 1
    assert response.json["tickets"][0]["id"] == 1011


def test_combined_ticket_filters(client):
    response = client.get(
        "/api/support-tickets?status=open&priority=high&category=delivery"
        "&assigned_to=Alex%20Morgan"
    )

    assert response.status_code == 200
    assert response.json["count"] == 1
    assert response.json["tickets"][0]["id"] == 1011
    assert response.json["status_counts"] == {
        "open": 1,
        "pending": 0,
        "solved": 0,
    }


def test_unassigned_ticket_filter(client):
    response = client.get("/api/support-tickets?assigned_to=unassigned")

    assert response.status_code == 200
    assert response.json["count"] == 3
    assert all(ticket["assigned_to"] is None for ticket in response.json["tickets"])


def test_invalid_ticket_filter_returns_bad_request(client):
    response = client.get("/api/support-tickets?status=closed")

    assert response.status_code == 400
    assert response.json == {"error": "Invalid status filter."}


def test_missing_support_ticket_returns_not_found(client):
    response = client.get("/api/support-tickets/9999")

    assert response.status_code == 404
    assert response.json == {"error": "Support ticket not found."}


def test_staff_ticket_list_htmx_fragment(client):
    response = client.get(
        "/support-ui/staff/tickets", headers={"HX-Request": "true"}
    )

    assert response.status_code == 200
    assert b"All tickets" in response.data
    assert b"#1011" in response.data
    assert b"Staff reply needed" in response.data


def test_staff_ticket_list_filters_and_empty_state(client):
    response = client.get(
        "/support-ui/staff/tickets?search=no%20matching%20ticket",
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert b"No tickets found" in response.data
    assert b"ticketFilters" in response.data


def test_staff_ticket_detail_htmx_fragment(client):
    response = client.get(
        "/support-ui/staff/tickets/1011", headers={"HX-Request": "true"}
    )

    assert response.status_code == 200
    assert b"Parcel marked delivered but not received" in response.data
    assert b"Oliver Jones" in response.data
    assert b"Conversation" in response.data
    assert b"staff-message" in response.data
    assert response.data.count(b'<li class="messageThread__item ') == 5


def test_database_failure_returns_safe_error(client, monkeypatch):
    ticket_model = import_module(
        "student-Ethan Goldman.backend.models.ticket_model"
    )

    def raise_database_error(filters=None):
        raise sqlite3.DatabaseError("database unavailable")

    monkeypatch.setattr(ticket_model, "get_tickets", raise_database_error)

    response = client.get("/api/support-tickets")

    assert response.status_code == 500
    assert response.json == {"error": "Unable to retrieve support tickets."}
