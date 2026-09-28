"""Safe failure and credential boundaries for the support HTTP adapter."""

import json
from types import SimpleNamespace

import pytest
import requests

from mcp_server.tools.ethan_goldman_support import (
    SEARCH_TICKETS, get_ticket_context, search_tickets,
)


def context(cookie="staff-session-test"):
    return SimpleNamespace(request_context=SimpleNamespace(request=SimpleNamespace(
        cookies={"ethan_session": cookie} if cookie else {},
    )))


@pytest.mark.parametrize("status,body,code", [
    (302, b"", "UPSTREAM_ERROR"),
    (500, b"private upstream stack trace", "UPSTREAM_ERROR"),
    (200, b"invalid JSON with private content", "UPSTREAM_ERROR"),
    (200, b"[]", "UPSTREAM_ERROR"),
    (200, b"{}", "UPSTREAM_ERROR"),
    (200, b"x" * (256 * 1024 + 1), "UPSTREAM_ERROR"),
    (503, b"", "UPSTREAM_UNAVAILABLE"),
])
def test_safe_upstream_failures(monkeypatch, status, body, code):
    response = requests.Response()
    response.status_code = status
    response._content = body
    response._content_consumed = True
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: response)
    result = search_tickets(context())
    assert result["success"] is False and result["error"]["code"] == code
    assert "private" not in json.dumps(result)
    assert "staff-session-test" not in json.dumps(result)


def test_invalid_arguments_and_missing_session_do_not_connect(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid or anonymous calls must not contact the support API")

    monkeypatch.setattr(requests, "get", forbidden)
    assert search_tickets(context(None))["error"]["code"] == "AUTHENTICATION_REQUIRED"
    for arguments in ({"limit": True}, {"limit": 1.5}, {"offset": 10001}, {"search": 42}):
        assert search_tickets(context(), **arguments)["error"]["code"] == "INVALID_ARGUMENT"
    assert get_ticket_context(context(), True)["error"]["code"] == "INVALID_ARGUMENT"


def test_transport_cookie_and_safe_timeout(monkeypatch):
    def timeout(url, **kwargs):
        assert url.endswith("/api/support/admin/tool-data/tickets")
        assert kwargs["cookies"] == {"ethan_session": "staff-session-test"}
        assert kwargs["allow_redirects"] is False and kwargs["stream"] is True
        assert "ethan_session" not in kwargs["params"]
        raise requests.Timeout("staff-session-test private timeout detail")

    monkeypatch.setattr(requests, "get", timeout)
    result = search_tickets(context())
    assert result["tool"] == SEARCH_TICKETS and result["error"]["code"] == "UPSTREAM_UNAVAILABLE"
    assert "staff-session-test" not in json.dumps(result)
