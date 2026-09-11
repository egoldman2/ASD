"""Tests for Chufeng's backend-side MCP protocol adapter."""

import asyncio
from importlib import import_module

import httpx
import pytest

from mcp_server.server import create_server


mcp_client_module = import_module(
    "student-Chufeng.backend.services.mcp_client"
)
CHUFENG_ALLOWED_TOOLS = mcp_client_module.CHUFENG_ALLOWED_TOOLS
ChufengMCPClient = mcp_client_module.ChufengMCPClient
MCPClientError = mcp_client_module.MCPClientError
MCPClientSettings = mcp_client_module.MCPClientSettings
MCPConfigurationError = mcp_client_module.MCPConfigurationError
MCPDisabledError = mcp_client_module.MCPDisabledError
MCPToolNotAllowedError = mcp_client_module.MCPToolNotAllowedError


def _settings(*, enabled=True):
    return MCPClientSettings(
        enabled=enabled,
        server_url="http://127.0.0.1:8765/mcp",
        timeout_seconds=2.0,
    )


def test_settings_load_environment(monkeypatch):
    monkeypatch.setenv("MCP_ENABLED", "yes")
    monkeypatch.setenv("MCP_SERVER_URL", "http://localhost:9000/custom/")
    monkeypatch.setenv("MCP_CLIENT_TIMEOUT_SECONDS", "3.5")

    settings = MCPClientSettings.from_environment()

    assert settings.enabled is True
    assert settings.server_url == "http://localhost:9000/custom"
    assert settings.timeout_seconds == 3.5


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("MCP_ENABLED", "sometimes"),
        ("MCP_SERVER_URL", "localhost:8765/mcp"),
        ("MCP_CLIENT_TIMEOUT_SECONDS", "0"),
        ("MCP_CLIENT_TIMEOUT_SECONDS", "slow"),
    ],
)
def test_invalid_settings_fail_early(monkeypatch, setting, value):
    monkeypatch.setenv(setting, value)

    with pytest.raises(MCPConfigurationError):
        MCPClientSettings.from_environment()


def test_disabled_client_rejects_calls_before_connecting():
    client = ChufengMCPClient(
        _settings(enabled=False),
        http_client_factory=lambda: pytest.fail("must not connect"),
    )

    with pytest.raises(MCPDisabledError) as failure:
        client.list_tools()

    assert failure.value.code == "MCP_DISABLED"
    assert failure.value.status_code == 503


def test_tool_allowlist_and_arguments_are_checked_before_connecting():
    client = ChufengMCPClient(
        _settings(),
        http_client_factory=lambda: pytest.fail("must not connect"),
    )

    with pytest.raises(MCPToolNotAllowedError) as forbidden:
        client.call_tool("howard_delete_everything", {})
    with pytest.raises(MCPClientError) as invalid_arguments:
        client.call_tool("chufeng_search_products", ["not", "an", "object"])

    assert forbidden.value.code == "TOOL_NOT_ALLOWED"
    assert forbidden.value.status_code == 403
    assert invalid_arguments.value.code == "INVALID_ARGUMENT"
    assert invalid_arguments.value.status_code == 400


def test_async_client_lists_and_calls_tools_over_mcp(
    database_api_url,
    monkeypatch,
):
    monkeypatch.setenv("PRODUCT_DATABASE_API_URL", database_api_url)

    async def exercise_client():
        server = create_server()
        app = server.streamable_http_app()
        base_url = "http://127.0.0.1:8765"

        def http_client_factory():
            return httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url=base_url,
                timeout=2.0,
            )

        client = ChufengMCPClient(
            _settings(),
            http_client_factory=http_client_factory,
        )

        async with app.router.lifespan_context(app):
            tools = await client.alist_tools()
            successful = await client.acall_tool(
                "chufeng_get_product_details",
                {"product_id": 11},
            )
            business_failure = await client.acall_tool(
                "chufeng_search_products",
                {"limit": 0},
            )

        assert {tool["name"] for tool in tools} == CHUFENG_ALLOWED_TOOLS
        assert all(tool["annotations"]["readOnlyHint"] for tool in tools)
        assert successful["success"] is True
        assert successful["result"]["product"]["name"] == "Mechanical Keyboard"
        assert business_failure["success"] is False
        assert business_failure["error"]["code"] == "INVALID_ARGUMENT"

    asyncio.run(exercise_client())


def test_connection_failure_is_converted_to_safe_error():
    def unavailable_factory():
        raise httpx.ConnectError("private socket information")

    client = ChufengMCPClient(
        _settings(),
        http_client_factory=unavailable_factory,
    )

    with pytest.raises(MCPClientError) as failure:
        client.list_tools()

    assert failure.value.code == "MCP_UNAVAILABLE"
    assert failure.value.status_code == 503
    assert str(failure.value) == "The MCP server is unavailable."
    assert "private socket information" not in str(failure.value)


def test_sync_wrapper_requires_async_method_inside_event_loop():
    client = ChufengMCPClient(_settings())

    async def call_sync_method():
        with pytest.raises(MCPClientError) as failure:
            client.list_tools()
        assert failure.value.code == "MCP_ASYNC_CONTEXT"

    asyncio.run(call_sync_method())
