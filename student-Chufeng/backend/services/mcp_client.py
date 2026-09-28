"""Chufeng's allowlist and backwards-compatible adapter for shared MCP transport."""

from shared.mcp_client import (
    DEFAULT_MCP_CLIENT_TIMEOUT_SECONDS,
    DEFAULT_MCP_SERVER_URL,
    MCPClient,
    MCPClientError,
    MCPClientSettings,
    MCPConfigurationError,
    MCPDisabledError,
    MCPToolNotAllowedError,
)


CHUFENG_ALLOWED_TOOLS = frozenset(
    {
        "chufeng_search_products",
        "chufeng_get_product_details",
        "chufeng_check_product_stock",
        "chufeng_calculate_cart_summary",
    }
)


class ChufengMCPClient(MCPClient):
    """Preserve the existing catalogue interface and default tool boundary."""

    def __init__(
        self,
        settings=None,
        *,
        allowed_tools=CHUFENG_ALLOWED_TOOLS,
        http_client_factory=None,
    ):
        super().__init__(
            settings,
            allowed_tools=allowed_tools,
            http_client_factory=http_client_factory,
        )
