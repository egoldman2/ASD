from importlib import import_module
import sqlite3


def test_json_deletes_ticket_and_its_messages(client, database_path):
    response = client.delete("/api/support-tickets/1011")

    assert response.status_code == 200
    assert response.json == {
        "message": "Support ticket deleted.",
        "ticket_id": 1011,
    }
    assert client.get("/api/support-tickets/1011").status_code == 404
    assert client.get("/api/support-tickets").json["count"] == 11

    with sqlite3.connect(database_path) as connection:
        message_count = connection.execute(
            "SELECT COUNT(*) FROM support_ticket_messages WHERE ticket_id = ?",
            (1011,),
        ).fetchone()[0]
    assert message_count == 0


def test_missing_and_repeated_ticket_deletes_return_not_found(client):
    missing = client.delete("/api/support-tickets/9999")
    first = client.delete("/api/support-tickets/1012")
    repeated = client.delete("/api/support-tickets/1012")

    assert missing.status_code == 404
    assert missing.json == {"error": "Support ticket not found."}
    assert first.status_code == 200
    assert repeated.status_code == 404
    assert repeated.json == {"error": "Support ticket not found."}


def test_staff_htmx_delete_renders_confirmation(client):
    response = client.delete(
        "/support-ui/staff/tickets/1011",
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert b"Ticket #1011 deleted" in response.data
    assert b"Back to queue" in response.data
    assert client.get("/api/support-tickets/1011").status_code == 404


def test_ticket_detail_requires_delete_confirmation(client):
    response = client.get(
        "/support-ui/staff/tickets/1011",
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert b'hx-delete="http://localhost:5000/support-ui/staff/tickets/1011"' in response.data
    assert b"hx-confirm=" in response.data
    assert b"cannot be undone" in response.data


def test_ticket_delete_database_failure_returns_safe_error(client, monkeypatch):
    ticket_model = import_module(
        "student-Ethan Goldman.backend.models.ticket_model"
    )

    def raise_database_error(*args):
        raise sqlite3.DatabaseError("database unavailable")

    monkeypatch.setattr(ticket_model, "delete_ticket", raise_database_error)
    response = client.delete("/api/support-tickets/1011")

    assert response.status_code == 500
    assert response.json == {"error": "Unable to delete the support ticket."}
