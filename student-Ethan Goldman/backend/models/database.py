"""SQLite connection helpers for Customer Support."""

import os
from pathlib import Path
import sqlite3


DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[2] / "database" / "support_tickets.db"
DATABASE_PATH = Path(os.getenv("SUPPORT_DATABASE_PATH", DEFAULT_DATABASE_PATH))


def get_database_connection(database_path=None):
    """Return a row-based SQLite connection with foreign keys enabled."""
    path = Path(database_path or DATABASE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
