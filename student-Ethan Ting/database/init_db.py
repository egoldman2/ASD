import os
import sqlite3
from pathlib import Path

from werkzeug.security import generate_password_hash


DATABASE_FOLDER = Path(__file__).resolve().parent
DATABASE_PATH = Path(
    os.environ.get("DATABASE_PATH", DATABASE_FOLDER / "users.db")
)
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
    ("sophia@example.test", "CustomerPass!2026", "Sophia Lee", "customer"),
]

LOYALTY_STARTING_POINTS = {
    "customer@asd.local": 120,
    "ava@example.test": 540,
    "liam@example.test": 280,
    "mia@example.test": 1020,
    "noah@example.test": 760,
    "isla@example.test": 430,
    "jack@example.test": 890,
    "zoe@example.test": 1350,
    "leo@example.test": 610,
    "sophia@example.test": 250,
}


def initialise_database():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
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

        for email, starting_points in LOYALTY_STARTING_POINTS.items():
            user = connection.execute(
                "SELECT id FROM users WHERE email = ? AND role = 'customer'",
                (email,),
            ).fetchone()

            if user is None:
                continue

            user_id = user[0]
            connection.execute(
                """
                INSERT OR IGNORE INTO loyalty_accounts
                    (user_id, points_balance)
                VALUES (?, ?)
                """,
                (user_id, starting_points),
            )

            transaction_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM loyalty_transactions
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()[0]

            if transaction_count == 0 and starting_points > 0:
                connection.execute(
                    """
                    INSERT INTO loyalty_transactions
                        (user_id, points_change, reason)
                    VALUES (?, ?, 'Initial loyalty points')
                    """,
                    (user_id, starting_points),
                )

        connection.execute(
            """
            INSERT OR IGNORE INTO loyalty_accounts (user_id, points_balance)
            SELECT id, 0
            FROM users
            WHERE role = 'customer'
            """
        )

        user_count = connection.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        loyalty_count = connection.execute(
            "SELECT COUNT(*) FROM loyalty_accounts"
        ).fetchone()[0]

        transaction_count = connection.execute(
            "SELECT COUNT(*) FROM loyalty_transactions"
        ).fetchone()[0]

    print(
        "Database ready with "
        f"{user_count} users, {loyalty_count} loyalty accounts, "
        f"and {transaction_count} loyalty transactions."
    )


if __name__ == "__main__":
    initialise_database()
