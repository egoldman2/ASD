"""Flask routes exposing Ryan's MCP integration to the inventory frontend.

The MCP client, settings and controller logic live in this one module,
matching the other inventory blueprints. Endpoints and response shapes
mirror Chufeng's /api/chufeng/mcp routes.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable, Coroutine, TypeVar
from urllib.parse import urlparse

import httpx
from flask import Blueprint, g, jsonify, request
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


LOGGER = logging.getLogger(__name__)

mcp_blueprint = Blueprint(
    "inventory_mcp",
    __name__,
    url_prefix="/api/inventory/mcp",
)

DEFAULT_MCP_SERVER_URL = "http://127.0.0.1:8765/mcp"
DEFAULT_MCP_CLIENT_TIMEOUT_SECONDS = 10.0

MCP_MODE_HEADER = "X-MCP-Mode"
MCP_MODE_ON_VALUES = {"1", "true", "yes", "on"}

RYAN_ALLOWED_TOOLS = frozenset(
    {
        "ryan_get_low_stock_items",
        "ryan_get_product_inventory",
        "ryan_get_supplier_details",
        "ryan_calculate_restock_order",
    }
)

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

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}
_T = TypeVar("_T")


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------

class MCPClientError(Exception):
    """Safe failure raised by the inventory MCP adapter."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "MCP_CLIENT_ERROR",
        status_code: int = 502,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code

    def to_dict(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message}}


class MCPConfigurationError(MCPClientError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="MCP_CONFIGURATION_ERROR", status_code=500)


class MCPDisabledError(MCPClientError):
    def __init__(self) -> None:
        super().__init__(
            "MCP integration is disabled.",
            code="MCP_DISABLED",
            status_code=503,
        )


class MCPToolNotAllowedError(MCPClientError):
    def __init__(self, tool_name: str) -> None:
        super().__init__(
            f"Tool '{tool_name}' is not allowed for the inventory feature.",
            code="TOOL_NOT_ALLOWED",
            status_code=403,
        )


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------

def _boolean_setting(value: str, setting_name: str) -> bool:
    normalised = value.strip().lower()
    if normalised in _TRUE_VALUES:
        return True
    if normalised in _FALSE_VALUES:
        return False
    raise MCPConfigurationError(
        f"{setting_name} must be one of: true, false, 1, 0, yes, no, on, off."
    )


def _positive_timeout(value: str) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise MCPConfigurationError(
            "MCP_CLIENT_TIMEOUT_SECONDS must be a number."
        ) from exc
    if timeout <= 0:
        raise MCPConfigurationError(
            "MCP_CLIENT_TIMEOUT_SECONDS must be greater than zero."
        )
    return timeout


def _server_url(value: str) -> str:
    cleaned = value.strip().rstrip("/")
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise MCPConfigurationError(
            "MCP_SERVER_URL must be an absolute HTTP or HTTPS URL."
        )
    return cleaned


@dataclass(frozen=True)
class MCPClientSettings:
    enabled: bool
    server_url: str
    timeout_seconds: float

    @classmethod
    def from_environment(cls) -> "MCPClientSettings":
        return cls(
            enabled=_boolean_setting(os.getenv("MCP_ENABLED", "true"), "MCP_ENABLED"),
            server_url=_server_url(
                os.getenv("MCP_SERVER_URL", DEFAULT_MCP_SERVER_URL)
            ),
            timeout_seconds=_positive_timeout(
                os.getenv(
                    "MCP_CLIENT_TIMEOUT_SECONDS",
                    str(DEFAULT_MCP_CLIENT_TIMEOUT_SECONDS),
                )
            ),
        )


# --------------------------------------------------------------------------
# MCP client
# --------------------------------------------------------------------------

def _run_synchronously(factory: Callable[[], Coroutine[Any, Any, _T]]) -> _T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(factory())
    raise MCPClientError(
        "Use the asynchronous MCP client methods inside an event loop.",
        code="MCP_ASYNC_CONTEXT",
        status_code=500,
    )


class InventoryMCPClient:
    """Small protocol adapter around the official Python MCP client."""

    def __init__(
        self,
        settings: MCPClientSettings | None = None,
        *,
        allowed_tools: frozenset[str] = RYAN_ALLOWED_TOOLS,
    ) -> None:
        self.settings = settings or MCPClientSettings.from_environment()
        self.allowed_tools = frozenset(allowed_tools)

    def _ensure_enabled(self) -> None:
        if not self.settings.enabled:
            raise MCPDisabledError()

    def _validate_tool_call(self, tool_name: Any, arguments: Any) -> None:
        if not isinstance(tool_name, str) or not tool_name.strip():
            raise MCPClientError(
                "tool_name must be a non-empty string.",
                code="INVALID_ARGUMENT",
                status_code=400,
            )
        if tool_name not in self.allowed_tools:
            raise MCPToolNotAllowedError(tool_name)
        if not isinstance(arguments, dict):
            raise MCPClientError(
                "arguments must be an object.",
                code="INVALID_ARGUMENT",
                status_code=400,
            )

    async def alist_tools(self) -> list[dict[str, Any]]:
        self._ensure_enabled()
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.timeout_seconds
            ) as http_client:
                async with streamable_http_client(
                    self.settings.server_url,
                    http_client=http_client,
                ) as (read_stream, write_stream, _):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        result = await session.list_tools()
        except MCPClientError:
            raise
        except Exception as exc:
            raise MCPClientError(
                "The MCP server is unavailable.",
                code="MCP_UNAVAILABLE",
                status_code=503,
            ) from exc

        tools = []
        for tool in result.tools:
            if tool.name not in self.allowed_tools:
                continue
            tools.append(
                {
                    "name": tool.name,
                    "title": tool.title,
                    "description": tool.description,
                    "input_schema": tool.inputSchema,
                    "output_schema": tool.outputSchema,
                    "annotations": (
                        tool.annotations.model_dump(exclude_none=True)
                        if tool.annotations is not None
                        else None
                    ),
                }
            )
        return tools

    async def acall_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_enabled()
        supplied_arguments = {} if arguments is None else arguments
        self._validate_tool_call(tool_name, supplied_arguments)

        try:
            async with httpx.AsyncClient(
                timeout=self.settings.timeout_seconds
            ) as http_client:
                async with streamable_http_client(
                    self.settings.server_url,
                    http_client=http_client,
                ) as (read_stream, write_stream, _):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        result = await session.call_tool(
                            tool_name,
                            supplied_arguments,
                            read_timeout_seconds=timedelta(
                                seconds=self.settings.timeout_seconds
                            ),
                        )
        except MCPClientError:
            raise
        except Exception as exc:
            raise MCPClientError(
                "The MCP server is unavailable.",
                code="MCP_UNAVAILABLE",
                status_code=503,
            ) from exc

        if result.isError:
            raise MCPClientError(
                "The MCP server could not execute the requested tool.",
                code="MCP_TOOL_ERROR",
                status_code=502,
            )
        if not isinstance(result.structuredContent, dict):
            raise MCPClientError(
                "The MCP server returned an invalid structured response.",
                code="MCP_INVALID_RESPONSE",
                status_code=502,
            )
        return result.structuredContent

    def list_tools(self) -> list[dict[str, Any]]:
        return _run_synchronously(self.alist_tools)

    def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return _run_synchronously(lambda: self.acall_tool(tool_name, arguments))


# --------------------------------------------------------------------------
# Request helpers
# --------------------------------------------------------------------------

def _create_client() -> InventoryMCPClient:
    """Create a client per request so environment overrides remain testable."""
    return InventoryMCPClient()


def _require_admin():
    if g.authenticated_user.get("role") != "admin":
        return jsonify({"error": "Administrator access required."}), 403
    return None


def _request_mcp_mode_enabled() -> bool:
    value = request.headers.get(MCP_MODE_HEADER, "on")
    return value.strip().lower() in MCP_MODE_ON_VALUES


def _mcp_mode_disabled_response():
    return jsonify(
        {
            "error": {
                "code": "MCP_DISABLED",
                "message": "MCP mode is disabled for this request.",
            }
        }
    ), 403


def _safe_internal_error():
    return jsonify(
        {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "The MCP request could not be completed.",
            }
        }
    ), 500


def _invalid(message: str):
    return jsonify(
        {"error": {"code": "INVALID_ARGUMENT", "message": message}}
    ), 400


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@mcp_blueprint.get("/status")
def get_mcp_status():
    """UI-friendly snapshot. Status failures are never fatal (always 200)."""
    if (error := _require_admin()) is not None:
        return error

    try:
        tools = _create_client().list_tools()
    except MCPDisabledError as exc:
        return jsonify(
            {
                "success": True,
                "enabled": False,
                "available": False,
                "tool_count": 0,
                "error": {"code": exc.code, "message": exc.message},
            }
        ), 200
    except MCPClientError as exc:
        return jsonify(
            {
                "success": True,
                "enabled": True,
                "available": False,
                "tool_count": 0,
                "error": {"code": exc.code, "message": exc.message},
            }
        ), 200
    except Exception:
        LOGGER.exception("Unexpected failure while checking MCP status")
        return jsonify(
            {
                "success": True,
                "enabled": True,
                "available": False,
                "tool_count": 0,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "The MCP status could not be checked.",
                },
            }
        ), 200

    return jsonify(
        {
            "success": True,
            "enabled": True,
            "available": True,
            "tool_count": len(tools),
            "error": None,
        }
    ), 200


@mcp_blueprint.get("/tools")
def list_mcp_tools():
    """Return the inventory feature's allowlisted MCP tool definitions."""
    if (error := _require_admin()) is not None:
        return error

    try:
        tools = _create_client().list_tools()
    except MCPClientError as exc:
        return jsonify(exc.to_dict()), exc.status_code
    except Exception:
        LOGGER.exception("Unexpected failure while listing MCP tools")
        return _safe_internal_error()

    return jsonify(
        {"success": True, "tools": tools, "count": len(tools), "error": None}
    ), 200


@mcp_blueprint.post("/tools/call")
def call_mcp_tool():
    """POST /api/inventory/mcp/tools/call
    Body: { tool: str, arguments: object }
    Header X-MCP-Mode: off disables the call for this request.
    """
    if (error := _require_admin()) is not None:
        return error
    if not _request_mcp_mode_enabled():
        return _mcp_mode_disabled_response()

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _invalid("A JSON request body is required.")

    tool_name = data.get("tool")
    if not isinstance(tool_name, str) or not tool_name.strip():
        return _invalid("tool must be a non-empty string.")

    arguments = data.get("arguments", {})
    if not isinstance(arguments, dict):
        return _invalid("arguments must be an object.")

    try:
        payload = _create_client().call_tool(tool_name.strip(), arguments)
    except MCPClientError as exc:
        return jsonify(exc.to_dict()), exc.status_code
    except Exception:
        LOGGER.exception("Unexpected failure while calling MCP tool")
        return _safe_internal_error()

    if not isinstance(payload, dict):
        LOGGER.error("MCP client returned a non-object payload")
        return jsonify(
            {
                "error": {
                    "code": "MCP_INVALID_RESPONSE",
                    "message": "The MCP server returned an invalid response.",
                }
            }
        ), 502

    if payload.get("success") is False:
        error_body = payload.get("error")
        code = error_body.get("code") if isinstance(error_body, dict) else None
        return jsonify(payload), TOOL_ERROR_HTTP_STATUS.get(code, 502)

    return jsonify(payload), 200