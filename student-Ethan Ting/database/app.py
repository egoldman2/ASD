import os
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, request
from werkzeug.security import generate_password_hash

from init_db import initialise_database


app = Flask(__name__)

DATABASE_FOLDER = Path(__file__).resolve().parent
DATABASE_PATH = Path(
    os.environ.get("DATABASE_PATH", DATABASE_FOLDER / "users.db")
)

initialise_database()


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


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
    email = str(data.get("email", "")).strip().lower()
    full_name = str(data.get("full_name", "")).strip()
    password = str(data.get("password", ""))

    if not email or "@" not in email:
        return jsonify({"error": "A valid email is required."}), 400

    if not full_name:
        return jsonify({"error": "Full name is required."}), 400

    if len(password) < 8:
        return jsonify({
            "error": "Password must contain at least 8 characters."
        }), 400

    try:
        with get_connection() as connection:
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
    except sqlite3.IntegrityError:
        return jsonify({"error": "That email is already in use."}), 409

    return jsonify({"user": public_user(find_user_by_id(user_id))}), 201


@app.put("/internal/users/<int:user_id>")
def update_user(user_id):
    data = request.get_json(silent=True) or {}
    updates = []
    parameters = []

    if "full_name" in data:
        full_name = str(data["full_name"]).strip()
        if not full_name:
            return jsonify({"error": "Full name is required."}), 400
        updates.append("full_name = ?")
        parameters.append(full_name)

    if "email" in data:
        email = str(data["email"]).strip().lower()
        if not email or "@" not in email:
            return jsonify({"error": "A valid email is required."}), 400
        updates.append("email = ?")
        parameters.append(email)

    if "is_active" in data:
        is_active = 1 if bool(data["is_active"]) else 0
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
