"""Checks against Ethan's genuine SQLite initialization and migration code."""

from importlib import import_module
from pathlib import Path
import sqlite3


def test_real_database_seed_is_idempotent_and_owner_scoped(tmp_path):
    init_db = import_module("student-Ethan Goldman.database_service.init_db")
    database = import_module("student-Ethan Goldman.database_service.database")
    path = Path(tmp_path) / "support.db"
    first = init_db.initialize_database(path)
    second = init_db.initialize_database(path)
    assert first["initialized"] is True
    assert second["initialized"] is False
    assert second["tickets"] == first["tickets"]
    assert second["messages"] == first["messages"]
    assert first["tickets"] >= 10
    assert first["messages"] >= 10

    own, _counts = database.get_tickets(
        {"owner_user_id": "2"}, database_path=path
    )
    assert [ticket["id"] for ticket in own] == [2002]
    assert database.get_ticket(2003, database_path=path, owner_user_id="2") is None

    connection = sqlite3.connect(path)
    connection.execute(
        """UPDATE support_tickets
           SET customer_user_id = 'legacy-ticket:2002',
               customer_name_snapshot = 'Legacy customer 2002',
               customer_email_snapshot = 'legacy-ticket-2002@invalid.local'
           WHERE id = 2002"""
    )
    connection.commit()
    connection.close()
    repaired = init_db.initialize_database(path)
    assert repaired["initialized"] is True
    connection = sqlite3.connect(path)
    restored = connection.execute(
        """SELECT customer_user_id, customer_name_snapshot,
                  customer_email_snapshot
           FROM support_tickets WHERE id = 2002"""
    ).fetchone()
    connection.close()
    assert restored == ("2", "Demo Customer", "customer@asd.local")


def test_real_legacy_database_migrates_once_without_losing_data(tmp_path):
    init_db = import_module("student-Ethan Goldman.database_service.init_db")
    path = Path(tmp_path) / "legacy.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE support_tickets (
            id INTEGER PRIMARY KEY, customer_name TEXT, customer_email TEXT,
            subject TEXT, category TEXT, priority TEXT, status TEXT,
            assigned_to TEXT, message TEXT, created_at TEXT, updated_at TEXT
        );
        INSERT INTO support_tickets VALUES
          (77, 'Legacy User', 'legacy@example.com', 'Old support request',
           'general', 'medium', 'open', 'Alex Morgan', 'Legacy body',
           '2026-08-01T10:00:00Z', '2026-08-01T10:00:00Z');
        """
    )
    connection.commit()
    connection.close()

    first = init_db.initialize_database(path)
    second = init_db.initialize_database(path)
    assert first["initialized"] is True
    assert second["initialized"] is False
    assert second["tickets"] == first["tickets"]
    assert second["messages"] == first["messages"]
    connection = sqlite3.connect(path)
    row = connection.execute(
        "SELECT customer_user_id, category, status FROM support_tickets WHERE id = 77"
    ).fetchone()
    message = connection.execute(
        "SELECT sender_role, message FROM support_ticket_messages WHERE ticket_id = 77"
    ).fetchone()
    connection.close()
    assert row == ("legacy-email:legacy@example.com", "other", "open")
    assert message == ("customer", "Legacy body")


def test_real_constraint_rebuild_preserves_modern_verified_identity(tmp_path):
    init_db = import_module("student-Ethan Goldman.database_service.init_db")
    path = Path(tmp_path) / "modern-old-constraint.db"
    schema = init_db.SCHEMA_PATH.read_text(encoding="utf-8").replace(
        "LENGTH(TRIM(triage_applied_by)) BETWEEN 1 AND 128",
        "LENGTH(TRIM(triage_applied_by)) BETWEEN 2 AND 100",
    )
    connection = sqlite3.connect(path)
    connection.executescript(schema)
    connection.execute(
        """INSERT INTO support_tickets (
               id, customer_user_id, customer_name_snapshot,
               customer_email_snapshot, subject, category, priority, status,
               assigned_to, triage_applied_by, created_at, updated_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            9000,
            "42",
            "Verified Customer",
            "verified@example.test",
            "Preserve verified identity",
            "account",
            "medium",
            "open",
            None,
            None,
            "2026-08-31T00:00:00Z",
            "2026-08-31T00:00:00Z",
        ),
    )
    connection.execute(
        """INSERT INTO support_ticket_messages
               (ticket_id, sender_role, author_name, message, created_at)
           VALUES (9000, 'customer', 'Verified Customer',
                   'Keep this real message.', '2026-08-31T00:00:00Z')"""
    )
    connection.commit()
    connection.close()

    result = init_db.initialize_database(path)
    assert result["initialized"] is True
    connection = sqlite3.connect(path)
    ticket = connection.execute(
        """SELECT customer_user_id, customer_name_snapshot,
                  customer_email_snapshot
           FROM support_tickets WHERE id = 9000"""
    ).fetchone()
    message = connection.execute(
        "SELECT author_name, message FROM support_ticket_messages WHERE ticket_id = 9000"
    ).fetchone()
    connection.close()
    assert ticket == ("42", "Verified Customer", "verified@example.test")
    assert message == ("Verified Customer", "Keep this real message.")
