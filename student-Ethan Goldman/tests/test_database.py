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
    assert result["messages"] == 23


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
                    customer_name, customer_email, subject, category,
                    priority, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Test Customer",
                    "test@example.com",
                    "Test ticket subject",
                    "other",
                    "low",
                    "closed",
                    "2026-08-26T00:00:00Z",
                    "2026-08-26T00:00:00Z",
                ),
            )


def test_message_schema_rejects_invalid_sender_role(database_path):
    with sqlite3.connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO support_ticket_messages (
                    ticket_id, sender_role, author_name, message, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (1011, "robot", "Test Robot", "Invalid role", "2026-08-26T00:00:00Z"),
            )


def test_deleting_ticket_cascades_to_its_messages(database_path):
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("DELETE FROM support_tickets WHERE id = ?", (1011,))
        remaining = connection.execute(
            "SELECT COUNT(*) FROM support_ticket_messages WHERE ticket_id = ?",
            (1011,),
        ).fetchone()[0]

    assert remaining == 0


def test_initializer_migrates_legacy_message_columns(tmp_path):
    database_path = tmp_path / "legacy_support.db"
    init_db = import_module("student-Ethan Goldman.database.init_db")
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE support_tickets (
                id INTEGER PRIMARY KEY,
                customer_name TEXT NOT NULL,
                customer_email TEXT NOT NULL,
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                assigned_to TEXT,
                staff_response TEXT,
                responded_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO support_tickets VALUES (
                1, 'Legacy Customer', 'legacy@example.com', 'Legacy ticket',
                'Opening customer message', 'other', 'low', 'pending',
                'Alex Morgan', 'Legacy staff reply', '2026-08-26T01:00:00Z',
                '2026-08-26T00:00:00Z', '2026-08-26T01:00:00Z'
            );
            """
        )

    result = init_db.initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        ticket_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(support_tickets)")
        }
        messages = connection.execute(
            """
            SELECT sender_role, message
            FROM support_ticket_messages
            WHERE ticket_id = 1
            ORDER BY datetime(created_at), id
            """
        ).fetchall()

    assert result["initialized"] is True
    assert "message" not in ticket_columns
    assert messages == [
        ("customer", "Opening customer message"),
        ("staff", "Legacy staff reply"),
    ]


def test_model_connection_returns_row_objects(database_path):
    database = import_module("student-Ethan Goldman.backend.models.database")

    with database.get_database_connection() as connection:
        ticket = connection.execute(
            "SELECT id, subject FROM support_tickets WHERE id = ?", (1011,)
        ).fetchone()

    assert ticket["id"] == 1011
    assert ticket["subject"] == "Parcel marked delivered but not received"
