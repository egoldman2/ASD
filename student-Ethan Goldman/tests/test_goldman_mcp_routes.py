"""Frontend-facing support routes through a real HTTP MCP server."""

from hashlib import sha256
from importlib import import_module

import pytest
import requests

from shared.mcp_client import MCPClient

adapter = import_module("student-Ethan Goldman.support_backend.mcp_client")



def test_staff_routes_discover_and_call_all_four_tools(live_mcp):
    stack = live_mcp
    admin = stack.admin()
    base = stack.backend.url + "/api/support/admin/mcp"
    before = sha256(stack.database_path.read_bytes()).hexdigest()
    discovered = admin.get(base + "/tools", timeout=10)
    assert discovered.status_code == 200
    assert {tool["name"] for tool in discovered.json()["tools"]} == adapter.GOLDMAN_ALLOWED_TOOLS
    for tool, arguments in ((adapter.SEARCH_TICKETS, {"limit": 1}),
                            (adapter.GET_TICKET_CONTEXT, {"ticket_id": 2002, "message_limit": 1}),
                            (adapter.GET_QUEUE_SUMMARY, {}),
                            (adapter.GET_TICKETS_NEEDING_ATTENTION, {"limit": 1})):
        response = admin.post(base + "/tools/call", json={"tool": tool, "arguments": arguments},
                              headers=stack.origin_headers, timeout=10)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["success"] is True and result["tool"] == tool
        assert result["metadata"]["read_only"] is True
        assert "customer_email_snapshot" not in response.text and "author_name" not in response.text
        assert "ethan_session" not in response.text
    assert sha256(stack.database_path.read_bytes()).hexdigest() == before
    missing = admin.post(base + "/tools/call", json={"tool": adapter.GET_TICKET_CONTEXT,
                                                    "arguments": {"ticket_id": 999999}},
                         headers=stack.origin_headers, timeout=10)
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "RECORD_NOT_FOUND"


def test_denied_and_invalid_routes_do_not_contact_mcp(support_stack, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Denied or invalid requests must not contact MCP")

    monkeypatch.setattr(MCPClient, "list_tools", forbidden)
    monkeypatch.setattr(MCPClient, "call_tool", forbidden)
    base = support_stack.backend.url + "/api/support/admin/mcp"
    headers = support_stack.origin_headers
    payload = {"tool": adapter.GET_QUEUE_SUMMARY}
    assert requests.get(base + "/tools", timeout=10).status_code == 401
    assert requests.post(base + "/tools/call", json=payload, headers=headers, timeout=10).status_code == 401
    customer = support_stack.customer()
    assert customer.get(base + "/tools", timeout=10).status_code == 403
    assert customer.post(base + "/tools/call", json=payload, headers=headers, timeout=10).status_code == 403
    admin = support_stack.admin()
    assert admin.post(base + "/tools/call", json=payload, timeout=10).status_code == 403
    invalid_payloads = (
        ({"tool": "chufeng_search_products"}, 403),
        ({"tool": "invented"}, 403),
        ({"tool": adapter.GET_QUEUE_SUMMARY, "role": "admin"}, 400),
        ({"tool": adapter.GET_QUEUE_SUMMARY, "arguments": {"ethan_session": "fake"}}, 400),
        ({"tool": adapter.GET_QUEUE_SUMMARY, "arguments": []}, 400),
        ({"tool": adapter.GET_QUEUE_SUMMARY, "arguments": None}, 400),
        ({"tool": adapter.GET_TICKET_CONTEXT}, 400),
        ({"tool": adapter.GET_TICKET_CONTEXT, "arguments": {"ticket_id": True}}, 400),
        ({"tool": adapter.SEARCH_TICKETS, "arguments": {"limit": 51}}, 400),
        ({"tool": adapter.SEARCH_TICKETS, "arguments": {"status": "wrong"}}, 400),
        ({"tool": adapter.GET_TICKETS_NEEDING_ATTENTION, "arguments": {"inactive_hours": 721}}, 400),
        ({"tool": adapter.GET_QUEUE_SUMMARY, "arguments": {"category": "x" * 5000}}, 413),
    )
    for body, status in invalid_payloads:
        response = admin.post(base + "/tools/call", json=body, headers=headers, timeout=10)
        assert response.status_code == status, response.text
    assert admin.post(base + "/tools/call", data="not JSON", headers=headers, timeout=10).status_code == 400


def test_disabled_mcp_returns_before_opening_transport(support_stack, monkeypatch):
    monkeypatch.setenv("MCP_ENABLED", "false")

    def forbidden(*args, **kwargs):
        pytest.fail("Disabled mode must not open MCP transport")

    monkeypatch.setattr(MCPClient, "_default_http_client", forbidden)
    admin = support_stack.admin()
    base = support_stack.backend.url + "/api/support/admin/mcp"
    discovered = admin.get(base + "/tools", timeout=10)
    called = admin.post(base + "/tools/call", json={"tool": adapter.GET_QUEUE_SUMMARY},
                        headers=support_stack.origin_headers, timeout=10)
    for response in (discovered, called):
        assert response.status_code == 503 and response.json()["error"]["code"] == "MCP_DISABLED"
    assert admin.get(support_stack.backend.url + "/api/support/admin/tickets", timeout=10).status_code == 200


def test_unavailable_mcp_returns_safe_error(support_stack, monkeypatch):
    monkeypatch.setenv("MCP_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_URL", "http://127.0.0.1:1/mcp")
    monkeypatch.setenv("MCP_CLIENT_TIMEOUT_SECONDS", "0.2")
    admin = support_stack.admin()
    response = admin.post(support_stack.backend.url + "/api/support/admin/mcp/tools/call",
                          json={"tool": adapter.GET_QUEUE_SUMMARY},
                          headers=support_stack.origin_headers, timeout=10)
    assert response.status_code == 503 and response.json()["error"]["code"] == "MCP_UNAVAILABLE"
    assert admin.cookies.get("ethan_session") not in response.text


@pytest.mark.parametrize("result", [{}, {"success": True, "tool": "other", "result": {}, "error": None},
                                    {"success": False, "tool": adapter.GET_QUEUE_SUMMARY,
                                     "result": None, "error": {"code": []}}])
def test_malformed_mcp_results_are_rejected(result):
    from shared.mcp_client import MCPClientError
    with pytest.raises(MCPClientError, match="invalid response"):
        adapter.validate_tool_response(adapter.GET_QUEUE_SUMMARY, result)
