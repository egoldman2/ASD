from importlib import import_module
import sqlite3

import pytest


def test_initialization_creates_seeded_ticket_database(tmp_path):
    database_path = tmp_path / "nested" / "support_tickets.db"
    init_db = import_module("student-Ethan Goldman.database.init_db")

    result = init_db.initialize_database(database_path)

    assert database_path.exists()
    assert result["initialized"] is True
    assert result["tickets"] == 12


def test_initialization_is_idempotent(database_path):
    init_db = import_module("student-Ethan Goldman.database.init_db")

    result = init_db.initialize_database(database_path)

    assert result["initialized"] is False
    assert result["tickets"] == 12


def test_reset_restores_all_seeded_tickets(database_path):
    init_db = import_module("student-Ethan Goldman.database.init_db")

    with sqlite3.connect(database_path) as connection:
        connection.execute("DELETE FROM support_tickets WHERE id = 1012")
        connection.commit()

    result = init_db.initialize_database(database_path, reset=True)

    assert result["initialized"] is True
    assert result["tickets"] == 12


def test_seeded_tickets_cover_all_queue_statuses(database_path):
    with sqlite3.connect(database_path) as connection:
        status_counts = dict(
            connection.execute(
                "SELECT status, COUNT(*) FROM support_tickets GROUP BY status"
            ).fetchall()
        )

    assert status_counts == {"open": 5, "pending": 3, "solved": 4}


def test_schema_rejects_invalid_ticket_status(database_path):
    with sqlite3.connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO support_tickets (
                    customer_name, customer_email, subject, message, category,
                    priority, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Test Customer",
                    "test@example.com",
                    "Test ticket subject",
                    "This is a valid test message for the ticket.",
                    "other",
                    "low",
                    "closed",
                    "2026-08-26T00:00:00Z",
                    "2026-08-26T00:00:00Z",
                ),
            )


def test_model_connection_returns_row_objects(database_path):
    database = import_module("student-Ethan Goldman.backend.models.database")

    with database.get_database_connection() as connection:
        ticket = connection.execute(
            "SELECT id, subject FROM support_tickets WHERE id = ?", (1011,)
        ).fetchone()

    assert ticket["id"] == 1011
    assert ticket["subject"] == "Parcel marked delivered but not received"
