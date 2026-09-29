"""Backend boundary tests for Ethan Ting's loyalty MCP integration."""

import importlib.util
from pathlib import Path

import pytest


BACKEND_APP = Path(__file__).resolve().parents[1] / "backend" / "app.py"


@pytest.fixture
def auth_module():
    specification = importlib.util.spec_from_file_location(
        "ethan_mcp_loyalty_app", BACKEND_APP
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    module.app.config.update(TESTING=True, SECRET_KEY="mcp-test-key")
    return module


def login_session(client, role="admin"):
    with client.session_transaction() as current_session:
        current_session["user"] = {
            "id": 1,
            "email": f"{role}@asd.local",
            "full_name": "Test User",
            "role": role,
        }


def database_request(path, method="GET", payload=None):
    if path == "/internal/users/1":
        return {
            "user": {
                "id": 1,
                "email": "admin@asd.local",
                "full_name": "Test User",
                "role": "admin",
                "is_active": 1,
            }
        }
    if path == "/internal/loyalty/2":
        return {
            "loyalty": {
                "user_id": 2,
                "full_name": "Private Customer",
                "email": "private@example.test",
                "points_balance": 720,
            }
        }
    raise AssertionError(f"Unexpected database request: {method} {path}")


def tool_response(points=720):
    return {
        "success": True,
        "tool": "ethan_ting_calculate_loyalty_tier",
        "result": {
            "points_balance": points,
            "tier": "Silver",
            "next_tier": "Gold",
            "points_to_next_tier": 1000 - points,
        },
        "error": None,
        "metadata": {"read_only": True},
    }


def test_mcp_route_requires_admin(auth_module):
    with auth_module.app.test_client() as client:
        anonymous = client.post("/api/admin/mcp/loyalty-tier", json={"user_id": 2})
        login_session(client, role="customer")
        customer = client.post("/api/admin/mcp/loyalty-tier", json={"user_id": 2})

    assert anonymous.status_code == 401
    assert customer.status_code == 403


@pytest.mark.parametrize("body", [{}, {"user_id": True}, {"user_id": 0}, {"user_id": "2"}])
def test_mcp_route_rejects_invalid_customer_id(auth_module, monkeypatch, body):
    monkeypatch.setattr(auth_module, "database_request", database_request)
    with auth_module.app.test_client() as client:
        login_session(client)
        response = client.post("/api/admin/mcp/loyalty-tier", json=body)

    assert response.status_code == 400


def test_mcp_route_sends_only_points_and_returns_structured_result(
    auth_module, monkeypatch
):
    monkeypatch.setattr(auth_module, "database_request", database_request)
    monkeypatch.setenv("MCP_ENABLED", "true")
    calls = []

    def fake_mcp_call(points_balance):
        calls.append(points_balance)
        return tool_response(points_balance)

    monkeypatch.setattr(auth_module, "call_loyalty_tier_mcp", fake_mcp_call)
    with auth_module.app.test_client() as client:
        login_session(client)
        response = client.post("/api/admin/mcp/loyalty-tier", json={"user_id": 2})

    assert response.status_code == 200
    assert calls == [720]
    assert response.get_json()["result"]["points_to_next_tier"] == 280
    assert "private@example.test" not in response.get_data(as_text=True)
    assert "Private Customer" not in response.get_data(as_text=True)


def test_mcp_route_stays_disabled_in_ci(auth_module, monkeypatch):
    monkeypatch.setattr(auth_module, "database_request", database_request)
    monkeypatch.setenv("MCP_ENABLED", "false")
    with auth_module.app.test_client() as client:
        login_session(client)
        response = client.post("/api/admin/mcp/loyalty-tier", json={"user_id": 2})

    assert response.status_code == 503
    assert response.get_json()["error"] == "MCP mode is disabled."


def test_mcp_route_rejects_invalid_database_points(auth_module, monkeypatch):
    def invalid_points(path, method="GET", payload=None):
        if path == "/internal/loyalty/2":
            return {"loyalty": {"points_balance": -1}}
        return database_request(path, method, payload)

    monkeypatch.setattr(auth_module, "database_request", invalid_points)
    monkeypatch.setenv("MCP_ENABLED", "true")
    with auth_module.app.test_client() as client:
        login_session(client)
        response = client.post("/api/admin/mcp/loyalty-tier", json={"user_id": 2})

    assert response.status_code == 502


@pytest.mark.parametrize("invalid_payload", [None, {}, {"success": True}])
def test_mcp_route_rejects_bad_tool_output(auth_module, monkeypatch, invalid_payload):
    monkeypatch.setattr(auth_module, "database_request", database_request)
    monkeypatch.setenv("MCP_ENABLED", "true")
    monkeypatch.setattr(
        auth_module, "call_loyalty_tier_mcp", lambda points: invalid_payload
    )
    with auth_module.app.test_client() as client:
        login_session(client)
        response = client.post("/api/admin/mcp/loyalty-tier", json={"user_id": 2})

    assert response.status_code == 502


def test_mcp_route_reports_local_service_unavailable(auth_module, monkeypatch):
    monkeypatch.setattr(auth_module, "database_request", database_request)
    monkeypatch.setenv("MCP_ENABLED", "true")

    def unavailable(_):
        raise ConnectionError("private transport details")

    monkeypatch.setattr(auth_module, "call_loyalty_tier_mcp", unavailable)
    with auth_module.app.test_client() as client:
        login_session(client)
        response = client.post("/api/admin/mcp/loyalty-tier", json={"user_id": 2})

    assert response.status_code == 503
    assert "private transport details" not in response.get_data(as_text=True)
