import importlib.util
import sys
from pathlib import Path

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
    monkeypatch.setattr(
        auth_module,
        "find_user_by_email",
        lambda email: {
            "id": 2,
            "email": email,
            "password_hash": generate_password_hash("CustomerPass!2026"),
            "full_name": "Demo Customer",
            "role": "customer",
            "is_active": 1,
        },
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


def test_admin_can_read_customer_list(auth_module, monkeypatch):
    monkeypatch.setattr(
        auth_module,
        "database_request",
        lambda path, method="GET", payload=None: {
            "count": 1,
            "users": [{
                "id": 2,
                "email": "customer@asd.local",
                "full_name": "Demo Customer",
                "role": "customer",
                "is_active": 1,
            }],
        },
    )

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

        update_response = client.put(
            f"/internal/users/{customer_id}",
            json={"full_name": "Updated Customer"},
        )
        assert update_response.status_code == 200
        assert update_response.get_json()["user"]["full_name"] == (
            "Updated Customer"
        )

        delete_response = client.delete(f"/internal/users/{customer_id}")
        assert delete_response.status_code == 200
        assert delete_response.get_json()["user"]["is_active"] == 0
