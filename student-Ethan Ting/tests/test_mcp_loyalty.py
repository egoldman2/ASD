"""Backend boundary tests for Ethan Ting's loyalty MCP integration."""

import importlib.util
import json
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


@pytest.mark.parametrize("field,value", [
    ("tier", "Gold"),
    ("next_tier", None),
    ("points_to_next_tier", 279),
])
def test_mcp_route_rejects_inconsistent_tier(auth_module, monkeypatch, field, value):
    monkeypatch.setattr(auth_module, "database_request", database_request)
    monkeypatch.setenv("MCP_ENABLED", "true")
    invalid = tool_response()
    invalid["result"][field] = value
    monkeypatch.setattr(auth_module, "call_loyalty_tier_mcp", lambda _: invalid)
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


@pytest.mark.parametrize("points,tier,next_tier,remaining", [
    (0, "Bronze", "Silver", 500), (499, "Bronze", "Silver", 1),
    (500, "Silver", "Gold", 500), (720, "Silver", "Gold", 280),
    (999, "Silver", "Gold", 1), (1000, "Gold", None, 0),
    (1200, "Gold", None, 0),
])
def test_ai_calculates_and_verifies_boundaries(auth_module, monkeypatch, points, tier, next_tier, remaining):
    monkeypatch.setenv("AI_MODE_ENABLED", "true")
    expected = {"points_balance": points, "tier": tier,
                "next_tier": next_tier, "points_to_next_tier": remaining}
    calls = []
    def model(system, prompt, num_predict, **kwargs):
        calls.append((json.loads(prompt), kwargs))
        return json.dumps(expected)
    monkeypatch.setattr(auth_module, "ollama_chat", model)
    result = auth_module.ai_loyalty_calculation(expected)
    assert result["status"] == "verified" and result["result"] == expected
    assert result["model"] == auth_module.OLLAMA_MODEL
    assert calls[0][0] == {"points_balance": points}
    assert calls[0][1]["timeout"] == 30
    assert calls[0][1]["response_format"]["additionalProperties"] is False


@pytest.mark.parametrize("answer", [
    "not JSON", "[]", "null", "{}",
    json.dumps({**tool_response()["result"], "points_to_next_tier": 279}),
    json.dumps({**tool_response()["result"], "points_balance": True}),
    json.dumps({**tool_response()["result"], "points_to_next_tier": 280.0}),
    json.dumps({**tool_response()["result"], "tier": "Gold"}),
    json.dumps({**tool_response()["result"], "unexpected": "data"}),
])
def test_ai_wrong_or_malformed_calculation_is_rejected(auth_module, monkeypatch, answer):
    monkeypatch.setenv("AI_MODE_ENABLED", "true")
    monkeypatch.setattr(auth_module, "ollama_chat", lambda *args, **kwargs: answer)
    assert auth_module.ai_loyalty_calculation(tool_response()["result"])["status"] == "rejected"


def test_ai_unavailable_keeps_rule_based_result(auth_module, monkeypatch):
    monkeypatch.setenv("AI_MODE_ENABLED", "true")
    def unavailable(*args, **kwargs):
        raise auth_module.OllamaUnavailableError
    monkeypatch.setattr(auth_module, "ollama_chat", unavailable)
    assert auth_module.ai_loyalty_calculation(tool_response()["result"])["status"] == "unavailable"


def test_ai_disabled_does_not_contact_model(auth_module, monkeypatch):
    monkeypatch.setenv("AI_MODE_ENABLED", "false")
    def forbidden(*args, **kwargs):
        pytest.fail("Disabled AI must not contact Ollama")
    monkeypatch.setattr(auth_module, "ollama_chat", forbidden)
    assert auth_module.ai_loyalty_calculation(tool_response()["result"]) == {"status": "disabled", "model": None}


def test_progress_route_explicitly_requests_ai(auth_module, monkeypatch):
    monkeypatch.setenv("MCP_ENABLED", "true")
    monkeypatch.setattr(auth_module, "database_request", database_request)
    monkeypatch.setattr(auth_module, "call_loyalty_tier_mcp", lambda points: tool_response(points))
    calls = []
    def calculate(result):
        calls.append(result)
        return {"status": "verified", "model": "test-model", "result": result}
    monkeypatch.setattr(auth_module, "ai_loyalty_calculation", calculate)
    with auth_module.app.test_client() as client:
        login_session(client)
        response = client.post("/api/admin/mcp/loyalty-tier", json={"user_id": 2, "use_ai": True})
    assert response.status_code == 200
    assert calls == [tool_response()["result"]]
    assert response.json["ai_calculation"]["status"] == "verified"


@pytest.mark.parametrize("value", ["true", 1, None, {}])
def test_progress_rejects_invalid_ai_flag(auth_module, monkeypatch, value):
    monkeypatch.setattr(auth_module, "database_request", database_request)
    with auth_module.app.test_client() as client:
        login_session(client)
        response = client.post("/api/admin/mcp/loyalty-tier", json={"user_id": 2, "use_ai": value})
    assert response.status_code == 400
