"""HTTP route tests for Chufeng's backend MCP integration."""

from importlib import import_module

import pytest


mcp_controller = import_module(
    "student-Chufeng.backend.controllers.mcp_controller"
)
mcp_client_module = import_module(
    "student-Chufeng.backend.services.mcp_client"
)
MCPClientError = mcp_client_module.MCPClientError
MCPDisabledError = mcp_client_module.MCPDisabledError
MCPToolNotAllowedError = mcp_client_module.MCPToolNotAllowedError


TOOLS = [
    {
        "name": "chufeng_search_products",
        "title": "Search Product Catalogue",
        "description": "Search customer-visible products.",
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "annotations": {"readOnlyHint": True},
    }
]


class StubMCPClient:
    def __init__(self, *, tools=None, result=None, failure=None):
        self.tools = TOOLS if tools is None else tools
        self.result = result
        self.failure = failure
        self.calls = []

    def list_tools(self):
        if self.failure:
            raise self.failure
        return self.tools

    def call_tool(self, tool_name, arguments):
        self.calls.append((tool_name, arguments))
        if self.failure:
            raise self.failure
        return self.result


def _use_stub(monkeypatch, stub):
    monkeypatch.setattr(mcp_controller, "_create_client", lambda: stub)


def test_status_reports_connected_mcp(client, monkeypatch):
    _use_stub(monkeypatch, StubMCPClient())

    response = client.get("/api/chufeng/mcp/status")

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "enabled": True,
        "available": True,
        "tool_count": 1,
        "error": None,
    }


@pytest.mark.parametrize(
    ("failure", "expected_enabled", "expected_code"),
    [
        (MCPDisabledError(), False, "MCP_DISABLED"),
        (
            MCPClientError(
                "The MCP server is unavailable.",
                code="MCP_UNAVAILABLE",
                status_code=503,
            ),
            True,
            "MCP_UNAVAILABLE",
        ),
    ],
)
def test_status_reports_disabled_or_unavailable_mcp(
    client,
    monkeypatch,
    failure,
    expected_enabled,
    expected_code,
):
    _use_stub(monkeypatch, StubMCPClient(failure=failure))

    response = client.get("/api/chufeng/mcp/status")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["enabled"] is expected_enabled
    assert payload["available"] is False
    assert payload["tool_count"] == 0
    assert payload["error"]["code"] == expected_code


def test_tools_route_returns_allowlisted_definitions(client, monkeypatch):
    _use_stub(monkeypatch, StubMCPClient())

    response = client.get("/api/chufeng/mcp/tools")

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "tools": TOOLS,
        "count": 1,
        "error": None,
    }


def test_call_route_passes_valid_request_to_mcp_client(client, monkeypatch):
    result = {
        "success": True,
        "tool": "chufeng_check_product_stock",
        "result": {"available": True, "available_quantity": 20},
        "error": None,
    }
    stub = StubMCPClient(result=result)
    _use_stub(monkeypatch, stub)

    response = client.post(
        "/api/chufeng/mcp/tools/call",
        json={
            "tool": "chufeng_check_product_stock",
            "arguments": {"product_id": 11, "quantity": 2},
        },
    )

    assert response.status_code == 200
    assert response.get_json() == result
    assert stub.calls == [
        (
            "chufeng_check_product_stock",
            {"product_id": 11, "quantity": 2},
        )
    ]


@pytest.mark.parametrize(
    ("request_kwargs", "expected_message"),
    [
        ({}, "A JSON request body is required."),
        ({"json": {}}, "tool must be a non-empty string."),
        ({"json": {"tool": 123}}, "tool must be a non-empty string."),
        (
            {
                "json": {
                    "tool": "chufeng_search_products",
                    "arguments": [],
                }
            },
            "arguments must be an object.",
        ),
    ],
)
def test_call_route_rejects_invalid_http_input(
    client,
    monkeypatch,
    request_kwargs,
    expected_message,
):
    monkeypatch.setattr(
        mcp_controller,
        "_create_client",
        lambda: pytest.fail("invalid input must not create an MCP client"),
    )

    response = client.post(
        "/api/chufeng/mcp/tools/call",
        **request_kwargs,
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == {
        "code": "INVALID_ARGUMENT",
        "message": expected_message,
    }


def test_call_route_maps_forbidden_tool_without_leaking_details(client, monkeypatch):
    stub = StubMCPClient(
        failure=MCPToolNotAllowedError("howard_delete_everything")
    )
    _use_stub(monkeypatch, stub)

    response = client.post(
        "/api/chufeng/mcp/tools/call",
        json={"tool": "howard_delete_everything", "arguments": {}},
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "TOOL_NOT_ALLOWED"


def test_call_route_maps_tool_business_failure_to_http_status(client, monkeypatch):
    result = {
        "success": False,
        "tool": "chufeng_get_product_details",
        "result": None,
        "error": {
            "code": "RECORD_NOT_FOUND",
            "message": "The requested product was not found.",
        },
    }
    _use_stub(monkeypatch, StubMCPClient(result=result))

    response = client.post(
        "/api/chufeng/mcp/tools/call",
        json={
            "tool": "chufeng_get_product_details",
            "arguments": {"product_id": 999},
        },
    )

    assert response.status_code == 404
    assert response.get_json() == result


def test_unexpected_controller_failure_is_safe(client, monkeypatch):
    _use_stub(monkeypatch, StubMCPClient(failure=RuntimeError("private detail")))

    response = client.get("/api/chufeng/mcp/tools")

    assert response.status_code == 500
    assert response.get_json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "The MCP request could not be completed.",
        }
    }
    assert "private detail" not in response.get_data(as_text=True)


def test_mcp_routes_support_trusted_frontend_cors(client, monkeypatch):
    _use_stub(monkeypatch, StubMCPClient())

    response = client.options(
        "/api/chufeng/mcp/tools/call",
        headers={"Origin": "http://localhost:8001"},
    )

    assert response.status_code == 204
    assert response.headers["Access-Control-Allow-Origin"] == (
        "http://localhost:8001"
    )
    assert "POST" in response.headers["Access-Control-Allow-Methods"]
