import json
import os
from functools import wraps
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as URLRequest
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
app.config["SESSION_COOKIE_NAME"] = "ethan_session"

DATABASE_API_URL = os.environ.get(
    "DATABASE_API_URL",
    "http://host.docker.internal:6003",
)

ALLOWED_ORIGINS = {
    "http://localhost:8000",
    "http://localhost:8003",
}


def database_request(path, method="GET", payload=None):
    data = None
    headers = {}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request_to_database = URLRequest(
        f"{DATABASE_API_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )

    with urlopen(request_to_database, timeout=5) as response:
        return json.load(response)


def find_user_by_email(email):
    query = urlencode({"email": email})

    try:
        result = database_request(f"/internal/users/by-email?{query}")
        return result["user"]
    except HTTPError as error:
        if error.code == 404:
            return None
        raise


def database_error_response(error):
    if isinstance(error, HTTPError):
        try:
            payload = json.loads(error.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {"error": "The database rejected the request."}
        return jsonify(payload), error.code

    return jsonify({"error": "The user database is unavailable."}), 503


def login_required(function):
    @wraps(function)
    def protected_function(*args, **kwargs):
        if session.get("user") is None:
            return jsonify({"error": "You must sign in."}), 401
        return function(*args, **kwargs)

    return protected_function


def admin_required(function):
    @wraps(function)
    def protected_function(*args, **kwargs):
        user = session.get("user")

        if user is None:
            return jsonify({"error": "You must sign in."}), 401

        if user.get("role") != "admin":
            return jsonify({
                "error": "Administrator access required."
            }), 403

        return function(*args, **kwargs)

    return protected_function


@app.after_request
def allow_frontend_requests(response):
    origin = request.headers.get("Origin")

    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"

    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = (
        "GET, POST, PUT, DELETE, OPTIONS"
    )
    return response


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


@app.post("/api/register")
def register():
    data = request.get_json(silent=True) or {}

    full_name = str(data.get("full_name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    password_confirmation = str(data.get("password_confirmation", ""))

    if not full_name:
        return jsonify({"error": "Full name is required."}), 400

    if not email or "@" not in email:
        return jsonify({"error": "A valid email is required."}), 400

    if len(password) < 8:
        return jsonify({
            "error": "Password must contain at least 8 characters."
        }), 400

    if password != password_confirmation:
        return jsonify({"error": "Passwords do not match."}), 400

    try:
        result = database_request(
            "/internal/users",
            method="POST",
            payload={
                "full_name": full_name,
                "email": email,
                "password": password,
            },
        )
    except (HTTPError, URLError) as error:
        return database_error_response(error)

    created_user = result["user"]
    safe_user = {
        "id": created_user["id"],
        "email": created_user["email"],
        "full_name": created_user["full_name"],
        "role": created_user["role"],
    }

    session.clear()
    session["user"] = safe_user

    return jsonify({
        "message": "Account created successfully.",
        "user": safe_user,
    }), 201


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


@app.get("/api/profile")
@login_required
def get_profile():
    user_id = session["user"]["id"]

    try:
        result = database_request(f"/internal/users/{user_id}")
    except (HTTPError, URLError) as error:
        return database_error_response(error)

    return jsonify(result)


@app.put("/api/profile")
@login_required
def update_profile():
    data = request.get_json(silent=True) or {}
    allowed_changes = {
        key: data[key]
        for key in ("full_name", "email")
        if key in data
    }
    user_id = session["user"]["id"]

    try:
        result = database_request(
            f"/internal/users/{user_id}",
            method="PUT",
            payload=allowed_changes,
        )
    except (HTTPError, URLError) as error:
        return database_error_response(error)

    updated_user = result["user"]
    session["user"] = {
        "id": updated_user["id"],
        "email": updated_user["email"],
        "full_name": updated_user["full_name"],
        "role": updated_user["role"],
    }

    return jsonify({"user": session["user"]})


@app.get("/api/admin/customers")
@admin_required
def get_customers():
    try:
        result = database_request("/internal/users?role=customer")
    except (HTTPError, URLError) as error:
        return database_error_response(error)

    return jsonify(result)


@app.post("/api/admin/customers")
@admin_required
def create_customer():
    data = request.get_json(silent=True) or {}

    try:
        result = database_request(
            "/internal/users",
            method="POST",
            payload=data,
        )
    except (HTTPError, URLError) as error:
        return database_error_response(error)

    return jsonify(result), 201


@app.put("/api/admin/customers/<int:user_id>")
@admin_required
def update_customer(user_id):
    data = request.get_json(silent=True) or {}
    allowed_changes = {
        key: data[key]
        for key in ("full_name", "email", "is_active")
        if key in data
    }

    try:
        result = database_request(
            f"/internal/users/{user_id}",
            method="PUT",
            payload=allowed_changes,
        )
    except (HTTPError, URLError) as error:
        return database_error_response(error)

    return jsonify(result)


@app.delete("/api/admin/customers/<int:user_id>")
@admin_required
def deactivate_customer(user_id):
    try:
        result = database_request(
            f"/internal/users/{user_id}",
            method="DELETE",
        )
    except (HTTPError, URLError) as error:
        return database_error_response(error)

    return jsonify(result)


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=6002,
        debug=os.environ.get("APP_DEBUG", "false").lower() == "true",
        use_reloader=False,
    )
