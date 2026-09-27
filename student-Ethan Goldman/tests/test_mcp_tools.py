"""Support tools over real MCP, auth and database APIs, using disposable data."""

import asyncio
from hashlib import sha256
from importlib import import_module
from pathlib import Path
import sys

import httpx
import pytest
import requests

sys.path.insert(0, str(Path(__file__).parents[2] / "ai-services"))
from mcp_server.server import REGISTERED_GOLDMAN_TOOLS, create_server
from shared.mcp_client import MCPClient, MCPClientSettings

database = import_module("student-Ethan Goldman.database_service.database")


def seed_ticket(stack, *, messages=0, subject="Bounded case Jane Hidden"):
    ticket = database.create_ticket({
        "customer_user_id": "2", "customer_name_snapshot": "Jane Hidden",
        "customer_email_snapshot": "jane.private@example.test", "subject": subject,
        "message": "Jane Hidden: jane.private@example.test, phone 0412 345 678",
    }, "2026-09-27T00:00:00Z", stack.database_path)
    for index in range(messages):
        database.create_ticket_message(ticket["id"], {
            "sender_role": "customer", "author_name": "Jane Hidden",
            "message": f"Message {index:03}: Jane Hidden jane.private@example.test 0412 345 678",
        }, f"2026-09-27T00:{index // 60:02}:{index % 60:02}Z", stack.database_path)
    database.update_ticket(ticket["id"], {"assigned_to": "Ethan Goldman"},
                           "2026-09-27T01:00:00Z", stack.database_path)
    return ticket["id"]


def test_bounded_reads_page_in_sql_and_redact_identity(support_stack, monkeypatch):
    ticket_id = seed_ticket(support_stack, messages=55)
    for index in range(54):
        seed_ticket(support_stack, subject=f"Bounded case {index:03}")
    queries = []
    connect = database.get_database_connection

    def traced_connection(path=None):
        connection = connect(path)
        connection.set_trace_callback(queries.append)
        return connection

    monkeypatch.setattr(database, "get_database_connection", traced_connection)
    before = sha256(support_stack.database_path.read_bytes()).hexdigest()
    admin = support_stack.admin()
    endpoint = support_stack.backend.url + "/api/support/admin/tool-data/tickets"
    response = admin.get(endpoint, params={"search": "Bounded case", "limit": 50}, timeout=10)
    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 55 and len(page["tickets"]) == 50
    assert page["next_offset"] == 50 and page["truncated"] is True
    assert all("messages" not in ticket for ticket in page["tickets"])
    last = admin.get(endpoint, params={"search": "Bounded case", "limit": 50, "offset": 50}, timeout=10).json()
    assert len(last["tickets"]) == 5 and last["next_offset"] is None
    assert {ticket["id"] for ticket in page["tickets"]}.isdisjoint(ticket["id"] for ticket in last["tickets"])
    result = admin.get(f"{endpoint}/{ticket_id}", params={"message_limit": 3}, timeout=10).json()
    assert result["message_count"] == 56 and result["messages_truncated"] is True
    assert [message["message"].split(":")[0] for message in result["messages"]] == ["Message 052", "Message 053", "Message 054"]
    assert result["assigned_to"] == "Ethan Goldman"
    for forbidden in ("Jane Hidden", "jane.private", "0412", "customer_user_id", "author_name", "customer_email_snapshot"):
        assert forbidden not in str(result)
        assert forbidden not in str(page)
    assert any("LIMIT 50 OFFSET 0" in query for query in queries)
    assert any("LIMIT 3" in query and "support_ticket_messages" in query for query in queries)
    assert not any("WHERE ticket_id IN" in query for query in queries)
    assert sha256(support_stack.database_path.read_bytes()).hexdigest() == before


def test_tool_read_routes_reject_access_and_invalid_queries(support_stack):
    ticket_id = seed_ticket(support_stack)
    endpoint = support_stack.backend.url + "/api/support/admin/tool-data/tickets"
    assert requests.get(endpoint, timeout=10).status_code == 401
    customer = support_stack.customer()
    assert customer.get(endpoint, timeout=10).status_code == 403
    assert customer.get(f"{endpoint}/{ticket_id}", timeout=10).status_code == 403
    admin = support_stack.admin()
    for query in ({"limit": 0}, {"limit": 51}, {"offset": -1}, {"offset": 10001},
                  {"status": "invalid"}, {"owner_user_id": "2"}, {"search": "x" * 161},
                  [("limit", 1), ("limit", 2)], {"limit": "1.5"}):
        assert admin.get(endpoint, params=query, timeout=10).status_code == 400
    for query in ({"message_limit": 0}, {"message_limit": 51}, {"customer_user_id": "2"}):
        assert admin.get(f"{endpoint}/{ticket_id}", params=query, timeout=10).status_code == 400
    assert admin.get(f"{endpoint}/999999", timeout=10).status_code == 404
    assert admin.get(f"{endpoint}/0", timeout=10).status_code == 400
    internal = support_stack.database.url + "/api/tool-data/tickets"
    for query in ({"limit": 51}, {"offset": 10001}, {"owner_user_id": "2"}):
        assert requests.get(internal, params=query, timeout=10).status_code == 400
    seed_ticket(support_stack, subject="Literal % symbol")
    literal = admin.get(endpoint, params={"search": "%"}, timeout=10).json()
    assert literal["total"] == 1


def test_support_tools_use_real_protocol_and_revalidate_sessions(support_stack, monkeypatch):
    ticket_id = seed_ticket(support_stack, messages=4)
    monkeypatch.setenv("MCP_SUPPORT_API_URL", support_stack.backend.url)
    admin = support_stack.admin()
    customer = support_stack.customer()
    before = sha256(support_stack.database_path.read_bytes()).hexdigest()

    async def exercise():
        server = create_server()
        app = server.streamable_http_app()
        client = MCPClient(
            MCPClientSettings(True, "http://127.0.0.1:8765/mcp", 10),
            allowed_tools=frozenset(REGISTERED_GOLDMAN_TOOLS),
            http_client_factory=lambda: httpx.AsyncClient(transport=httpx.ASGITransport(app=app)),
        )
        headers = {"Cookie": "ethan_session=" + admin.cookies.get("ethan_session")}
        customer_headers = {"Cookie": "ethan_session=" + customer.cookies.get("ethan_session")}
        async with app.router.lifespan_context(app):
            tools = await client.alist_tools()
            assert {tool["name"] for tool in tools} == set(REGISTERED_GOLDMAN_TOOLS)
            assert all("ctx" not in tool["input_schema"]["properties"] for tool in tools)
            for name, arguments in (
                ("ethan_goldman_search_tickets", {"search": "Bounded case", "limit": 1}),
                ("ethan_goldman_get_ticket_context", {"ticket_id": ticket_id, "message_limit": 2}),
            ):
                result = await client.acall_tool(name, arguments, request_headers=headers)
                assert result["success"] is True and result["metadata"]["read_only"] is True
                assert "Jane Hidden" not in str(result)
                assert (await client.acall_tool(name, arguments))["error"]["code"] == "AUTHENTICATION_REQUIRED"
                assert (await client.acall_tool(name, arguments, request_headers=customer_headers))["error"]["code"] == "TOOL_NOT_ALLOWED"
                expired = await client.acall_tool(name, arguments, request_headers={"Cookie": "ethan_session=expired"})
                assert expired["error"]["code"] == "AUTHENTICATION_REQUIRED"
            for name, arguments, code in (
                ("ethan_goldman_search_tickets", {"limit": 0}, "INVALID_ARGUMENT"),
                ("ethan_goldman_search_tickets", {"priority": "invalid"}, "INVALID_ARGUMENT"),
                ("ethan_goldman_get_ticket_context", {"ticket_id": -1}, "INVALID_ARGUMENT"),
                ("ethan_goldman_get_ticket_context", {"ticket_id": 999999}, "RECORD_NOT_FOUND"),
            ):
                result = await client.acall_tool(name, arguments, request_headers=headers)
                assert result["success"] is False and result["error"]["code"] == code
            # A boolean must not be silently converted to ticket ID 1 by the SDK.
            from shared.mcp_client import MCPClientError
            with pytest.raises(MCPClientError):
                await client.acall_tool("ethan_goldman_get_ticket_context", {"ticket_id": True}, request_headers=headers)
            monkeypatch.setenv("MCP_SUPPORT_API_URL", "http://127.0.0.1:1")
            result = await client.acall_tool("ethan_goldman_search_tickets", request_headers=headers)
            assert result["error"]["code"] == "UPSTREAM_UNAVAILABLE"

    asyncio.run(exercise())
    assert sha256(support_stack.database_path.read_bytes()).hexdigest() == before
