"""Environment-backed configuration for the shared local MCP server."""

from __future__ import annotations

from dataclasses import dataclass
import os


DEFAULT_MCP_HOST = "127.0.0.1"
DEFAULT_MCP_PORT = 8765
DEFAULT_MCP_PATH = "/mcp"
DEFAULT_PRODUCT_DATABASE_API_URL = "http://127.0.0.1:6001/api/database"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 10.0
DEFAULT_LOG_LEVEL = "INFO"


class ConfigurationError(ValueError):
    """Raised when an MCP environment setting is invalid."""


def _required_text(value: str, setting_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ConfigurationError(f"{setting_name} must not be empty.")
    return cleaned


def _port_from_environment(value: str) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError("MCP_PORT must be an integer.") from exc

    if not 1 <= port <= 65535:
        raise ConfigurationError("MCP_PORT must be between 1 and 65535.")
    return port


def _timeout_from_environment(value: str) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(
            "MCP_REQUEST_TIMEOUT_SECONDS must be a number."
        ) from exc

    if timeout <= 0:
        raise ConfigurationError(
            "MCP_REQUEST_TIMEOUT_SECONDS must be greater than zero."
        )
    return timeout


def _normalise_path(value: str) -> str:
    path = _required_text(value, "MCP_PATH")
    if not path.startswith("/"):
        path = f"/{path}"
    if len(path) > 1:
        path = path.rstrip("/")
    return path


@dataclass(frozen=True, slots=True)
class MCPSettings:
    """Configuration shared by the MCP server and its tool adapters."""

    host: str
    port: int
    path: str
    product_database_api_url: str
    request_timeout_seconds: float
    log_level: str

    @property
    def endpoint_url(self) -> str:
        """Return the local URL used by host-side MCP clients."""

        display_host = "127.0.0.1" if self.host == "0.0.0.0" else self.host
        return f"http://{display_host}:{self.port}{self.path}"

    @classmethod
    def from_environment(cls) -> "MCPSettings":
        """Build validated settings from the current process environment."""

        host = _required_text(
            os.getenv("MCP_HOST", DEFAULT_MCP_HOST),
            "MCP_HOST",
        )
        port = _port_from_environment(
            os.getenv("MCP_PORT", str(DEFAULT_MCP_PORT))
        )
        path = _normalise_path(os.getenv("MCP_PATH", DEFAULT_MCP_PATH))
        product_database_api_url = _required_text(
            os.getenv(
                "PRODUCT_DATABASE_API_URL",
                DEFAULT_PRODUCT_DATABASE_API_URL,
            ),
            "PRODUCT_DATABASE_API_URL",
        ).rstrip("/")
        timeout = _timeout_from_environment(
            os.getenv(
                "MCP_REQUEST_TIMEOUT_SECONDS",
                str(DEFAULT_REQUEST_TIMEOUT_SECONDS),
            )
        )
        log_level = _required_text(
            os.getenv("MCP_LOG_LEVEL", DEFAULT_LOG_LEVEL),
            "MCP_LOG_LEVEL",
        ).upper()

        return cls(
            host=host,
            port=port,
            path=path,
            product_database_api_url=product_database_api_url,
            request_timeout_seconds=timeout,
            log_level=log_level,
        )


def get_settings() -> MCPSettings:
    """Load settings on demand so tests can safely override the environment."""

    return MCPSettings.from_environment()
