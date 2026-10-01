"""Read-only history routing, authentication and untrusted-output checks."""

import copy
import importlib.util
from pathlib import Path

import pytest


TOOL = "ethan_ting_get_loyalty_history"
CHAT = "/api/admin/ai/customer-insight"
HISTORY = "/api/admin/mcp/tool-data/loyalty/2/history"
QUICK_HISTORY = "/api/admin/mcp/loyalty-history"
CUSTOMER = {"id": 2, "role": "customer", "full_name": "Demo Customer", "email": "customer@asd.local", "is_active": 1}
ROW = {"id": 4, "user_id": 2, "points_change": 50, "reason": "Purchase reward", "created_at": "2026-10-01 10:00:00", "created_by_admin_name": "Private Admin"}


@pytest.fixture
def module(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "backend" / "app.py"
    spec = importlib.util.spec_from_file_location("history_chat_app", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.config.update(TESTING=True, SECRET_KEY="history-test-key")
    monkeypatch.setenv("MCP_ENABLED", "true")
    monkeypatch.setenv("AI_MODE_ENABLED", "true")
    calls = []

    def database(path, method="GET", payload=None):
        calls.append((method, path))
        assert method == "GET", "History must never change records"
        if path == "/internal/users/1":
            return {"user": {"id": 1, "role": "admin", "is_active": 1, "email": "admin@asd.local", "full_name": "Admin"}}
        if path == "/internal/users?role=customer":
            return {"users": [dict(CUSTOMER)]}
        if path == "/internal/users/2":
            return {"user": dict(CUSTOMER)}
        if path.startswith("/internal/loyalty/2/transactions?limit="):
            return {"count": 1, "transactions": [dict(ROW)]}
        raise AssertionError(path)

    module.database_calls = calls
    monkeypatch.setattr(module, "database_request", database)
    monkeypatch.setattr(module, "ollama_chat", lambda *args: pytest.fail("History must not call Ollama"))
    monkeypatch.setattr(module, "call_loyalty_history_mcp", lambda customer_id, limit: response(customer_id, limit))
    return module


def response(customer_id=2, limit=5):
    return {"success": True, "tool": TOOL, "metadata": {"read_only": True},
            "result": {"customer_id": customer_id, "limit": limit, "count": 1, "transactions": [dict(ROW)]}}


def sign_in(client, role="admin"):
    with client.session_transaction() as session:
        session["user"] = {"id": 1, "role": role, "email": "admin@asd.local", "full_name": "Admin"}


def test_selected_history_works_without_ai_mode(module, monkeypatch):
    monkeypatch.setenv("AI_MODE_ENABLED", "false")
    with module.app.test_client() as client:
        sign_in(client)
        result = client.post(QUICK_HISTORY, json={"user_id": 2, "limit": 5})
    assert result.status_code == 200
    assert result.get_json()["history"]["customer_id"] == 2
    assert result.get_json()["read_only"] is True


@pytest.mark.parametrize("body", [{}, {"user_id": True}, {"user_id": 0}, {"user_id": "2"}, {"user_id": 2147483648},
                                   {"user_id": 2, "limit": True}, {"user_id": 2, "limit": 0}, {"user_id": 2, "limit": 21},
                                   {"user_id": 2, "question": "untrusted"}])
def test_selected_history_rejects_invalid_arguments(module, monkeypatch, body):
    monkeypatch.setattr(module, "call_loyalty_history_mcp", lambda *args: pytest.fail("Invalid arguments must not reach MCP"))
    with module.app.test_client() as client:
        sign_in(client)
        assert client.post(QUICK_HISTORY, json=body).status_code == 400


def test_selected_history_access_and_disabled_mode(module, monkeypatch):
    with module.app.test_client() as client:
        assert client.post(QUICK_HISTORY, json={"user_id": 2}).status_code == 401
        sign_in(client, "customer")
        assert client.post(QUICK_HISTORY, json={"user_id": 2}).status_code == 403
        sign_in(client)
        monkeypatch.setenv("MCP_ENABLED", "false")
        assert client.post(QUICK_HISTORY, json={"user_id": 2}).status_code == 503


@pytest.mark.parametrize("path,method", [(CHAT, "post"), (HISTORY, "get")])
def test_history_requires_admin(module, path, method):
    with module.app.test_client() as client:
        assert getattr(client, method)(path, json={"question": "Show point history for Customer #2"}).status_code == 401
        sign_in(client, "customer")
        assert getattr(client, method)(path, json={"question": "Show point history for Customer #2"}).status_code == 403


@pytest.mark.parametrize("role,active", [("customer", 1), ("admin", 0)])
def test_history_rechecks_current_admin_role(module, monkeypatch, role, active):
    monkeypatch.setattr(module, "database_request", lambda *args: {"user": {"id": 1, "role": role, "is_active": active}})
    with module.app.test_client() as client:
        sign_in(client)
        assert client.post(CHAT, json={"question": "Show point history for Customer #2"}).status_code in (401, 403)


@pytest.mark.parametrize("target", ["Customer #2", "customer 2", "customer@asd.local", "Demo Customer"])
@pytest.mark.parametrize("limit", [1, 5, 20])
def test_history_resolves_one_customer_and_validates_rows(module, target, limit):
    with module.app.test_client() as client:
        sign_in(client)
        result = client.post(CHAT, json={"question": f"Show the last {limit} point changes for {target}"})
    assert result.status_code == 200
    data = result.get_json()
    assert data["source"] == "mcp" and data["read_only"] is True
    assert data["history"]["limit"] == limit
    assert data["history"]["transactions"][0]["points_change"] == 50
    assert "Private Admin" not in result.get_data(as_text=True)
    assert all(method == "GET" for method, _ in module.database_calls)


@pytest.mark.parametrize("target", ["", "Customer #99", "unknown@example.test", "Customer #2 and Customer #99", "customer@asd.local and unknown@example.test"])
def test_unknown_or_multiple_identifiers_need_clarification(module, target, monkeypatch):
    monkeypatch.setattr(module, "call_loyalty_history_mcp", lambda *args: pytest.fail("No unambiguous customer"))
    with module.app.test_client() as client:
        sign_in(client)
        result = client.post(CHAT, json={"question": f"Show point history for {target}"})
    assert result.status_code == 200
    assert result.get_json()["clarification_required"] is True
    assert "history" not in result.get_json()


def test_duplicate_customer_names_need_clarification(module, monkeypatch):
    original = module.database_request
    monkeypatch.setattr(module, "database_request", lambda path, **kw: {"users": [CUSTOMER, {**CUSTOMER, "id": 3, "email": "other@asd.local"}]} if "?role=" in path else original(path, **kw))
    with module.app.test_client() as client:
        sign_in(client)
        result = client.post(CHAT, json={"question": "Show point history for Demo Customer"})
    assert result.get_json()["clarification_required"] is True
    assert "More than one" in result.get_json()["answer"]


@pytest.mark.parametrize("limit", [-1, 0, 1.5, 21, 999])
def test_chat_rejects_unbounded_history(module, limit):
    with module.app.test_client() as client:
        sign_in(client)
        assert client.post(CHAT, json={"question": f"Show last {limit} point changes for Customer #2"}).status_code == 400


@pytest.mark.parametrize("limit", ["0", "21", "no", "1.5", "-1", "1_0"])
def test_data_endpoint_rejects_bad_limit(module, limit):
    with module.app.test_client() as client:
        sign_in(client)
        assert client.get(f"{HISTORY}?limit={limit}").status_code == 400


def test_data_endpoint_only_exposes_approved_fields(module):
    with module.app.test_client() as client:
        sign_in(client)
        result = client.get(HISTORY)
    assert result.status_code == 200
    assert set(result.get_json()["transactions"][0]) == {"id", "reason", "points_change", "created_at"}


@pytest.mark.parametrize("payload", [None, {"user": []}])
def test_data_endpoint_rejects_malformed_customer(module, monkeypatch, payload):
    original = module.database_request
    monkeypatch.setattr(module, "database_request", lambda path, **kwargs: payload if path == "/internal/users/2" else original(path, **kwargs))
    with module.app.test_client() as client:
        sign_in(client)
        assert client.get(HISTORY).status_code == 502


@pytest.mark.parametrize("path,method", [(CHAT, "post"), (HISTORY, "get")])
def test_database_timeout_has_safe_retry_error(module, monkeypatch, path, method):
    original = module.database_request
    def timeout_after_auth(route, **kwargs):
        if route == "/internal/users/1":
            return original(route, **kwargs)
        raise TimeoutError("private database details")
    monkeypatch.setattr(module, "database_request", timeout_after_auth)
    with module.app.test_client() as client:
        sign_in(client)
        result = getattr(client, method)(path, json={"question": "Show point history for Customer #2"})
    assert result.status_code == 503
    assert "private database details" not in result.get_data(as_text=True)


def test_conflicting_name_and_id_need_clarification(module, monkeypatch):
    original = module.database_request
    monkeypatch.setattr(module, "database_request", lambda path, **kw: {"users": [CUSTOMER, {**CUSTOMER, "id": 3, "full_name": "Other Person", "email": "other@asd.local"}]} if "?role=" in path else original(path, **kw))
    with module.app.test_client() as client:
        sign_in(client)
        result = client.post(CHAT, json={"question": "Show point history for Demo Customer and Customer #3"})
    assert result.get_json()["clarification_required"] is True


@pytest.mark.parametrize("path,method", [(CHAT, "post"), (HISTORY, "get")])
def test_disabled_mcp_does_not_call_tool(module, monkeypatch, path, method):
    monkeypatch.setenv("MCP_ENABLED", "false")
    monkeypatch.setattr(module, "call_loyalty_history_mcp", lambda *args: pytest.fail("MCP is disabled"))
    with module.app.test_client() as client:
        sign_in(client)
        assert getattr(client, method)(path, json={"question": "Show point history for Customer #2"}).status_code == 503


@pytest.mark.parametrize("fault", ["customer", "limit", "count", "readonly", "tool", "boolean", "date", "duplicate", "row_customer"])
def test_chat_rejects_tampered_tool_output(module, monkeypatch, fault):
    payload = copy.deepcopy(response())
    history = payload["result"]
    if fault == "customer": history["customer_id"] = 3
    if fault == "limit": history["limit"] = 20
    if fault == "count": history["count"] = 2
    if fault == "readonly": payload["metadata"]["read_only"] = False
    if fault == "tool": payload["tool"] = "other_tool"
    if fault == "boolean": history["transactions"][0]["points_change"] = True
    if fault == "date": history["transactions"][0]["created_at"] = "bad-date"
    if fault == "duplicate": history["transactions"] *= 2; history["count"] = 2
    if fault == "row_customer": history["transactions"][0]["user_id"] = 3
    monkeypatch.setattr(module, "call_loyalty_history_mcp", lambda *args: payload)
    with module.app.test_client() as client:
        sign_in(client)
        assert client.post(CHAT, json={"question": "Show point history for Customer #2"}).status_code == 502


def test_empty_history_is_explicit(module, monkeypatch):
    payload = response()
    payload["result"].update(count=0, transactions=[])
    monkeypatch.setattr(module, "call_loyalty_history_mcp", lambda *args: payload)
    with module.app.test_client() as client:
        sign_in(client)
        result = client.post(CHAT, json={"question": "Show point history for Customer #2"})
    assert "no recorded" in result.get_json()["answer"]


def test_outage_can_be_retried(module, monkeypatch):
    def unavailable(*args):
        raise TimeoutError("private details")
    monkeypatch.setattr(module, "call_loyalty_history_mcp", unavailable)
    with module.app.test_client() as client:
        sign_in(client)
        result = client.post(CHAT, json={"question": "Show point history for Customer #2"})
        assert result.status_code == 503 and "private details" not in result.get_data(as_text=True)
        monkeypatch.setattr(module, "call_loyalty_history_mcp", lambda *args: response())
        assert client.post(CHAT, json={"question": "Show point history for Customer #2"}).status_code == 200


def test_cookie_is_transport_only(module, monkeypatch):
    captured = {}
    class Client:
        def __init__(self, **kwargs): captured.update(kwargs)
        def call_tool(self, tool, arguments, **kwargs):
            captured.update(tool=tool, arguments=arguments, **kwargs)
            return response()
    # The fixture stubs the tool call; load its real adapter independently.
    spec = importlib.util.spec_from_file_location("history_real_adapter", Path(module.__file__))
    real = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(real)
    monkeypatch.setattr(real, "MCPClient", Client)
    with real.app.test_request_context(headers={"Cookie": "ethan_session=test-session"}):
        real.call_loyalty_history_mcp(2, 5)
    assert captured["arguments"] == {"customer_id": 2, "limit": 5}
    assert captured["request_headers"] == {"Cookie": "ethan_session=test-session"}
    assert captured["allowed_tools"] == frozenset({TOOL})


def test_authenticated_protocol_reads_through_protected_backend(module, monkeypatch):
    """Real SDK/ASGI MCP transport calls an actual HTTP feature backend."""
    import asyncio
    import sys
    import threading
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    from werkzeug.serving import make_server
    student_folder = Path(__file__).resolve().parents[1]
    project_root = student_folder if (student_folder / "ai-services").is_dir() else student_folder.parent
    sys.path.insert(0, str(project_root / "ai-services"))
    from mcp_server.server import create_server

    backend = make_server("127.0.0.1", 0, module.app, threaded=True)
    thread = threading.Thread(target=backend.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("MCP_CUSTOMER_API_URL", f"http://127.0.0.1:{backend.server_port}")
    with module.app.test_client() as client:
        sign_in(client)
        with client.session_transaction() as current:
            admin_cookie = module.app.session_interface.get_signing_serializer(module.app).dumps(dict(current))
        sign_in(client, "customer")
        with client.session_transaction() as current:
            customer_cookie = module.app.session_interface.get_signing_serializer(module.app).dumps(dict(current))

    async def exercise(cookie):
        server = create_server()
        app = server.streamable_http_app()
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), headers={"Cookie": f"ethan_session={cookie}"}) as http:
                async with streamable_http_client("http://127.0.0.1:8765/mcp", http_client=http) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(TOOL, {"customer_id": 2, "limit": 5})
                        assert result.isError is False
                        return result.structuredContent
    try:
        allowed = asyncio.run(exercise(admin_cookie))
        assert allowed["success"] is True
        assert allowed["result"]["transactions"][0]["points_change"] == 50
        assert "Private Admin" not in str(allowed)
        assert asyncio.run(exercise(customer_cookie))["error"]["code"] == "TOOL_NOT_ALLOWED"
        assert asyncio.run(exercise("forged-session"))["error"]["code"] == "AUTHENTICATION_REQUIRED"
    finally:
        backend.shutdown()
        thread.join(timeout=5)
        backend.server_close()
    assert all(method == "GET" for method, _ in module.database_calls)
