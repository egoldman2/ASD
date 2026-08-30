import json
import os
from functools import wraps
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as URLRequest
from urllib.request import urlopen

from flask import Flask, g, jsonify, request, session
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
    "http://localhost:8001",
    "http://localhost:8002",
    "http://localhost:8003",
    "http://localhost:8004",
    "http://localhost:8005",
}


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

    return jsonify({"error": "The customer database is unavailable."}), 503


def validated_session_user():
    """Return the current active database user, not only cookie data."""
    if hasattr(g, "authenticated_user"):
        return g.authenticated_user, None

    cookie_user = session.get("user")
    if cookie_user is None:
        return None, (jsonify({"error": "You must sign in."}), 401)

    if (
        not isinstance(cookie_user, dict)
        or not isinstance(cookie_user.get("id"), int)
        or cookie_user.get("role") not in {"admin", "customer"}
    ):
        session.clear()
        return None, (jsonify({"error": "You must sign in."}), 401)

    try:
        result = database_request(f"/internal/users/{cookie_user['id']}")
    except HTTPError as error:
        if error.code == 404:
            session.clear()
            return None, (jsonify({"error": "You must sign in."}), 401)
        return None, database_error_response(error)
    except URLError as error:
        return None, database_error_response(error)

    stored_user = result.get("user", {})
    if (
        not isinstance(stored_user, dict)
        or stored_user.get("is_active") != 1
        or stored_user.get("role") != cookie_user.get("role")
        or any(
            field not in stored_user
            for field in ("id", "email", "full_name", "role")
        )
    ):
        session.clear()
        return None, (jsonify({"error": "You must sign in."}), 401)

    safe_user = {
        "id": stored_user["id"],
        "email": stored_user["email"],
        "full_name": stored_user["full_name"],
        "role": stored_user["role"],
    }
    session["user"] = safe_user
    g.authenticated_user = safe_user
    return safe_user, None


def login_required(function):
    @wraps(function)
    def protected_function(*args, **kwargs):
        _, error_response = validated_session_user()
        if error_response is not None:
            return error_response
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

        _, error_response = validated_session_user()
        if error_response is not None:
            return error_response

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


@app.get("/ready")
def ready():
    try:
        database_health = database_request("/health")
    except (HTTPError, URLError):
        return jsonify({
            "status": "starting",
            "database": "unavailable",
        }), 503

    return jsonify({
        "status": "ready",
        "database": database_health.get("status", "unknown"),
    })


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}

    email = clean_text(data.get("email")).lower()
    supplied_password = data.get("password")
    password = supplied_password if isinstance(supplied_password, str) else ""

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

    full_name = clean_text(data.get("full_name"))
    email = clean_text(data.get("email")).lower()
    supplied_password = data.get("password")
    supplied_confirmation = data.get("password_confirmation")
    password = supplied_password if isinstance(supplied_password, str) else ""
    password_confirmation = (
        supplied_confirmation
        if isinstance(supplied_confirmation, str)
        else ""
    )

    if not full_name:
        return jsonify({"error": "Full name is required."}), 400

    if len(full_name) > 100:
        return jsonify({
            "error": "Full name must be 100 characters or fewer."
        }), 400

    if not valid_email(email):
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
    user, error_response = validated_session_user()
    if error_response is not None:
        return error_response

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


@app.get("/api/loyalty")
@login_required
def get_own_loyalty():
    user_id = session["user"]["id"]

    try:
        result = database_request(f"/internal/loyalty/{user_id}")
    except (HTTPError, URLError) as error:
        return database_error_response(error)

    return jsonify(result)


@app.get("/api/loyalty/history")
@login_required
def get_own_loyalty_history():
    user_id = session["user"]["id"]

    try:
        result = database_request(
            f"/internal/loyalty/{user_id}/transactions?limit=20"
        )
    except (HTTPError, URLError) as error:
        return database_error_response(error)

    return jsonify(result)


@app.get("/api/admin/customers")
@admin_required
def get_customers():
    try:
        result = database_request("/internal/users?role=customer")
    except (HTTPError, URLError) as error:
        return database_error_response(error)

    return jsonify(result)


@app.get("/api/admin/loyalty")
@admin_required
def get_all_loyalty_accounts():
    try:
        result = database_request("/internal/loyalty")
    except (HTTPError, URLError) as error:
        return database_error_response(error)

    return jsonify(result)


@app.get("/api/admin/loyalty/<int:user_id>/history")
@admin_required
def get_customer_loyalty_history(user_id):
    try:
        result = database_request(
            f"/internal/loyalty/{user_id}/transactions?limit=20"
        )
    except (HTTPError, URLError) as error:
        return database_error_response(error)

    return jsonify(result)


@app.post("/api/admin/loyalty/<int:user_id>/adjustments")
@admin_required
def create_loyalty_adjustment(user_id):
    data = request.get_json(silent=True) or {}

    try:
        result = database_request(
            f"/internal/loyalty/{user_id}/adjustments",
            method="POST",
            payload={
                "points_change": data.get("points_change"),
                "reason": data.get("reason"),
                "created_by_admin_id": session["user"]["id"],
            },
        )
    except (HTTPError, URLError) as error:
        return database_error_response(error)

    return jsonify(result), 201


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
        target_result = database_request(f"/internal/users/{user_id}")
        if target_result["user"].get("role") != "customer":
            return jsonify({"error": "Customer not found."}), 404

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
