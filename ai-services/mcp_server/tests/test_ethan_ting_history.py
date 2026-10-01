"""Authenticated history tool validates and minimises upstream records."""

import json
from types import SimpleNamespace

import pytest
import requests

from mcp_server.tools import ethan_ting_customer as tools


def context(cookie="signed-admin-cookie"):
    return SimpleNamespace(request_context=SimpleNamespace(request=SimpleNamespace(cookies={"ethan_session": cookie}) if cookie else None))


def history():
    return {"customer_id": 2, "limit": 5, "count": 1, "transactions": [{"id": 1, "user_id": 2, "points_change": -10, "reason": "Correction", "created_at": "2026-10-01 12:00:00", "password_hash": "private", "created_by_admin_name": "Private Admin"}]}


class Response:
    def __init__(self, status=200, payload=None, body=None):
        self.status_code = status
        self.body = body if body is not None else json.dumps(payload or history()).encode()
    def iter_content(self, chunk_size):
        yield self.body
    def close(self):
        pass


@pytest.mark.parametrize("customer_id,limit", [(0, 5), (-1, 5), (True, 5), ("2", 5), (2**31, 5), (2, 0), (2, 21), (2, True), (2, "5")])
def test_rejects_invalid_arguments_without_http(monkeypatch, customer_id, limit):
    monkeypatch.setattr(tools.requests, "get", lambda *args, **kwargs: pytest.fail("Invalid request"))
    assert tools.get_loyalty_history(context(), customer_id, limit)["error"]["code"] == "INVALID_ARGUMENT"


def test_requires_transport_session(monkeypatch):
    monkeypatch.setattr(tools.requests, "get", lambda *args, **kwargs: pytest.fail("No session"))
    assert tools.get_loyalty_history(context(None), 2)["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_fixed_endpoint_cookie_forwarding_and_minimum_fields(monkeypatch):
    captured = {}
    monkeypatch.setenv("MCP_CUSTOMER_API_URL", "http://127.0.0.1:6002")
    def get(url, **kwargs):
        captured.update(url=url, **kwargs)
        return Response()
    monkeypatch.setattr(tools.requests, "get", get)
    result = tools.get_loyalty_history(context(), 2)
    assert result["success"] is True and result["metadata"]["read_only"] is True
    assert captured["url"] == "http://127.0.0.1:6002/api/admin/mcp/tool-data/loyalty/2/history"
    assert captured["params"] == {"limit": 5}
    assert captured["cookies"] == {"ethan_session": "signed-admin-cookie"}
    assert captured["allow_redirects"] is False and captured["timeout"] > 0
    assert "private" not in json.dumps(result).lower()
    assert set(result["result"]["transactions"][0]) == {"id", "points_change", "reason", "created_at"}


@pytest.mark.parametrize("status,code", [(400, "INVALID_ARGUMENT"), (401, "AUTHENTICATION_REQUIRED"), (403, "TOOL_NOT_ALLOWED"), (404, "RECORD_NOT_FOUND"), (503, "UPSTREAM_UNAVAILABLE"), (302, "UPSTREAM_ERROR"), (500, "UPSTREAM_ERROR")])
def test_http_errors_are_safe(monkeypatch, status, code):
    monkeypatch.setattr(tools.requests, "get", lambda *args, **kwargs: Response(status, body=b"private error details"))
    result = tools.get_loyalty_history(context(), 2)
    assert result["error"]["code"] == code
    assert "private" not in json.dumps(result)


@pytest.mark.parametrize("body", [b"not json", b"x" * 65537, b"[]", b"{}"])
def test_invalid_or_oversized_output_is_rejected(monkeypatch, body):
    monkeypatch.setattr(tools.requests, "get", lambda *args, **kwargs: Response(body=body))
    assert tools.get_loyalty_history(context(), 2)["error"]["code"] == "UPSTREAM_ERROR"


def test_cross_customer_rows_rejected(monkeypatch):
    payload = history()
    payload["transactions"][0]["user_id"] = 3
    monkeypatch.setattr(tools.requests, "get", lambda *args, **kwargs: Response(payload=payload))
    assert tools.get_loyalty_history(context(), 2)["error"]["code"] == "UPSTREAM_ERROR"


def test_timeout_is_safe(monkeypatch):
    def timeout(*args, **kwargs):
        raise requests.Timeout("private upstream details")
    monkeypatch.setattr(tools.requests, "get", timeout)
    result = tools.get_loyalty_history(context(), 2)
    assert result["error"]["code"] == "UPSTREAM_UNAVAILABLE"
    assert "private" not in json.dumps(result)
