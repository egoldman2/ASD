"""Read-only Customer Support tools using a revalidated staff session."""

from contextlib import closing
import json
from typing import Any

from mcp.server.fastmcp import Context
from pydantic import StrictInt
import requests

from mcp_server.config import get_settings
from mcp_server.response import ToolErrorCode, error_response, success_response


SEARCH_TICKETS = "ethan_goldman_search_tickets"
GET_TICKET_CONTEXT = "ethan_goldman_get_ticket_context"
MAX_RESPONSE_BYTES = 256 * 1024


def _integer(value, field, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{field} must be an integer between {minimum} and {maximum}.")
    return value


def _read(tool, ctx, path, params):
    # Credentials come only from the transport; model arguments cannot supply them.
    http_request = ctx.request_context.request
    cookie = http_request.cookies.get("ethan_session") if http_request is not None else None
    if not cookie:
        return error_response(tool, ToolErrorCode.AUTHENTICATION_REQUIRED, "A staff session is required.")
    settings = get_settings()
    try:
        with closing(requests.get(
            settings.support_api_url + "/api/support/admin/tool-data" + path,
            params={key: value for key, value in params.items() if value is not None},
            cookies={"ethan_session": cookie}, headers={"Accept": "application/json"},
            timeout=settings.request_timeout_seconds, allow_redirects=False, stream=True,
        )) as response:
            errors = {
                400: (ToolErrorCode.INVALID_ARGUMENT, "Invalid support tool arguments."),
                401: (ToolErrorCode.AUTHENTICATION_REQUIRED, "A valid staff session is required."),
                403: (ToolErrorCode.TOOL_NOT_ALLOWED, "Only staff may use support tools."),
                404: (ToolErrorCode.RECORD_NOT_FOUND, "Ticket not found."),
                503: (ToolErrorCode.UPSTREAM_UNAVAILABLE, "Support services are unavailable."),
            }
            if response.status_code in errors:
                return error_response(tool, *errors[response.status_code])
            if response.status_code != 200:
                return error_response(tool, ToolErrorCode.UPSTREAM_ERROR, "The support API could not complete the request.")
            body = bytearray()
            for chunk in response.iter_content(8192):
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise ValueError("Response exceeds limit")
            result = json.loads(body)
            if not isinstance(result, dict):
                raise ValueError("Invalid response shape")
            if path == "/tickets":
                if not isinstance(result.get("tickets"), list) or not isinstance(result.get("total"), int):
                    raise ValueError("Invalid search result")
            elif not isinstance(result.get("id"), int) or not isinstance(result.get("messages"), list):
                raise ValueError("Invalid context result")
    except requests.RequestException:
        return error_response(tool, ToolErrorCode.UPSTREAM_UNAVAILABLE, "Support services are unavailable.")
    except (ValueError, TypeError):
        return error_response(tool, ToolErrorCode.UPSTREAM_ERROR, "The support API returned an invalid response.")
    return success_response(tool, result, metadata={"read_only": True})


def search_tickets(
    ctx: Context, search: str | None = None, status: str | None = None,
    category: str | None = None, priority: str | None = None, assigned_to: str | None = None,
    limit: StrictInt = 20, offset: StrictInt = 0,
) -> dict[str, Any]:
    """Search staff tickets without conversation bodies; admin session required."""
    try:
        _integer(limit, "limit", 1, 50)
        _integer(offset, "offset", 0, 10000)
        filters = {"search": search, "status": status, "category": category,
                   "priority": priority, "assigned_to": assigned_to}
        for field, value in filters.items():
            if value is not None and (not isinstance(value, str) or len(value) > (160 if field == "search" else 100)):
                raise ValueError(f"Invalid {field} filter.")
    except ValueError as exc:
        return error_response(SEARCH_TICKETS, ToolErrorCode.INVALID_ARGUMENT, str(exc))
    return _read(SEARCH_TICKETS, ctx, "/tickets", {**filters, "limit": limit, "offset": offset})


def get_ticket_context(
    ctx: Context, ticket_id: StrictInt, message_limit: StrictInt = 20,
) -> dict[str, Any]:
    """Return a ticket and its latest bounded, redacted messages for staff."""
    try:
        _integer(ticket_id, "ticket_id", 1, 2**63 - 1)
        _integer(message_limit, "message_limit", 1, 50)
    except ValueError as exc:
        return error_response(GET_TICKET_CONTEXT, ToolErrorCode.INVALID_ARGUMENT, str(exc))
    return _read(GET_TICKET_CONTEXT, ctx, f"/tickets/{ticket_id}", {"message_limit": message_limit})
