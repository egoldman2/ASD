"""HTTP-facing orchestration for Chufeng's MCP integration."""

from __future__ import annotations

import logging
from typing import Any

from ..services.mcp_client import (
    ChufengMCPClient,
    MCPClientError,
    MCPDisabledError,
)


LOGGER = logging.getLogger(__name__)

TOOL_ERROR_HTTP_STATUS = {
    "INVALID_ARGUMENT": 400,
    "TOOL_NOT_FOUND": 404,
    "TOOL_NOT_ALLOWED": 403,
    "RECORD_NOT_FOUND": 404,
    "UPSTREAM_UNAVAILABLE": 503,
    "UPSTREAM_ERROR": 502,
    "MCP_DISABLED": 503,
    "INTERNAL_ERROR": 500,
}


def _create_client() -> ChufengMCPClient:
    """Create a client per request so environment overrides remain testable."""

    return ChufengMCPClient()


def _safe_internal_error() -> tuple[dict[str, Any], int]:
    return {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "The MCP request could not be completed.",
        }
    }, 500


def get_mcp_status() -> tuple[dict[str, Any], int]:
    """Return a UI-friendly snapshot without making status failures fatal."""

    try:
        client = _create_client()
        tools = client.list_tools()
    except MCPDisabledError as exc:
        return {
            "success": True,
            "enabled": False,
            "available": False,
            "tool_count": 0,
            "error": {"code": exc.code, "message": exc.message},
        }, 200
    except MCPClientError as exc:
        return {
            "success": True,
            "enabled": True,
            "available": False,
            "tool_count": 0,
            "error": {"code": exc.code, "message": exc.message},
        }, 200
    except Exception:
        LOGGER.exception("Unexpected failure while checking MCP status")
        return {
            "success": True,
            "enabled": True,
            "available": False,
            "tool_count": 0,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "The MCP status could not be checked.",
            },
        }, 200

    return {
        "success": True,
        "enabled": True,
        "available": True,
        "tool_count": len(tools),
        "error": None,
    }, 200


def list_mcp_tools() -> tuple[dict[str, Any], int]:
    """Return Chufeng's allowlisted MCP tool definitions."""

    try:
        tools = _create_client().list_tools()
    except MCPClientError as exc:
        return exc.to_dict(), exc.status_code
    except Exception:
        LOGGER.exception("Unexpected failure while listing MCP tools")
        return _safe_internal_error()

    return {
        "success": True,
        "tools": tools,
        "count": len(tools),
        "error": None,
    }, 200


def call_mcp_tool(data: Any) -> tuple[dict[str, Any], int]:
    """Validate an HTTP request and invoke one Chufeng MCP tool."""

    if not isinstance(data, dict):
        return {
            "error": {
                "code": "INVALID_ARGUMENT",
                "message": "A JSON request body is required.",
            }
        }, 400

    tool_name = data.get("tool")
    if not isinstance(tool_name, str) or not tool_name.strip():
        return {
            "error": {
                "code": "INVALID_ARGUMENT",
                "message": "tool must be a non-empty string.",
            }
        }, 400

    arguments = data.get("arguments", {})
    if not isinstance(arguments, dict):
        return {
            "error": {
                "code": "INVALID_ARGUMENT",
                "message": "arguments must be an object.",
            }
        }, 400

    try:
        payload = _create_client().call_tool(tool_name.strip(), arguments)
    except MCPClientError as exc:
        return exc.to_dict(), exc.status_code
    except Exception:
        LOGGER.exception("Unexpected failure while calling MCP tool")
        return _safe_internal_error()

    if not isinstance(payload, dict):
        LOGGER.error("MCP client returned a non-object payload")
        return {
            "error": {
                "code": "MCP_INVALID_RESPONSE",
                "message": "The MCP server returned an invalid response.",
            }
        }, 502

    if payload.get("success") is False:
        error = payload.get("error")
        code = error.get("code") if isinstance(error, dict) else None
        return payload, TOOL_ERROR_HTTP_STATUS.get(code, 502)

    return payload, 200
