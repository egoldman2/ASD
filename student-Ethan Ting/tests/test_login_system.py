import importlib.util
import sys
from pathlib import Path

import pytest
from werkzeug.security import check_password_hash, generate_password_hash


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
    module = load_module("ethan_auth_app", BACKEND_APP_PATH)
    module.app.config.update(TESTING=True, SECRET_KEY="test-secret")
    return module


@pytest.fixture
def database_module(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "users.db"))
    monkeypatch.syspath_prepend(str(DATABASE_FOLDER))
    sys.modules.pop("init_db", None)
    return load_module("ethan_database_app", DATABASE_APP_PATH)


def test_valid_customer_login_creates_session(auth_module, monkeypatch):
    user = {
        "id": 2,
        "email": "customer@asd.local",
        "password_hash": generate_password_hash("CustomerPass!2026"),
        "full_name": "Demo Customer",
        "role": "customer",
        "is_active": 1,
    }
    monkeypatch.setattr(
        auth_module,
        "find_user_by_email",
        lambda email: {**user, "email": email},
    )
    monkeypatch.setattr(
        auth_module,
        "database_request",
        lambda path, method="GET", payload=None: {"user": user},
    )

    with auth_module.app.test_client() as client:
        response = client.post("/api/login", json={
            "email": "customer@asd.local",
            "password": "CustomerPass!2026",
        })

        assert response.status_code == 200
        assert response.get_json()["user"]["role"] == "customer"

        session_response = client.get("/api/session")
        assert session_response.status_code == 200
        assert session_response.get_json()["authenticated"] is True


def test_customer_registration_creates_customer_session(auth_module, monkeypatch):
    captured_request = {}

    def create_customer(path, method="GET", payload=None):
        if method == "GET":
            return {
                "user": {
                    "id": 12,
                    "email": "new.customer@example.test",
                    "full_name": "New Customer",
                    "role": "customer",
                    "is_active": 1,
                }
            }
        captured_request.update({
            "path": path,
            "method": method,
            "payload": payload,
        })
        return {
            "user": {
                "id": 12,
                "email": payload["email"],
                "full_name": payload["full_name"],
                "role": "customer",
                "is_active": 1,
            }
        }

    monkeypatch.setattr(auth_module, "database_request", create_customer)

    with auth_module.app.test_client() as client:
        response = client.post("/api/register", json={
            "email": "new.customer@example.test",
            "full_name": "New Customer",
            "password": "NewCustomerPass!2026",
            "password_confirmation": "NewCustomerPass!2026",
            "role": "admin",
        })

        assert response.status_code == 201
        assert response.get_json()["user"]["role"] == "customer"
        assert captured_request == {
            "path": "/internal/users",
            "method": "POST",
            "payload": {
                "email": "new.customer@example.test",
                "full_name": "New Customer",
                "password": "NewCustomerPass!2026",
            },
        }

        session_response = client.get("/api/session")
        assert session_response.status_code == 200
        assert session_response.get_json()["user"]["id"] == 12


def test_customer_registration_requires_matching_passwords(
    auth_module,
    monkeypatch,
):
    def unexpected_database_request(*args, **kwargs):
        pytest.fail("The database should not be called for invalid input.")

    monkeypatch.setattr(
        auth_module,
        "database_request",
        unexpected_database_request,
    )

    with auth_module.app.test_client() as client:
        response = client.post("/api/register", json={
            "email": "new.customer@example.test",
            "full_name": "New Customer",
            "password": "NewCustomerPass!2026",
            "password_confirmation": "DifferentPass!2026",
        })

    assert response.status_code == 400
    assert response.get_json()["error"] == "Passwords do not match."


def test_customer_is_forbidden_from_admin_api(auth_module):
    with auth_module.app.test_client() as client:
        with client.session_transaction() as login_session:
            login_session["user"] = {
                "id": 2,
                "email": "customer@asd.local",
                "full_name": "Demo Customer",
                "role": "customer",
            }

        response = client.get("/api/admin/customers")

    assert response.status_code == 403
    assert response.get_json()["error"] == "Administrator access required."


def test_customer_can_change_password(auth_module, monkeypatch):
    old_password = "CustomerPass!2026"
    captured_update = {}
    stored_user = {
        "id": 2,
        "email": "customer@asd.local",
        "full_name": "Demo Customer",
        "role": "customer",
        "is_active": 1,
        "password_hash": generate_password_hash(old_password),
    }

    def password_request(path, method="GET", payload=None):
        if method == "PUT":
            captured_update.update({
                "path": path,
                "method": method,
                "payload": payload,
            })
            return {"user": {key: value for key, value in stored_user.items()
                             if key != "password_hash"}}
        return {"user": stored_user}

    monkeypatch.setattr(auth_module, "database_request", password_request)

    with auth_module.app.test_client() as client:
        with client.session_transaction() as login_session:
            login_session["user"] = {
                "id": 2,
                "email": "customer@asd.local",
                "full_name": "Demo Customer",
                "role": "customer",
            }

        response = client.put("/api/profile/password", json={
            "current_password": old_password,
            "new_password": "NewCustomerPass!2026",
            "password_confirmation": "NewCustomerPass!2026",
        })

    assert response.status_code == 200
    assert response.get_json()["message"] == "Password updated successfully."
    assert captured_update == {
        "path": "/internal/users/2",
        "method": "PUT",
        "payload": {"password": "NewCustomerPass!2026"},
    }


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        ({
            "current_password": "WrongPassword!2026",
            "new_password": "NewCustomerPass!2026",
            "password_confirmation": "NewCustomerPass!2026",
        }, "Current password is incorrect."),
        ({
            "current_password": "CustomerPass!2026",
            "new_password": "short",
            "password_confirmation": "short",
        }, "New password must contain at least 8 characters."),
        ({
            "current_password": "CustomerPass!2026",
            "new_password": "NewCustomerPass!2026",
            "password_confirmation": "DifferentPass!2026",
        }, "New passwords do not match."),
        ({
            "current_password": "CustomerPass!2026",
            "new_password": "CustomerPass!2026",
            "password_confirmation": "CustomerPass!2026",
        }, "New password must be different from the current password."),
    ],
)
def test_customer_password_change_rejects_invalid_input(
    auth_module,
    monkeypatch,
    payload,
    expected_error,
):
    stored_user = {
        "id": 2,
        "email": "customer@asd.local",
        "full_name": "Demo Customer",
        "role": "customer",
        "is_active": 1,
        "password_hash": generate_password_hash("CustomerPass!2026"),
    }

    def password_request(path, method="GET", payload=None):
        if method == "PUT":
            pytest.fail("An invalid password change must not be saved.")
        return {"user": stored_user}

    monkeypatch.setattr(auth_module, "database_request", password_request)

    with auth_module.app.test_client() as client:
        with client.session_transaction() as login_session:
            login_session["user"] = {
                "id": 2,
                "email": "customer@asd.local",
                "full_name": "Demo Customer",
                "role": "customer",
            }

        response = client.put("/api/profile/password", json=payload)

    assert response.status_code == 400
    assert response.get_json()["error"] == expected_error


def test_admin_can_read_customer_list(auth_module, monkeypatch):
    def customer_list(path, method="GET", payload=None):
        if path == "/internal/users/1":
            return {"user": {
                "id": 1,
                "email": "admin@asd.local",
                "full_name": "Marketplace Administrator",
                "role": "admin",
                "is_active": 1,
            }}
        return {
            "count": 1,
            "users": [{
                "id": 2,
                "email": "customer@asd.local",
                "full_name": "Demo Customer",
                "role": "customer",
                "is_active": 1,
            }],
        }

    monkeypatch.setattr(auth_module, "database_request", customer_list)

    with auth_module.app.test_client() as client:
        with client.session_transaction() as login_session:
            login_session["user"] = {
                "id": 1,
                "email": "admin@asd.local",
                "full_name": "Marketplace Administrator",
                "role": "admin",
            }

        response = client.get("/api/admin/customers")

    assert response.status_code == 200
    assert response.get_json()["count"] == 1


def test_admin_can_read_and_create_administrators(auth_module, monkeypatch):
    captured_create = {}

    def administrator_request(path, method="GET", payload=None):
        if path == "/internal/users/1":
            return {"user": {
                "id": 1,
                "email": "admin@asd.local",
                "full_name": "Marketplace Administrator",
                "role": "admin",
                "is_active": 1,
            }}
        if path == "/internal/users?role=admin":
            return {
                "count": 1,
                "users": [{
                    "id": 1,
                    "email": "admin@asd.local",
                    "full_name": "Marketplace Administrator",
                    "role": "admin",
                    "is_active": 1,
                }],
            }

        captured_create.update({
            "path": path,
            "method": method,
            "payload": payload,
        })
        return {"user": {
            "id": 12,
            "email": payload["email"],
            "full_name": payload["full_name"],
            "role": payload["role"],
            "is_active": 1,
        }}

    monkeypatch.setattr(
        auth_module,
        "database_request",
        administrator_request,
    )

    with auth_module.app.test_client() as client:
        with client.session_transaction() as login_session:
            login_session["user"] = {
                "id": 1,
                "email": "admin@asd.local",
                "full_name": "Marketplace Administrator",
                "role": "admin",
            }

        list_response = client.get("/api/admin/administrators")
        create_response = client.post(
            "/api/admin/administrators",
            json={
                "full_name": "Second Administrator",
                "email": "second.admin@example.test",
                "password": "AdminPassword!2026",
                "role": "customer",
            },
        )

    assert list_response.status_code == 200
    assert list_response.get_json()["count"] == 1
    assert create_response.status_code == 201
    assert captured_create == {
        "path": "/internal/users",
        "method": "POST",
        "payload": {
            "full_name": "Second Administrator",
            "email": "second.admin@example.test",
            "password": "AdminPassword!2026",
            "role": "admin",
        },
    }


def test_customer_cannot_create_administrator(auth_module):
    with auth_module.app.test_client() as client:
        with client.session_transaction() as login_session:
            login_session["user"] = {
                "id": 2,
                "email": "customer@asd.local",
                "full_name": "Demo Customer",
                "role": "customer",
            }

        response = client.post(
            "/api/admin/administrators",
            json={
                "full_name": "Not Allowed",
                "email": "not.allowed@example.test",
                "password": "Password!2026",
            },
        )

    assert response.status_code == 403
    assert response.get_json()["error"] == "Administrator access required."


def test_customer_can_only_request_own_loyalty_account(
    auth_module,
    monkeypatch,
):
    captured_paths = []

    def loyalty_request(path, method="GET", payload=None):
        if path == "/internal/users/2":
            return {"user": {
                "id": 2,
                "email": "customer@asd.local",
                "full_name": "Demo Customer",
                "role": "customer",
                "is_active": 1,
            }}
        captured_paths.append(path)
        return {
            "loyalty": {
                "user_id": 2,
                "points_balance": 120,
                "tier": "Bronze",
            }
        }

    monkeypatch.setattr(auth_module, "database_request", loyalty_request)

    with auth_module.app.test_client() as client:
        with client.session_transaction() as login_session:
            login_session["user"] = {
                "id": 2,
                "email": "customer@asd.local",
                "full_name": "Demo Customer",
                "role": "customer",
            }

        response = client.get("/api/loyalty")

    assert response.status_code == 200
    assert response.get_json()["loyalty"]["user_id"] == 2
    assert captured_paths == ["/internal/loyalty/2"]


def test_customer_cannot_adjust_loyalty_points(auth_module):
    with auth_module.app.test_client() as client:
        with client.session_transaction() as login_session:
            login_session["user"] = {
                "id": 2,
                "email": "customer@asd.local",
                "full_name": "Demo Customer",
                "role": "customer",
            }

        response = client.post(
            "/api/admin/loyalty/2/adjustments",
            json={"points_change": 100, "reason": "Test"},
        )

    assert response.status_code == 403


def test_admin_adjustment_includes_authenticated_admin_id(
    auth_module,
    monkeypatch,
):
    captured_request = {}

    def adjustment_request(path, method="GET", payload=None):
        if path == "/internal/users/1":
            return {"user": {
                "id": 1,
                "email": "admin@asd.local",
                "full_name": "Marketplace Administrator",
                "role": "admin",
                "is_active": 1,
            }}
        captured_request.update({
            "path": path,
            "method": method,
            "payload": payload,
        })
        return {
            "message": "Loyalty points updated.",
            "loyalty": {"user_id": 2, "points_balance": 220},
        }

    monkeypatch.setattr(auth_module, "database_request", adjustment_request)

    with auth_module.app.test_client() as client:
        with client.session_transaction() as login_session:
            login_session["user"] = {
                "id": 1,
                "email": "admin@asd.local",
                "full_name": "Marketplace Administrator",
                "role": "admin",
            }

        response = client.post(
            "/api/admin/loyalty/2/adjustments",
            json={"points_change": 100, "reason": "Service recovery"},
        )

    assert response.status_code == 201
    assert captured_request == {
        "path": "/internal/loyalty/2/adjustments",
        "method": "POST",
        "payload": {
            "points_change": 100,
            "reason": "Service recovery",
            "created_by_admin_id": 1,
        },
    }


def test_database_customer_crud_uses_soft_delete(database_module):
    with database_module.app.test_client() as client:
        create_response = client.post("/internal/users", json={
            "email": "new.customer@example.test",
            "full_name": "New Customer",
            "password": "TemporaryPass!2026",
        })
        assert create_response.status_code == 201

        customer = create_response.get_json()["user"]
        customer_id = customer["id"]

        loyalty_response = client.get(f"/internal/loyalty/{customer_id}")
        assert loyalty_response.status_code == 200
        assert loyalty_response.get_json()["loyalty"]["points_balance"] == 0
        assert loyalty_response.get_json()["loyalty"]["tier"] == "Bronze"

        stored_response = client.get(
            "/internal/users/by-email?email=new.customer@example.test"
        )
        stored_user = stored_response.get_json()["user"]
        assert stored_user["password_hash"] != "TemporaryPass!2026"
        assert check_password_hash(
            stored_user["password_hash"],
            "TemporaryPass!2026",
        )

        duplicate_response = client.post("/internal/users", json={
            "email": "new.customer@example.test",
            "full_name": "Duplicate Customer",
            "password": "DifferentPass!2026",
        })
        assert duplicate_response.status_code == 409

        update_response = client.put(
            f"/internal/users/{customer_id}",
            json={"full_name": "Updated Customer"},
        )
        assert update_response.status_code == 200
        assert update_response.get_json()["user"]["full_name"] == (
            "Updated Customer"
        )

        password_response = client.put(
            f"/internal/users/{customer_id}",
            json={"password": "UpdatedPassword!2026"},
        )
        assert password_response.status_code == 200
        assert "password_hash" not in password_response.get_json()["user"]

        updated_stored_response = client.get(
            "/internal/users/by-email?email=new.customer@example.test"
        )
        updated_hash = updated_stored_response.get_json()["user"][
            "password_hash"
        ]
        assert check_password_hash(updated_hash, "UpdatedPassword!2026")
        assert not check_password_hash(updated_hash, "TemporaryPass!2026")

        delete_response = client.delete(f"/internal/users/{customer_id}")
        assert delete_response.status_code == 200
        assert delete_response.get_json()["user"]["is_active"] == 0


def test_database_admin_creation_does_not_create_loyalty_account(database_module):
    with database_module.app.test_client() as client:
        create_response = client.post("/internal/users", json={
            "email": "new.admin@example.test",
            "full_name": "New Administrator",
            "password": "AdminPassword!2026",
            "role": "admin",
        })

        assert create_response.status_code == 201
        administrator = create_response.get_json()["user"]
        assert administrator["role"] == "admin"

        loyalty_response = client.get(
            f"/internal/loyalty/{administrator['id']}"
        )
        assert loyalty_response.status_code == 404


def test_database_rejects_unknown_account_role(database_module):
    with database_module.app.test_client() as client:
        response = client.post("/internal/users", json={
            "email": "unknown.role@example.test",
            "full_name": "Unknown Role",
            "password": "Password!2026",
            "role": "superuser",
        })

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Account role must be admin or customer."
    )


def test_database_seeds_ten_loyalty_accounts_and_transactions(database_module):
    with database_module.app.test_client() as client:
        accounts_response = client.get("/internal/loyalty")
        accounts = accounts_response.get_json()["loyalty_accounts"]

        assert accounts_response.status_code == 200
        assert len(accounts) == 10

        transaction_count = 0
        for account in accounts:
            history_response = client.get(
                f"/internal/loyalty/{account['user_id']}/transactions"
            )
            transaction_count += history_response.get_json()["count"]

        assert transaction_count >= 10


def test_database_backfills_existing_customer_loyalty_account(database_module):
    with database_module.get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO users
                (email, password_hash, full_name, role)
            VALUES (?, ?, ?, 'customer')
            """,
            (
                "legacy.customer@example.test",
                generate_password_hash("CustomerPass!2026"),
                "Legacy Customer",
            ),
        )
        customer_id = cursor.lastrowid

    database_module.initialise_database()

    with database_module.app.test_client() as client:
        response = client.get(f"/internal/loyalty/{customer_id}")

    assert response.status_code == 200
    assert response.get_json()["loyalty"]["points_balance"] == 0


def test_database_loyalty_adjustment_updates_tier_and_history(database_module):
    with database_module.app.test_client() as client:
        customer = client.get(
            "/internal/users/by-email?email=customer@asd.local"
        ).get_json()["user"]
        admin = client.get(
            "/internal/users/by-email?email=admin@asd.local"
        ).get_json()["user"]

        adjustment_response = client.post(
            f"/internal/loyalty/{customer['id']}/adjustments",
            json={
                "points_change": 380,
                "reason": "Completed an order",
                "created_by_admin_id": admin["id"],
            },
        )

        assert adjustment_response.status_code == 201
        updated_loyalty = adjustment_response.get_json()["loyalty"]
        assert updated_loyalty["points_balance"] == 500
        assert updated_loyalty["tier"] == "Silver"
        assert updated_loyalty["points_to_next_tier"] == 500

        history_response = client.get(
            f"/internal/loyalty/{customer['id']}/transactions"
        )
        latest_transaction = history_response.get_json()["transactions"][0]
        assert latest_transaction["points_change"] == 380
        assert latest_transaction["reason"] == "Completed an order"
        assert latest_transaction["created_by_admin_name"] == (
            "Marketplace Administrator"
        )


def test_database_rejects_negative_loyalty_balance(database_module):
    with database_module.app.test_client() as client:
        customer = client.get(
            "/internal/users/by-email?email=customer@asd.local"
        ).get_json()["user"]

        response = client.post(
            f"/internal/loyalty/{customer['id']}/adjustments",
            json={
                "points_change": -121,
                "reason": "Invalid redemption",
            },
        )

        assert response.status_code == 400
        assert response.get_json()["error"] == (
            "Points balance cannot go below zero."
        )

        loyalty_response = client.get(
            f"/internal/loyalty/{customer['id']}"
        )
        assert loyalty_response.get_json()["loyalty"]["points_balance"] == 120
