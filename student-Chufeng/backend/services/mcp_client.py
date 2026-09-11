"""MCP client used by Chufeng's Flask backend and agentic workflow."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import os
from typing import Any, Callable, Coroutine, TypeVar
from urllib.parse import urlparse

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


DEFAULT_MCP_SERVER_URL = "http://127.0.0.1:8765/mcp"
DEFAULT_MCP_CLIENT_TIMEOUT_SECONDS = 10.0

CHUFENG_ALLOWED_TOOLS = frozenset(
    {
        "chufeng_search_products",
        "chufeng_get_product_details",
        "chufeng_check_product_stock",
        "chufeng_calculate_cart_summary",
    }
)

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}
_T = TypeVar("_T")


class MCPClientError(Exception):
    """Safe failure raised by the Chufeng backend MCP adapter."""

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
    """Raised when backend MCP environment settings are invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="MCP_CONFIGURATION_ERROR", status_code=500)


class MCPDisabledError(MCPClientError):
    """Raised when an MCP call is attempted while integration is disabled."""

    def __init__(self) -> None:
        super().__init__(
            "MCP integration is disabled.",
            code="MCP_DISABLED",
            status_code=503,
        )


class MCPToolNotAllowedError(MCPClientError):
    """Raised before a tool outside Chufeng's allowlist can be requested."""

    def __init__(self, tool_name: str) -> None:
        super().__init__(
            f"Tool '{tool_name}' is not allowed for the Chufeng feature.",
            code="TOOL_NOT_ALLOWED",
            status_code=403,
        )


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


@dataclass(frozen=True, slots=True)
class MCPClientSettings:
    """Validated connection settings for Chufeng's backend MCP client."""

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


class ChufengMCPClient:
    """Small protocol adapter around the official Python MCP client."""

    def __init__(
        self,
        settings: MCPClientSettings | None = None,
        *,
        allowed_tools: frozenset[str] = CHUFENG_ALLOWED_TOOLS,
        http_client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        self.settings = settings or MCPClientSettings.from_environment()
        self.allowed_tools = frozenset(allowed_tools)
        self._http_client_factory = http_client_factory or self._default_http_client

    def _default_http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.settings.timeout_seconds)

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
        """List only tools that the Chufeng feature is allowed to invoke."""

        self._ensure_enabled()
        try:
            async with self._http_client_factory() as http_client:
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
        """Call one allowlisted MCP tool and return its structured payload."""

        self._ensure_enabled()
        supplied_arguments = {} if arguments is None else arguments
        self._validate_tool_call(tool_name, supplied_arguments)

        try:
            async with self._http_client_factory() as http_client:
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
        """Synchronous wrapper intended for the current Flask backend."""

        return _run_synchronously(self.alist_tools)

    def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Synchronously call a tool from a Flask request handler."""

        return _run_synchronously(lambda: self.acall_tool(tool_name, arguments))


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
