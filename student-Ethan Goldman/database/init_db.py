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
REQUIRED_TABLES = {"support_tickets"}


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
        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        should_seed = reset or not REQUIRED_TABLES.issubset(existing_tables)

        if reset:
            connection.execute("DROP TABLE IF EXISTS support_tickets")

        connection.executescript(schema)
        if should_seed:
            connection.executescript(seed)

        ticket_count = connection.execute(
            "SELECT COUNT(*) FROM support_tickets"
        ).fetchone()[0]
        connection.commit()

    return {"initialized": should_seed, "tickets": ticket_count, "path": resolved_path}


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
    print(f"Database {action}: {result['path']} ({result['tickets']} tickets)")


if __name__ == "__main__":
    main()
