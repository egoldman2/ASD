import sqlite3
from pathlib import Path

from werkzeug.security import generate_password_hash


DATABASE_FOLDER = Path(__file__).resolve().parent
DATABASE_PATH = DATABASE_FOLDER / "users.db"
SCHEMA_PATH = DATABASE_FOLDER / "schema.sql"

USERS = [
    ("admin@asd.local", "AdminPass!2026", "Marketplace Administrator", "admin"),
    ("customer@asd.local", "CustomerPass!2026", "Demo Customer", "customer"),
    ("ava@example.test", "CustomerPass!2026", "Ava Chen", "customer"),
    ("liam@example.test", "CustomerPass!2026", "Liam Smith", "customer"),
    ("mia@example.test", "CustomerPass!2026", "Mia Wilson", "customer"),
    ("noah@example.test", "CustomerPass!2026", "Noah Brown", "customer"),
    ("isla@example.test", "CustomerPass!2026", "Isla Taylor", "customer"),
    ("jack@example.test", "CustomerPass!2026", "Jack Anderson", "customer"),
    ("zoe@example.test", "CustomerPass!2026", "Zoe Thomas", "customer"),
    ("leo@example.test", "CustomerPass!2026", "Leo Martin", "customer"),
]


def initialise_database():
    with sqlite3.connect(DATABASE_PATH) as connection:
        schema = SCHEMA_PATH.read_text()
        connection.executescript(schema)

        for email, password, full_name, role in USERS:
            connection.execute(
                """
                INSERT OR IGNORE INTO users
                    (email, password_hash, full_name, role)
                VALUES (?, ?, ?, ?)
                """,
                (
                    email,
                    generate_password_hash(password),
                    full_name,
                    role,
                ),
            )

        user_count = connection.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

    print(f"Database ready with {user_count} users.")


if __name__ == "__main__":
    initialise_database()
