"""Protocol-level tests for the shared Streamable HTTP MCP server."""

import asyncio

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from mcp_server.server import (
    REGISTERED_CHUFENG_TOOLS,
    SERVER_NAME,
    create_server,
)


def test_streamable_http_initialise_list_and_call(
    live_product_database_api,
    monkeypatch,
):
    monkeypatch.setenv("PRODUCT_DATABASE_API_URL", live_product_database_api)

    async def exercise_protocol():
        server = create_server()
        app = server.streamable_http_app()
        base_url = "http://127.0.0.1:8765"

        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url=base_url,
            ) as http_client:
                async with streamable_http_client(
                    f"{base_url}/mcp",
                    http_client=http_client,
                ) as (read_stream, write_stream, _):
                    async with ClientSession(read_stream, write_stream) as session:
                        initialised = await session.initialize()
                        assert initialised.serverInfo.name == SERVER_NAME

                        listed = await session.list_tools()
                        tools = {tool.name: tool for tool in listed.tools}
                        assert set(tools) == set(REGISTERED_CHUFENG_TOOLS)
                        for tool in tools.values():
                            assert tool.annotations.readOnlyHint is True
                            assert tool.annotations.destructiveHint is False
                            assert tool.annotations.idempotentHint is True
                            assert tool.annotations.openWorldHint is False
                            assert tool.outputSchema is not None

                        called = await session.call_tool(
                            "chufeng_search_products",
                            {"limit": 0},
                        )
                        assert called.isError is False
                        assert called.structuredContent["success"] is False
                        assert (
                            called.structuredContent["error"]["code"]
                            == "INVALID_ARGUMENT"
                        )

                        successful = await session.call_tool(
                            "chufeng_search_products",
                            {
                                "query": "Keyboard",
                                "category": "Electronics",
                                "max_price": 120,
                            },
                        )
                        assert successful.isError is False
                        assert successful.structuredContent["success"] is True
                        products = successful.structuredContent["result"]["products"]
                        assert [product["name"] for product in products] == [
                            "Mechanical Keyboard"
                        ]
                        assert "unit_cost" not in products[0]

    asyncio.run(exercise_protocol())


def test_health_route_reports_transport_and_tool_count():
    async def request_health():
        server = create_server()
        app = server.streamable_http_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://127.0.0.1:8765",
        ) as client:
            response = await client.get("/health")

        assert response.status_code == 200
        assert response.json() == {
            "status": "healthy",
            "service": "asd-marketplace-mcp",
            "transport": "streamable-http",
            "mcp_path": "/mcp",
            "registered_tools": 4,
        }

    asyncio.run(request_health())
