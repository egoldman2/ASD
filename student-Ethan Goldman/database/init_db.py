"""Initialise the Customer Support SQLite database from schema and seed files."""

import argparse
from contextlib import closing
import os
from pathlib import Path
import sqlite3


DATABASE_DIRECTORY = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = DATABASE_DIRECTORY / "support_tickets.db"
SCHEMA_PATH = DATABASE_DIRECTORY / "schema.sql"
SEED_PATH = DATABASE_DIRECTORY / "seed.sql"
REQUIRED_TABLES = {"support_tickets", "support_ticket_messages"}


def _table_names(connection):
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }


def _migrate_legacy_messages(connection):
    """Move the former single-message columns into the message history table."""
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(support_tickets)")
    }
    if "message" not in columns:
        return False

    connection.execute(
        """
        INSERT INTO support_ticket_messages (
            ticket_id, sender_role, author_name, message, created_at
        )
        SELECT id, 'customer', customer_name, message, created_at
        FROM support_tickets AS ticket
        WHERE NOT EXISTS (
            SELECT 1
            FROM support_ticket_messages AS existing
            WHERE existing.ticket_id = ticket.id
        )
        """
    )

    if "staff_response" in columns:
        connection.execute(
            """
            INSERT INTO support_ticket_messages (
                ticket_id, sender_role, author_name, message, created_at
            )
            SELECT
                id,
                'staff',
                COALESCE(assigned_to, 'Support staff'),
                staff_response,
                COALESCE(responded_at, updated_at)
            FROM support_tickets
            WHERE staff_response IS NOT NULL
              AND LENGTH(TRIM(staff_response)) > 0
            """
        )

    for column in ("responded_at", "staff_response", "message"):
        if column in columns:
            connection.execute(f"ALTER TABLE support_tickets DROP COLUMN {column}")

    return True


def initialize_database(database_path=None, reset=False):
    """Create or reset the support database and return its ticket count."""
    resolved_path = Path(
        database_path
        or os.getenv("SUPPORT_DATABASE_PATH", DEFAULT_DATABASE_PATH)
    )
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    seed = SEED_PATH.read_text(encoding="utf-8")

    with closing(sqlite3.connect(resolved_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        existing_tables = _table_names(connection)
        should_seed = reset or "support_tickets" not in existing_tables

        if reset:
            connection.execute("DROP TABLE IF EXISTS support_ticket_messages")
            connection.execute("DROP TABLE IF EXISTS support_tickets")

        connection.executescript(schema)
        if should_seed:
            connection.executescript(seed)

        migrated = False if should_seed else _migrate_legacy_messages(connection)

        ticket_count = connection.execute(
            "SELECT COUNT(*) FROM support_tickets"
        ).fetchone()[0]
        message_count = connection.execute(
            "SELECT COUNT(*) FROM support_ticket_messages"
        ).fetchone()[0]
        connection.commit()

    initialized = should_seed or migrated or not REQUIRED_TABLES.issubset(existing_tables)
    return {
        "initialized": initialized,
        "tickets": ticket_count,
        "messages": message_count,
        "path": resolved_path,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Create or reset the Customer Support SQLite database."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Replace existing support tickets with the records from seed.sql.",
    )
    arguments = parser.parse_args()

    result = initialize_database(reset=arguments.reset)
    action = "initialized" if result["initialized"] else "already initialized"
    print(
        f"Database {action}: {result['path']} "
        f"({result['tickets']} tickets, {result['messages']} messages)"
    )


if __name__ == "__main__":
    main()
