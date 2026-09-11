"""Stable structured response helpers shared by all marketplace MCP tools."""

from __future__ import annotations

from enum import Enum
from typing import Any


class ToolErrorCode(str, Enum):
    """Machine-readable error categories returned by MCP tools."""

    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    TOOL_NOT_ALLOWED = "TOOL_NOT_ALLOWED"
    RECORD_NOT_FOUND = "RECORD_NOT_FOUND"
    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    MCP_DISABLED = "MCP_DISABLED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


def _validate_tool_name(tool: str) -> str:
    if not isinstance(tool, str) or not tool.strip():
        raise ValueError("tool must be a non-empty string.")
    return tool.strip()


def success_response(
    tool: str,
    result: Any,
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the common success envelope used by every registered tool."""

    payload: dict[str, Any] = {
        "success": True,
        "tool": _validate_tool_name(tool),
        "result": result,
        "error": None,
    }
    if metadata is not None:
        payload["metadata"] = metadata
    return payload


def error_response(
    tool: str,
    code: ToolErrorCode | str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a safe machine-readable failure envelope for an MCP tool."""

    if not isinstance(message, str) or not message.strip():
        raise ValueError("message must be a non-empty string.")

    error: dict[str, Any] = {
        "code": code.value if isinstance(code, ToolErrorCode) else str(code),
        "message": message.strip(),
    }
    if details is not None:
        error["details"] = details

    return {
        "success": False,
        "tool": _validate_tool_name(tool),
        "result": None,
        "error": error,
    }
