import os
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, request
from werkzeug.security import generate_password_hash

from init_db import initialise_database


app = Flask(__name__)

MAX_POINTS_ADJUSTMENT = 1_000_000


def clean_text(value):
    return value.strip() if isinstance(value, str) else ""


def valid_email(email):
    local_part, separator, domain = email.partition("@")
    return (
        bool(local_part and separator and domain)
        and "@" not in domain
        and not any(character.isspace() for character in email)
        and len(email) <= 254
    )

DATABASE_FOLDER = Path(__file__).resolve().parent
DATABASE_PATH = Path(
    os.environ.get("DATABASE_PATH", DATABASE_FOLDER / "users.db")
)

initialise_database()


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def loyalty_status(points_balance):
    if points_balance >= 1000:
        return {
            "tier": "Gold",
            "next_tier": None,
            "points_to_next_tier": 0,
        }

    if points_balance >= 500:
        return {
            "tier": "Silver",
            "next_tier": "Gold",
            "points_to_next_tier": 1000 - points_balance,
        }

    return {
        "tier": "Bronze",
        "next_tier": "Silver",
        "points_to_next_tier": 500 - points_balance,
    }


def public_loyalty_account(account):
    result = {
        "user_id": account["user_id"],
        "full_name": account["full_name"],
        "email": account["email"],
        "is_active": account["is_active"],
        "points_balance": account["points_balance"],
        "joined_at": account["joined_at"],
        "updated_at": account["updated_at"],
    }
    result.update(loyalty_status(account["points_balance"]))
    return result


def find_loyalty_account(user_id, connection=None):
    query = """
        SELECT
            loyalty_accounts.user_id,
            users.full_name,
            users.email,
            users.is_active,
            loyalty_accounts.points_balance,
            loyalty_accounts.joined_at,
            loyalty_accounts.updated_at
        FROM loyalty_accounts
        JOIN users ON users.id = loyalty_accounts.user_id
        WHERE loyalty_accounts.user_id = ? AND users.role = 'customer'
    """

    if connection is not None:
        return connection.execute(query, (user_id,)).fetchone()

    with get_connection() as database_connection:
        return database_connection.execute(query, (user_id,)).fetchone()


def public_user(user):
    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "role": user["role"],
        "is_active": user["is_active"],
        "created_at": user["created_at"],
    }


def find_user_by_id(user_id):
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT id, email, full_name, role, is_active, created_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()


@app.get("/health")
def health():
    return jsonify({"status": "healthy"})


@app.get("/internal/users/by-email")
def get_user_by_email():
    email = request.args.get("email", "").strip().lower()

    if not email:
        return jsonify({"error": "Email is required."}), 400

    with get_connection() as connection:
        user = connection.execute(
            """
            SELECT id, email, password_hash, full_name, role, is_active
            FROM users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()

    if user is None:
        return jsonify({"error": "User not found."}), 404

    return jsonify({"user": dict(user)})


@app.get("/internal/users")
def get_users():
    role = request.args.get("role", "").strip().lower()

    query = """
        SELECT id, email, full_name, role, is_active, created_at
        FROM users
    """
    parameters = ()

    if role:
        query += " WHERE role = ?"
        parameters = (role,)

    query += " ORDER BY full_name COLLATE NOCASE"

    with get_connection() as connection:
        users = connection.execute(query, parameters).fetchall()

    return jsonify({
        "count": len(users),
        "users": [public_user(user) for user in users],
    })


@app.get("/internal/users/<int:user_id>")
def get_user(user_id):
    user = find_user_by_id(user_id)

    if user is None:
        return jsonify({"error": "User not found."}), 404

    return jsonify({"user": public_user(user)})


@app.post("/internal/users")
def create_user():
    data = request.get_json(silent=True) or {}
    email = clean_text(data.get("email")).lower()
    full_name = clean_text(data.get("full_name"))
    supplied_password = data.get("password")
    password = supplied_password if isinstance(supplied_password, str) else ""

    if not valid_email(email):
        return jsonify({"error": "A valid email is required."}), 400

    if not full_name:
        return jsonify({"error": "Full name is required."}), 400

    if len(full_name) > 100:
        return jsonify({
            "error": "Full name must be 100 characters or fewer."
        }), 400

    if len(password) < 8:
        return jsonify({
            "error": "Password must contain at least 8 characters."
        }), 400

    try:
        with get_connection() as connection:
            connection.execute("BEGIN")
            cursor = connection.execute(
                """
                INSERT INTO users
                    (email, password_hash, full_name, role, is_active)
                VALUES (?, ?, ?, 'customer', 1)
                """,
                (
                    email,
                    generate_password_hash(password),
                    full_name,
                ),
            )
            user_id = cursor.lastrowid
            connection.execute(
                """
                INSERT INTO loyalty_accounts (user_id, points_balance)
                VALUES (?, 0)
                """,
                (user_id,),
            )
    except sqlite3.IntegrityError:
        return jsonify({"error": "That email is already in use."}), 409

    return jsonify({"user": public_user(find_user_by_id(user_id))}), 201


@app.get("/internal/loyalty")
def get_loyalty_accounts():
    with get_connection() as connection:
        accounts = connection.execute(
            """
            SELECT
                loyalty_accounts.user_id,
                users.full_name,
                users.email,
                users.is_active,
                loyalty_accounts.points_balance,
                loyalty_accounts.joined_at,
                loyalty_accounts.updated_at
            FROM loyalty_accounts
            JOIN users ON users.id = loyalty_accounts.user_id
            WHERE users.role = 'customer'
            ORDER BY users.full_name COLLATE NOCASE
            """
        ).fetchall()

    return jsonify({
        "count": len(accounts),
        "loyalty_accounts": [
            public_loyalty_account(account) for account in accounts
        ],
    })


@app.get("/internal/loyalty/<int:user_id>")
def get_loyalty_account(user_id):
    account = find_loyalty_account(user_id)

    if account is None:
        return jsonify({"error": "Loyalty account not found."}), 404

    return jsonify({"loyalty": public_loyalty_account(account)})


@app.get("/internal/loyalty/<int:user_id>/transactions")
def get_loyalty_transactions(user_id):
    account = find_loyalty_account(user_id)

    if account is None:
        return jsonify({"error": "Loyalty account not found."}), 404

    requested_limit = request.args.get("limit", "20")
    try:
        limit = max(1, min(int(requested_limit), 100))
    except ValueError:
        return jsonify({"error": "Transaction limit must be a number."}), 400

    with get_connection() as connection:
        transactions = connection.execute(
            """
            SELECT
                loyalty_transactions.id,
                loyalty_transactions.user_id,
                loyalty_transactions.points_change,
                loyalty_transactions.reason,
                loyalty_transactions.created_by_admin_id,
                loyalty_transactions.created_at,
                administrators.full_name AS created_by_admin_name
            FROM loyalty_transactions
            LEFT JOIN users AS administrators
                ON administrators.id = loyalty_transactions.created_by_admin_id
            WHERE loyalty_transactions.user_id = ?
            ORDER BY loyalty_transactions.created_at DESC,
                     loyalty_transactions.id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()

    return jsonify({
        "count": len(transactions),
        "transactions": [dict(transaction) for transaction in transactions],
    })


@app.post("/internal/loyalty/<int:user_id>/adjustments")
def adjust_loyalty_points(user_id):
    data = request.get_json(silent=True) or {}
    points_change = data.get("points_change")
    supplied_reason = data.get("reason")
    reason = supplied_reason.strip() if isinstance(supplied_reason, str) else ""
    created_by_admin_id = data.get("created_by_admin_id")

    if isinstance(points_change, bool) or not isinstance(points_change, int):
        return jsonify({"error": "Points adjustment must be a whole number."}), 400

    if points_change == 0:
        return jsonify({"error": "Points adjustment cannot be zero."}), 400

    if abs(points_change) > MAX_POINTS_ADJUSTMENT:
        return jsonify({
            "error": "A single adjustment cannot exceed 1,000,000 points."
        }), 400

    if not reason:
        return jsonify({"error": "A reason is required."}), 400

    if len(reason) > 200:
        return jsonify({"error": "The reason must be 200 characters or fewer."}), 400

    try:
        with get_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            account = find_loyalty_account(user_id, connection)

            if account is None:
                return jsonify({"error": "Loyalty account not found."}), 404

            new_balance = account["points_balance"] + points_change
            if new_balance < 0:
                return jsonify({
                    "error": "Points balance cannot go below zero."
                }), 400

            if created_by_admin_id is not None:
                administrator = connection.execute(
                    """
                    SELECT id
                    FROM users
                    WHERE id = ? AND role = 'admin' AND is_active = 1
                    """,
                    (created_by_admin_id,),
                ).fetchone()
                if administrator is None:
                    return jsonify({"error": "Administrator not found."}), 400

            connection.execute(
                """
                UPDATE loyalty_accounts
                SET points_balance = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (new_balance, user_id),
            )
            cursor = connection.execute(
                """
                INSERT INTO loyalty_transactions
                    (user_id, points_change, reason, created_by_admin_id)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, points_change, reason, created_by_admin_id),
            )
            transaction_id = cursor.lastrowid
            updated_account = find_loyalty_account(user_id, connection)
            transaction = connection.execute(
                """
                SELECT
                    loyalty_transactions.id,
                    loyalty_transactions.user_id,
                    loyalty_transactions.points_change,
                    loyalty_transactions.reason,
                    loyalty_transactions.created_by_admin_id,
                    loyalty_transactions.created_at,
                    administrators.full_name AS created_by_admin_name
                FROM loyalty_transactions
                LEFT JOIN users AS administrators
                    ON administrators.id = loyalty_transactions.created_by_admin_id
                WHERE loyalty_transactions.id = ?
                """,
                (transaction_id,),
            ).fetchone()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Unable to save the points adjustment."}), 400

    return jsonify({
        "message": "Loyalty points updated.",
        "loyalty": public_loyalty_account(updated_account),
        "transaction": dict(transaction),
    }), 201


@app.put("/internal/users/<int:user_id>")
def update_user(user_id):
    data = request.get_json(silent=True) or {}
    updates = []
    parameters = []

    if "full_name" in data:
        full_name = clean_text(data["full_name"])
        if not full_name:
            return jsonify({"error": "Full name is required."}), 400
        if len(full_name) > 100:
            return jsonify({
                "error": "Full name must be 100 characters or fewer."
            }), 400
        updates.append("full_name = ?")
        parameters.append(full_name)

    if "email" in data:
        email = clean_text(data["email"]).lower()
        if not valid_email(email):
            return jsonify({"error": "A valid email is required."}), 400
        updates.append("email = ?")
        parameters.append(email)

    if "is_active" in data:
        supplied_status = data["is_active"]
        if isinstance(supplied_status, bool):
            is_active = int(supplied_status)
        elif supplied_status in (0, 1):
            is_active = supplied_status
        else:
            return jsonify({
                "error": "Account status must be active or disabled."
            }), 400
        updates.append("is_active = ?")
        parameters.append(is_active)

    if not updates:
        return jsonify({"error": "No valid changes were supplied."}), 400

    parameters.append(user_id)

    try:
        with get_connection() as connection:
            cursor = connection.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
                parameters,
            )
    except sqlite3.IntegrityError:
        return jsonify({"error": "That email is already in use."}), 409

    if cursor.rowcount == 0:
        return jsonify({"error": "User not found."}), 404

    return jsonify({"user": public_user(find_user_by_id(user_id))})


@app.delete("/internal/users/<int:user_id>")
def deactivate_user(user_id):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE users
            SET is_active = 0
            WHERE id = ? AND role = 'customer'
            """,
            (user_id,),
        )

    if cursor.rowcount == 0:
        return jsonify({"error": "Customer not found."}), 404

    return jsonify({
        "message": "Customer account disabled.",
        "user": public_user(find_user_by_id(user_id)),
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=6003,
        debug=os.environ.get("APP_DEBUG", "false").lower() == "true",
        use_reloader=False,
    )
