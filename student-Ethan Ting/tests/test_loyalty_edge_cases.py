import importlib.util
import json
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError
from urllib.error import URLError

import pytest
from werkzeug.security import generate_password_hash


STUDENT_FOLDER = Path(__file__).resolve().parents[1]
BACKEND_APP_PATH = STUDENT_FOLDER / "backend" / "app.py"
DATABASE_FOLDER = STUDENT_FOLDER / "database"
DATABASE_APP_PATH = DATABASE_FOLDER / "app.py"


def load_module(module_name, module_path):
    specification = importlib.util.spec_from_file_location(
        module_name,
        module_path,
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.fixture
def auth_module():
    module = load_module("ethan_auth_edge_app", BACKEND_APP_PATH)
    module.app.config.update(TESTING=True, SECRET_KEY="test-secret")
    return module


@pytest.fixture
def database_module(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "users.db"))
    monkeypatch.syspath_prepend(str(DATABASE_FOLDER))
    sys.modules.pop("init_db", None)
    return load_module("ethan_database_edge_app", DATABASE_APP_PATH)


def login_session(client, role="customer", user_id=2):
    with client.session_transaction() as current_session:
        current_session["user"] = {
            "id": user_id,
            "email": f"{role}@asd.local",
            "full_name": f"Test {role.title()}",
            "role": role,
        }


def find_user(client, email):
    return client.get(
        f"/internal/users/by-email?email={email}"
    ).get_json()["user"]


@pytest.mark.parametrize(
    ("points", "tier", "next_tier", "points_needed"),
    [
        (0, "Bronze", "Silver", 500),
        (499, "Bronze", "Silver", 1),
        (500, "Silver", "Gold", 500),
        (999, "Silver", "Gold", 1),
        (1000, "Gold", None, 0),
        (5000, "Gold", None, 0),
    ],
)
def test_tier_boundaries(
    database_module,
    points,
    tier,
    next_tier,
    points_needed,
):
    status = database_module.loyalty_status(points)

    assert status == {
        "tier": tier,
        "next_tier": next_tier,
        "points_to_next_tier": points_needed,
    }


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        ({}, "Points adjustment must be a whole number."),
        ({"points_change": True, "reason": "Invalid"},
         "Points adjustment must be a whole number."),
        ({"points_change": 1.5, "reason": "Invalid"},
         "Points adjustment must be a whole number."),
        ({"points_change": "100", "reason": "Invalid"},
         "Points adjustment must be a whole number."),
        ({"points_change": 0, "reason": "Invalid"},
         "Points adjustment cannot be zero."),
        ({"points_change": 100}, "A reason is required."),
        ({"points_change": 100, "reason": "   "}, "A reason is required."),
        ({"points_change": 100, "reason": None}, "A reason is required."),
        ({"points_change": 100, "reason": 123}, "A reason is required."),
        ({"points_change": 100, "reason": "x" * 201},
         "The reason must be 200 characters or fewer."),
        ({"points_change": 1_000_001, "reason": "Too large"},
         "A single adjustment cannot exceed 1,000,000 points."),
    ],
)
def test_database_rejects_invalid_adjustments(
    database_module,
    payload,
    expected_error,
):
    with database_module.app.test_client() as client:
        customer = find_user(client, "customer@asd.local")
        response = client.post(
            f"/internal/loyalty/{customer['id']}/adjustments",
            json=payload,
        )

    assert response.status_code == 400
    assert response.get_json()["error"] == expected_error


def test_database_rejects_missing_customer_and_invalid_admin(database_module):
    with database_module.app.test_client() as client:
        missing_customer = client.post(
            "/internal/loyalty/999999/adjustments",
            json={"points_change": 10, "reason": "Test"},
        )
        customer = find_user(client, "customer@asd.local")
        invalid_admin = client.post(
            f"/internal/loyalty/{customer['id']}/adjustments",
            json={
                "points_change": 10,
                "reason": "Test",
                "created_by_admin_id": customer["id"],
            },
        )

    assert missing_customer.status_code == 404
    assert invalid_admin.status_code == 400
    assert invalid_admin.get_json()["error"] == "Administrator not found."


def test_exact_redemption_to_zero_is_allowed(database_module):
    with database_module.app.test_client() as client:
        customer = find_user(client, "customer@asd.local")
        response = client.post(
            f"/internal/loyalty/{customer['id']}/adjustments",
            json={
                "points_change": -120,
                "reason": "Redeemed all available points",
            },
        )

    assert response.status_code == 201
    assert response.get_json()["loyalty"]["points_balance"] == 0
    assert response.get_json()["loyalty"]["tier"] == "Bronze"


def test_failed_redemption_does_not_create_history(database_module):
    with database_module.app.test_client() as client:
        customer = find_user(client, "customer@asd.local")
        history_path = (
            f"/internal/loyalty/{customer['id']}/transactions"
        )
        count_before = client.get(history_path).get_json()["count"]

        response = client.post(
            f"/internal/loyalty/{customer['id']}/adjustments",
            json={"points_change": -121, "reason": "Too many points"},
        )
        count_after = client.get(history_path).get_json()["count"]

    assert response.status_code == 400
    assert count_after == count_before


def test_tier_can_move_up_and_down(database_module):
    with database_module.app.test_client() as client:
        customer = find_user(client, "customer@asd.local")
        path = f"/internal/loyalty/{customer['id']}/adjustments"

        silver_response = client.post(
            path,
            json={"points_change": 380, "reason": "Reached Silver"},
        )
        gold_response = client.post(
            path,
            json={"points_change": 500, "reason": "Reached Gold"},
        )
        bronze_response = client.post(
            path,
            json={"points_change": -501, "reason": "Redeemed points"},
        )

    assert silver_response.get_json()["loyalty"]["tier"] == "Silver"
    assert gold_response.get_json()["loyalty"]["tier"] == "Gold"
    assert bronze_response.get_json()["loyalty"]["tier"] == "Bronze"
    assert bronze_response.get_json()["loyalty"]["points_balance"] == 499


def test_transaction_history_is_newest_first(database_module):
    with database_module.app.test_client() as client:
        customer = find_user(client, "customer@asd.local")
        adjustment_path = (
            f"/internal/loyalty/{customer['id']}/adjustments"
        )
        client.post(
            adjustment_path,
            json={"points_change": 10, "reason": "First adjustment"},
        )
        client.post(
            adjustment_path,
            json={"points_change": 20, "reason": "Second adjustment"},
        )

        history = client.get(
            f"/internal/loyalty/{customer['id']}/transactions?limit=2"
        ).get_json()["transactions"]

    assert [item["reason"] for item in history] == [
        "Second adjustment",
        "First adjustment",
    ]


def test_transaction_history_validates_and_clamps_limit(database_module):
    with database_module.app.test_client() as client:
        customer = find_user(client, "customer@asd.local")
        path = f"/internal/loyalty/{customer['id']}/transactions"

        invalid_response = client.get(f"{path}?limit=not-a-number")
        minimum_response = client.get(f"{path}?limit=0")

    assert invalid_response.status_code == 400
    assert minimum_response.status_code == 200
    assert minimum_response.get_json()["count"] == 1


def test_public_loyalty_responses_do_not_expose_password_hash(database_module):
    with database_module.app.test_client() as client:
        response_text = client.get("/internal/loyalty").get_data(as_text=True)

    assert "password" not in response_text.lower()


def test_database_initialisation_is_idempotent(database_module):
    with database_module.get_connection() as connection:
        counts_before = (
            connection.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            connection.execute(
                "SELECT COUNT(*) FROM loyalty_accounts"
            ).fetchone()[0],
            connection.execute(
                "SELECT COUNT(*) FROM loyalty_transactions"
            ).fetchone()[0],
        )

    database_module.initialise_database()
    database_module.initialise_database()

    with database_module.get_connection() as connection:
        counts_after = (
            connection.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            connection.execute(
                "SELECT COUNT(*) FROM loyalty_accounts"
            ).fetchone()[0],
            connection.execute(
                "SELECT COUNT(*) FROM loyalty_transactions"
            ).fetchone()[0],
        )

    assert counts_after == counts_before


def test_database_constraints_reject_invalid_direct_writes(database_module):
    with database_module.get_connection() as connection:
        customer = connection.execute(
            "SELECT id FROM users WHERE email = 'customer@asd.local'"
        ).fetchone()

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                UPDATE loyalty_accounts
                SET points_balance = -1
                WHERE user_id = ?
                """,
                (customer["id"],),
            )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO loyalty_transactions
                    (user_id, points_change, reason)
                VALUES (?, 0, 'Invalid zero adjustment')
                """,
                (customer["id"],),
            )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO loyalty_accounts (user_id, points_balance)
                VALUES (999999, 0)
                """
            )


def test_concurrent_adjustments_do_not_lose_points(database_module):
    with database_module.app.test_client() as client:
        customer = find_user(client, "customer@asd.local")
        customer_id = customer["id"]

    def add_one_point(adjustment_number):
        with database_module.app.test_client() as client:
            response = client.post(
                f"/internal/loyalty/{customer_id}/adjustments",
                json={
                    "points_change": 1,
                    "reason": f"Concurrent adjustment {adjustment_number}",
                },
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=5) as executor:
        statuses = list(executor.map(add_one_point, range(20)))

    with database_module.app.test_client() as client:
        loyalty = client.get(
            f"/internal/loyalty/{customer_id}"
        ).get_json()["loyalty"]
        history = client.get(
            f"/internal/loyalty/{customer_id}/transactions?limit=100"
        ).get_json()["transactions"]

    assert statuses == [201] * 20
    assert loyalty["points_balance"] == 140
    assert len(history) == 21


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/loyalty"),
        ("get", "/api/loyalty/history"),
        ("get", "/api/admin/loyalty"),
        ("get", "/api/admin/loyalty/2/history"),
        ("post", "/api/admin/loyalty/2/adjustments"),
    ],
)
def test_loyalty_endpoints_require_login(auth_module, method, path):
    with auth_module.app.test_client() as client:
        response = getattr(client, method)(path, json={} if method == "post" else None)

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/admin/loyalty"),
        ("get", "/api/admin/loyalty/2/history"),
        ("post", "/api/admin/loyalty/2/adjustments"),
    ],
)
def test_customer_is_forbidden_from_all_admin_loyalty_routes(
    auth_module,
    method,
    path,
):
    with auth_module.app.test_client() as client:
        login_session(client)
        response = getattr(client, method)(
            path,
            json={} if method == "post" else None,
        )

    assert response.status_code == 403


def test_customer_loyalty_path_uses_session_id(auth_module, monkeypatch):
    captured_paths = []

    def fake_database_request(path, method="GET", payload=None):
        if path == "/internal/users/42":
            return {"user": {
                "id": 42,
                "email": "customer@asd.local",
                "full_name": "Test Customer",
                "role": "customer",
                "is_active": 1,
            }}
        captured_paths.append(path)
        return {"loyalty": {"user_id": 42}}

    monkeypatch.setattr(auth_module, "database_request", fake_database_request)

    with auth_module.app.test_client() as client:
        login_session(client, user_id=42)
        response = client.get("/api/loyalty?user_id=3")

    assert response.status_code == 200
    assert captured_paths == ["/internal/loyalty/42"]


def test_backend_overrides_forged_admin_id(auth_module, monkeypatch):
    captured_payload = {}

    def fake_database_request(path, method="GET", payload=None):
        if path == "/internal/users/7":
            return {"user": {
                "id": 7,
                "email": "admin@asd.local",
                "full_name": "Test Admin",
                "role": "admin",
                "is_active": 1,
            }}
        captured_payload.update(payload)
        return {"message": "Loyalty points updated."}

    monkeypatch.setattr(auth_module, "database_request", fake_database_request)

    with auth_module.app.test_client() as client:
        login_session(client, role="admin", user_id=7)
        response = client.post(
            "/api/admin/loyalty/2/adjustments",
            json={
                "points_change": 25,
                "reason": "Test",
                "created_by_admin_id": 999,
            },
        )

    assert response.status_code == 201
    assert captured_payload["created_by_admin_id"] == 7


def test_admin_customer_route_cannot_edit_an_administrator(
    auth_module,
    monkeypatch,
):
    requests = []

    def fake_database_request(path, method="GET", payload=None):
        requests.append((path, method, payload))
        return {
            "user": {
                "id": 1,
                "email": "admin@asd.local",
                "full_name": "Administrator",
                "role": "admin",
                "is_active": 1,
            }
        }

    monkeypatch.setattr(auth_module, "database_request", fake_database_request)

    with auth_module.app.test_client() as client:
        login_session(client, role="admin", user_id=1)
        response = client.put(
            "/api/admin/customers/1",
            json={"email": "attacker@example.test", "is_active": 0},
        )

    assert response.status_code == 404
    assert requests == [
        ("/internal/users/1", "GET", None),
        ("/internal/users/1", "GET", None),
    ]


def test_login_cookie_is_httponly_and_samesite_lax(auth_module, monkeypatch):
    monkeypatch.setattr(
        auth_module,
        "find_user_by_email",
        lambda email: {
            "id": 2,
            "email": email,
            "password_hash": generate_password_hash("CorrectPassword!2026"),
            "full_name": "Cookie Customer",
            "role": "customer",
            "is_active": 1,
        },
    )

    with auth_module.app.test_client() as client:
        response = client.post("/api/login", json={
            "email": "cookie@example.test",
            "password": "CorrectPassword!2026",
        })

    cookie_header = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie_header
    assert "SameSite=Lax" in cookie_header
    assert "ethan_session=" in cookie_header


def test_logout_clears_authenticated_session(auth_module, monkeypatch):
    monkeypatch.setattr(
        auth_module,
        "database_request",
        lambda path, method="GET", payload=None: {"user": {
            "id": 2,
            "email": "customer@asd.local",
            "full_name": "Test Customer",
            "role": "customer",
            "is_active": 1,
        }},
    )

    with auth_module.app.test_client() as client:
        login_session(client)
        assert client.get("/api/session").status_code == 200

        logout_response = client.post("/api/logout")
        session_response = client.get("/api/session")

    assert logout_response.status_code == 200
    assert session_response.status_code == 401


def test_inactive_customer_cannot_log_in(auth_module, monkeypatch):
    monkeypatch.setattr(
        auth_module,
        "find_user_by_email",
        lambda email: {
            "id": 2,
            "email": email,
            "password_hash": generate_password_hash("CorrectPassword!2026"),
            "full_name": "Disabled Customer",
            "role": "customer",
            "is_active": 0,
        },
    )

    with auth_module.app.test_client() as client:
        response = client.post("/api/login", json={
            "email": "disabled@example.test",
            "password": "CorrectPassword!2026",
        })

    assert response.status_code == 401
    assert response.get_json()["error"] == "Invalid email or password."


def test_disabling_customer_invalidates_existing_session(
    auth_module,
    monkeypatch,
):
    active_state = {"is_active": 1}

    def current_user(path, method="GET", payload=None):
        assert path == "/internal/users/2"
        return {
            "user": {
                "id": 2,
                "email": "customer@asd.local",
                "full_name": "Demo Customer",
                "role": "customer",
                "is_active": active_state["is_active"],
            }
        }

    monkeypatch.setattr(auth_module, "database_request", current_user)

    with auth_module.app.test_client() as client:
        login_session(client)
        assert client.get("/api/session").status_code == 200

        active_state["is_active"] = 0
        disabled_response = client.get("/api/session")
        cleared_response = client.get("/api/session")

    assert disabled_response.status_code == 401
    assert cleared_response.status_code == 401


@pytest.mark.parametrize(
    "malformed_user",
    [
        "customer",
        {},
        {"id": "2", "role": "customer"},
        {"id": 2, "role": "unknown"},
    ],
)
def test_malformed_session_is_cleared_without_database_call(
    auth_module,
    monkeypatch,
    malformed_user,
):
    def unexpected_database_request(*args, **kwargs):
        pytest.fail("Malformed cookie data should not reach the database API.")

    monkeypatch.setattr(
        auth_module,
        "database_request",
        unexpected_database_request,
    )

    with auth_module.app.test_client() as client:
        with client.session_transaction() as current_session:
            current_session["user"] = malformed_user

        response = client.get("/api/session")
        second_response = client.get("/api/session")

    assert response.status_code == 401
    assert second_response.status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"email": None, "password": "Password!2026"},
        {"email": "customer@asd.local", "password": None},
        {"email": "", "password": "Password!2026"},
    ],
)
def test_login_rejects_missing_or_non_string_credentials(
    auth_module,
    payload,
):
    with auth_module.app.test_client() as client:
        response = client.post("/api/login", json=payload)

    assert response.status_code == 400
    assert response.get_json()["error"] == "Email and password are required."


@pytest.mark.parametrize(
    "payload",
    [
        {
            "full_name": None,
            "email": "new@example.test",
            "password": "NewPassword!2026",
            "password_confirmation": "NewPassword!2026",
        },
        {
            "full_name": "New Customer",
            "email": "customer@",
            "password": "NewPassword!2026",
            "password_confirmation": "NewPassword!2026",
        },
        {
            "full_name": "New Customer",
            "email": None,
            "password": "NewPassword!2026",
            "password_confirmation": "NewPassword!2026",
        },
        {
            "full_name": "New Customer",
            "email": "new@example.test",
            "password": None,
            "password_confirmation": None,
        },
    ],
)
def test_registration_rejects_invalid_value_types(
    auth_module,
    monkeypatch,
    payload,
):
    def unexpected_database_request(*args, **kwargs):
        pytest.fail("Invalid registration data reached the database API.")

    monkeypatch.setattr(
        auth_module,
        "database_request",
        unexpected_database_request,
    )

    with auth_module.app.test_client() as client:
        response = client.post("/api/register", json=payload)

    assert response.status_code == 400


def test_database_rejects_invalid_customer_value_types(database_module):
    invalid_customers = [
        {
            "full_name": None,
            "email": "new@example.test",
            "password": "NewPassword!2026",
        },
        {
            "full_name": "New Customer",
            "email": "customer@",
            "password": "NewPassword!2026",
        },
        {
            "full_name": "New Customer",
            "email": "new@example.test",
            "password": None,
        },
    ]

    with database_module.app.test_client() as client:
        responses = [
            client.post("/internal/users", json=payload)
            for payload in invalid_customers
        ]

    assert all(response.status_code == 400 for response in responses)


@pytest.mark.parametrize(
    "allowed_origin",
    [f"http://localhost:{port}" for port in range(8000, 8006)],
)
def test_cors_allows_each_team_frontend_origin(
    auth_module,
    allowed_origin,
):
    with auth_module.app.test_client() as client:
        allowed_response = client.get(
            "/health",
            headers={"Origin": allowed_origin},
        )

    assert allowed_response.headers["Access-Control-Allow-Origin"] == (
        allowed_origin
    )
    assert allowed_response.headers["Access-Control-Allow-Credentials"] == "true"


def test_cors_rejects_unknown_origin(auth_module):
    with auth_module.app.test_client() as client:
        unknown_response = client.get(
            "/health",
            headers={"Origin": "https://malicious.example"},
        )

    assert "Access-Control-Allow-Origin" not in unknown_response.headers


def test_backend_readiness_checks_database(auth_module, monkeypatch):
    monkeypatch.setattr(
        auth_module,
        "database_request",
        lambda path, method="GET", payload=None: {"status": "healthy"},
    )

    with auth_module.app.test_client() as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ready",
        "database": "healthy",
    }


def test_backend_readiness_reports_unavailable_database(
    auth_module,
    monkeypatch,
):
    def unavailable_database(*args, **kwargs):
        raise URLError("database unavailable")

    monkeypatch.setattr(
        auth_module,
        "database_request",
        unavailable_database,
    )

    with auth_module.app.test_client() as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.get_json()["status"] == "starting"


def test_database_http_error_is_forwarded_to_frontend(auth_module, monkeypatch):
    error_body = json.dumps({"error": "Points balance cannot go below zero."})

    def rejected_request(path, method="GET", payload=None):
        if path == "/internal/users/1":
            return {"user": {
                "id": 1,
                "email": "admin@asd.local",
                "full_name": "Test Admin",
                "role": "admin",
                "is_active": 1,
            }}
        raise HTTPError(
            url=path,
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=__import__("io").BytesIO(error_body.encode("utf-8")),
        )

    monkeypatch.setattr(auth_module, "database_request", rejected_request)

    with auth_module.app.test_client() as client:
        login_session(client, role="admin", user_id=1)
        response = client.post(
            "/api/admin/loyalty/2/adjustments",
            json={"points_change": -999, "reason": "Invalid"},
        )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Points balance cannot go below zero."
    )
