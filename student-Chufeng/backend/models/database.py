from pathlib import Path
import sqlite3


DATABASE_PATH = Path(__file__).resolve().parents[2] / "database" / "products.db"


def get_database_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
