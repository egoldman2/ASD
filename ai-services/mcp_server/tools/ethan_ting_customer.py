"""Read-only, customer-safe MCP tools for Ethan Ting's loyalty feature.

Tier calculations use supplied points. History reads use a transport session
revalidated by the feature backend; credentials are never tool arguments.
"""

from __future__ import annotations

from typing import Any
from contextlib import closing
import json

from mcp.server.fastmcp import Context
from pydantic import StrictInt
import requests

from mcp_server.config import get_settings
from mcp_server.response import ToolErrorCode, error_response, success_response
from shared.loyalty_history import validate_history_result


CALCULATE_LOYALTY_TIER = "ethan_ting_calculate_loyalty_tier"
GET_LOYALTY_HISTORY = "ethan_ting_get_loyalty_history"


def get_loyalty_history(ctx: Context, customer_id: StrictInt, limit: StrictInt = 5) -> dict[str, Any]:
    """Read the latest 1–20 point changes for a customer; an admin session is required."""
    if type(customer_id) is not int or not 1 <= customer_id <= 2147483647:
        return error_response(GET_LOYALTY_HISTORY, ToolErrorCode.INVALID_ARGUMENT, "customer_id must be a positive integer.")
    if type(limit) is not int or not 1 <= limit <= 20:
        return error_response(GET_LOYALTY_HISTORY, ToolErrorCode.INVALID_ARGUMENT, "limit must be an integer from 1 to 20.")
    http_request = ctx.request_context.request
    cookie = http_request.cookies.get("ethan_session") if http_request is not None else None
    if not cookie:
        return error_response(GET_LOYALTY_HISTORY, ToolErrorCode.AUTHENTICATION_REQUIRED, "An administrator session is required.")
    settings = get_settings()
    try:
        with closing(requests.get(
            f"{settings.customer_api_url}/api/admin/mcp/tool-data/loyalty/{customer_id}/history",
            params={"limit": limit}, cookies={"ethan_session": cookie},
            headers={"Accept": "application/json"}, timeout=settings.request_timeout_seconds,
            allow_redirects=False, stream=True,
        )) as response:
            errors = {
                400: (ToolErrorCode.INVALID_ARGUMENT, "Invalid history request."),
                401: (ToolErrorCode.AUTHENTICATION_REQUIRED, "The administrator session has expired. Sign in again."),
                403: (ToolErrorCode.TOOL_NOT_ALLOWED, "Administrator access is required."),
                404: (ToolErrorCode.RECORD_NOT_FOUND, "Customer not found."),
                503: (ToolErrorCode.UPSTREAM_UNAVAILABLE, "Customer services or MCP mode are unavailable."),
            }
            if response.status_code in errors:
                return error_response(GET_LOYALTY_HISTORY, *errors[response.status_code])
            if response.status_code != 200:
                return error_response(GET_LOYALTY_HISTORY, ToolErrorCode.UPSTREAM_ERROR, "The customer API could not return history.")
            body = bytearray()
            for chunk in response.iter_content(8192):
                body.extend(chunk)
                if len(body) > 64 * 1024:
                    raise ValueError("Response exceeds limit.")
            result = validate_history_result(json.loads(body), customer_id, limit)
    except requests.RequestException:
        return error_response(GET_LOYALTY_HISTORY, ToolErrorCode.UPSTREAM_UNAVAILABLE, "The customer API is unavailable.")
    except (ValueError, TypeError, UnicodeDecodeError):
        return error_response(GET_LOYALTY_HISTORY, ToolErrorCode.UPSTREAM_ERROR, "The customer API returned invalid history.")
    return success_response(GET_LOYALTY_HISTORY, result, metadata={"read_only": True})


def calculate_loyalty_tier(points_balance: int) -> dict[str, Any]:
    """Return the tier and progress for a non-negative points balance."""

    if (
        isinstance(points_balance, bool)
        or not isinstance(points_balance, int)
        or points_balance < 0
    ):
        return error_response(
            CALCULATE_LOYALTY_TIER,
            ToolErrorCode.INVALID_ARGUMENT,
            "points_balance must be a non-negative integer.",
            details={"field": "points_balance"},
        )

    if points_balance >= 1000:
        tier = "Gold"
        next_tier = None
        points_to_next_tier = 0
    elif points_balance >= 500:
        tier = "Silver"
        next_tier = "Gold"
        points_to_next_tier = 1000 - points_balance
    else:
        tier = "Bronze"
        next_tier = "Silver"
        points_to_next_tier = 500 - points_balance

    return success_response(
        CALCULATE_LOYALTY_TIER,
        {
            "points_balance": points_balance,
            "tier": tier,
            "next_tier": next_tier,
            "points_to_next_tier": points_to_next_tier,
        },
        metadata={"read_only": True},
    )
