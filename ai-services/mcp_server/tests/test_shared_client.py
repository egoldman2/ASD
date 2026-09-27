"""Feature boundaries and per-operation credentials over the real MCP protocol."""

import asyncio
from typing import Any

import httpx
import pytest
from mcp.server.fastmcp import Context, FastMCP

from mcp_server.server import create_server
from shared.mcp_client import (
    MCPClient,
    MCPClientError,
    MCPClientSettings,
    MCPConfigurationError,
    MCPDisabledError,
    MCPToolNotAllowedError,
)


def settings(*, enabled=True):
    return MCPClientSettings(enabled, "http://127.0.0.1:8765/mcp", 2.0)


def test_feature_allowlists_and_request_credentials_are_isolated():
    async def exercise():
        server = FastMCP("Client boundary test", stateless_http=True, json_response=True)

        @server.tool()
        async def support_context(ctx: Context) -> dict[str, Any]:
            await asyncio.sleep(0)  # Interleave requests from separate callers.
            return {"cookie": ctx.request_context.request.headers.get("cookie")}

        @server.tool()
        def catalogue_search() -> dict[str, Any]:
            return {"products": []}

        app = server.streamable_http_app()

        def factory():
            return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), timeout=2)

        support = MCPClient(
            settings(), allowed_tools=frozenset({"support_context"}),
            http_client_factory=factory,
        )
        catalogue = MCPClient(
            settings(), allowed_tools=frozenset({"catalogue_search"}),
            http_client_factory=factory,
        )
        first_headers = {"Cookie": "ethan_session=test-staff-one"}
        second_headers = {"Cookie": "ethan_session=test-staff-two"}

        async with app.router.lifespan_context(app):
            listed = await support.alist_tools(request_headers=first_headers)
            assert [tool["name"] for tool in listed] == ["support_context"]
            assert [tool["name"] for tool in await catalogue.alist_tools()] == ["catalogue_search"]
            first, second = await asyncio.gather(
                support.acall_tool("support_context", request_headers=first_headers),
                support.acall_tool("support_context", request_headers=second_headers),
            )
            anonymous = await support.acall_tool("support_context")
            assert first == {"cookie": "ethan_session=test-staff-one"}
            assert second == {"cookie": "ethan_session=test-staff-two"}
            assert anonymous == {"cookie": None}
            assert first_headers == {"Cookie": "ethan_session=test-staff-one"}
            assert second_headers == {"Cookie": "ethan_session=test-staff-two"}
            with pytest.raises(MCPToolNotAllowedError):
                await catalogue.acall_tool("support_context")

    asyncio.run(exercise())


def test_shared_client_denies_disabled_and_unlisted_calls_before_connecting():
    def must_not_connect():
        pytest.fail("Invalid/disabled calls must not open a connection")

    client = MCPClient(settings(), allowed_tools=frozenset(), http_client_factory=must_not_connect)
    with pytest.raises(MCPToolNotAllowedError):
        client.call_tool("support_context")
    disabled = MCPClient(
        settings(enabled=False), allowed_tools=frozenset({"support_context"}),
        http_client_factory=must_not_connect,
    )
    with pytest.raises(MCPDisabledError):
        disabled.call_tool("support_context")
    with pytest.raises(MCPDisabledError):
        disabled.list_tools()


def test_sync_wrappers_forward_headers_without_retaining_them(monkeypatch):
    observed = []

    async def list_tools(self, *, request_headers=None):
        observed.append(request_headers)
        return []

    async def call_tool(self, tool_name, arguments=None, *, request_headers=None):
        observed.append(request_headers)
        return {"tool": tool_name}

    monkeypatch.setattr(MCPClient, "alist_tools", list_tools)
    monkeypatch.setattr(MCPClient, "acall_tool", call_tool)
    client = MCPClient(settings(), allowed_tools=frozenset({"support_context"}))
    headers = {"Cookie": "ethan_session=test-staff"}
    assert client.list_tools(request_headers=headers) == []
    assert client.call_tool("support_context", request_headers=headers) == {"tool": "support_context"}
    client.call_tool("support_context")
    assert observed == [headers, headers, None]


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_timeout_must_be_finite(monkeypatch, value):
    monkeypatch.setenv("MCP_CLIENT_TIMEOUT_SECONDS", value)
    with pytest.raises(MCPConfigurationError):
        MCPClientSettings.from_environment()


def test_safe_connection_errors_do_not_expose_credentials():
    def unavailable():
        raise httpx.ConnectError("Cookie: ethan_session=private-test-value")

    client = MCPClient(
        settings(), allowed_tools=frozenset({"support_context"}), http_client_factory=unavailable,
    )
    with pytest.raises(MCPClientError) as error:
        client.call_tool("support_context", request_headers={"Cookie": "ethan_session=private-test-value"})
    assert error.value.to_dict() == {
        "error": {"code": "MCP_UNAVAILABLE", "message": "The MCP server is unavailable."},
    }


def test_health_counts_tools_added_by_other_features():
    async def exercise():
        server = create_server()

        @server.tool()
        def another_feature_tool() -> dict:
            return {"success": True}

        app = server.streamable_http_app()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client:
            response = await client.get("http://127.0.0.1:8765/health")
        assert response.json()["registered_tools"] == 5

    asyncio.run(exercise())
