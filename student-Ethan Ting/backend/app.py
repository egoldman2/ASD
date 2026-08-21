import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from flask import Flask, jsonify, request, session
from werkzeug.security import check_password_hash


app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SESSION_SECRET",
    "development-only-secret",
)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

DATABASE_API_URL = os.environ.get(
    "DATABASE_API_URL",
    "http://host.docker.internal:6003",
)


def find_user_by_email(email):
    query = urlencode({"email": email})
    url = f"{DATABASE_API_URL}/internal/users/by-email?{query}"

    try:
        with urlopen(url, timeout=5) as response:
            result = json.load(response)
            return result["user"]
    except HTTPError as error:
        if error.code == 404:
            return None
        raise


@app.get("/health")
def health():
    return jsonify({"status": "healthy"})


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}

    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not email or not password:
        return jsonify({
            "error": "Email and password are required."
        }), 400

    try:
        user = find_user_by_email(email)
    except (HTTPError, URLError):
        return jsonify({
            "error": "The user database is unavailable."
        }), 503

    valid_login = (
        user is not None
        and user["is_active"] == 1
        and check_password_hash(user["password_hash"], password)
    )

    if not valid_login:
        return jsonify({
            "error": "Invalid email or password."
        }), 401

    safe_user = {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "role": user["role"],
    }

    session.clear()
    session["user"] = safe_user

    return jsonify({
        "message": "Login successful.",
        "user": safe_user,
    })

@app.get("/api/session")
def current_session():
    user = session.get("user")

    if user is None:
        return jsonify({
            "authenticated": False
        }), 401

    return jsonify({
        "authenticated": True,
        "user": user,
    })


@app.post("/api/logout")
def logout():
    session.clear()

    return jsonify({
        "message": "Logout successful."
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6002, debug=True)