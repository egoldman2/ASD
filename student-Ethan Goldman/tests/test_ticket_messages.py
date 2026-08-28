from importlib import import_module
import sqlite3


def test_json_adds_multiple_customer_and_staff_messages(client):
    customer_response = client.post(
        "/api/support-tickets/1012/messages",
        json={"sender_role": "customer", "message": "Here is another customer update."},
    )
    staff_response = client.post(
        "/api/support-tickets/1012/messages",
        json={"sender_role": "staff", "message": "Thanks, the team is checking this now."},
    )

    assert customer_response.status_code == 201
    assert customer_response.json["message"]["sender_role"] == "customer"
    assert staff_response.status_code == 201
    assert staff_response.json["message"]["sender_role"] == "staff"

    ticket_response = client.get("/api/support-tickets/1012")
    assert ticket_response.json["ticket"]["message_count"] == 3
    assert [
        message["message"] for message in ticket_response.json["ticket"]["messages"]
    ][-2:] == [
        "Here is another customer update.",
        "Thanks, the team is checking this now.",
    ]


def test_message_updates_ticket_timestamp_and_queue_count(client):
    before = client.get("/api/support-tickets/1012").json["ticket"]["updated_at"]

    response = client.post(
        "/api/support-tickets/1012/messages",
        json={"sender_role": "staff", "message": "A new staff response."},
    )

    ticket = client.get("/api/support-tickets/1012").json["ticket"]
    queue_ticket = client.get("/api/support-tickets").json["tickets"][0]
    assert response.status_code == 201
    assert ticket["updated_at"] > before
    assert queue_ticket["id"] == 1012
    assert queue_ticket["message_count"] == 2


def test_json_message_validation_and_missing_ticket(client):
    invalid_role = client.post(
        "/api/support-tickets/1011/messages",
        json={"sender_role": "system", "message": "Not permitted"},
    )
    empty_message = client.post(
        "/api/support-tickets/1011/messages",
        json={"sender_role": "staff", "message": "   "},
    )
    missing_ticket = client.post(
        "/api/support-tickets/9999/messages",
        json={"sender_role": "staff", "message": "Ticket does not exist"},
    )

    assert invalid_role.status_code == 400
    assert empty_message.status_code == 400
    assert missing_ticket.status_code == 404


def test_staff_htmx_reply_renders_full_updated_thread(client):
    response = client.post(
        "/support-ui/staff/tickets/1011/messages",
        data={"message": "This is a second staff follow-up."},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 201
    assert b"Reply added to the conversation" in response.data
    assert b"This is a second staff follow-up" in response.data
    assert response.data.count(b'<li class="messageThread__item ') == 6


def test_customer_can_view_and_reply_to_verified_ticket(client):
    lookup = client.get(
        "/support-ui/customer/tickets",
        query_string={"ticket_id": 1011, "customer_email": "OLIVER.JONES@example.com"},
        headers={"HX-Request": "true"},
    )
    reply = client.post(
        "/support-ui/customer/tickets/1011/messages",
        data={
            "customer_email": "oliver.jones@example.com",
            "message": "One more update from the customer.",
        },
        headers={"HX-Request": "true"},
    )

    assert lookup.status_code == 200
    assert b"Parcel marked delivered but not received" in lookup.data
    assert b"priority" not in lookup.data.lower()
    assert reply.status_code == 201
    assert b"Your reply was added" in reply.data
    assert b"One more update from the customer" in reply.data


def test_customer_email_must_match_ticket(client):
    response = client.get(
        "/support-ui/customer/tickets",
        query_string={"ticket_id": 1011, "customer_email": "wrong@example.com"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert b"Ticket details could not be verified" in response.data
    assert b"Oliver Jones" not in response.data


def test_message_database_failure_returns_safe_error(client, monkeypatch):
    ticket_model = import_module(
        "student-Ethan Goldman.backend.models.ticket_model"
    )

    def raise_database_error(*args):
        raise sqlite3.DatabaseError("database unavailable")

    monkeypatch.setattr(ticket_model, "create_ticket_message", raise_database_error)
    response = client.post(
        "/api/support-tickets/1011/messages",
        json={"sender_role": "staff", "message": "This will fail safely."},
    )

    assert response.status_code == 500
    assert response.json == {"error": "Unable to add the ticket message."}
