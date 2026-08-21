import sqlite3
from pathlib import Path

from flask import Flask, jsonify, request

from init_db import initialise_database


app = Flask(__name__)

DATABASE_PATH = Path(__file__).resolve().parent / "users.db"

initialise_database()


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6003, debug=True)
