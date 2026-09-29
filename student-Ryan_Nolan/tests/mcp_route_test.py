import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_status_when_disabled_is_not_fatal(client, monkeypatch):
    monkeypatch.setenv("MCP_ENABLED", "false")
    response = client.get("/api/inventory/mcp/status")
    body = response.get_json()
    assert response.status_code == 200
    assert body["enabled"] is False
    assert body["error"]["code"] == "MCP_DISABLED"


def test_call_when_disabled_returns_mcp_disabled(client, monkeypatch):
    monkeypatch.setenv("MCP_ENABLED", "false")
    response = client.post(
        "/api/inventory/mcp/tools/call",
        json={"tool": "ryan_get_low_stock_items", "arguments": {"limit": 5}},
    )
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "MCP_DISABLED"


def test_header_can_switch_mcp_off_per_request(client):
    response = client.post(
        "/api/inventory/mcp/tools/call",
        headers={"X-MCP-Mode": "off"},
        json={"tool": "ryan_get_low_stock_items", "arguments": {}},
    )
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "MCP_DISABLED"


def test_tool_outside_allowlist_is_rejected(client, monkeypatch):
    monkeypatch.setenv("MCP_ENABLED", "true")
    response = client.post(
        "/api/inventory/mcp/tools/call",
        json={"tool": "chufeng_search_products", "arguments": {}},
    )
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "TOOL_NOT_ALLOWED"


def test_missing_tool_is_invalid(client):
    response = client.post("/api/inventory/mcp/tools/call", json={})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_ARGUMENT"