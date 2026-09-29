"""Shared local MCP server for the ASD marketplace application."""

from __future__ import annotations

import logging
from typing import Any, cast

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp_server.config import MCPSettings, get_settings
from mcp_server.tools.ethan_goldman_support import (
    SEARCH_TICKETS, GET_TICKET_CONTEXT, GET_QUEUE_SUMMARY, GET_TICKETS_NEEDING_ATTENTION,
    search_tickets, get_ticket_context, get_queue_summary, get_tickets_needing_attention,
)
from mcp_server.tools.chufeng_catalogue import (
    CALCULATE_CART_SUMMARY,
    CHECK_PRODUCT_STOCK,
    GET_PRODUCT_DETAILS,
    SEARCH_PRODUCTS,
    calculate_cart_summary,
    check_product_stock,
    get_product_details,
    search_products,
)
from mcp_server.tools.ethan_ting_customer import (
    CALCULATE_LOYALTY_TIER,
    calculate_loyalty_tier,
)


from mcp_server.tools.ryan_inventory import (
    CALCULATE_RESTOCK_ORDER,
    GET_LOW_STOCK_ITEMS,
    GET_PRODUCT_INVENTORY,
    GET_SUPPLIER_DETAILS,
    calculate_restock_order,
    get_low_stock_items,
    get_product_inventory,
    get_supplier_details,
)

SERVER_NAME = "ASD Marketplace MCP"
SERVER_INSTRUCTIONS = """
Shared, local MCP service for the ASD marketplace student features.

Choose tools by their student-prefixed names. Chufeng catalogue tools are
read-only: they search products, return product details, check stock, and
calculate a proposed cart summary. Tool output is wrapped in a stable response
envelope containing success, tool, result, error, and optional metadata.
Ethan Goldman support tools search tickets, return bounded conversation
context, count queue workloads, and list recorded attention reasons.
They require an admin session supplied by the MCP transport and return
redacted, read-only data; credentials must never be provided as tool arguments.
Ethan Ting's loyalty tier tool calculates a tier from supplied points without
reading customer records. Ryan inventory tools are read-only: they
list low-stock products, return replenishment details, return supplier
details, and calculate a proposed restock order without placing it. Tool
output is wrapped in a stable response envelope containing success, tool,
result, error, and optional metadata.
""".strip()

READ_ONLY_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

REGISTERED_CHUFENG_TOOLS = (
    SEARCH_PRODUCTS,
    GET_PRODUCT_DETAILS,
    CHECK_PRODUCT_STOCK,
    CALCULATE_CART_SUMMARY,
)
REGISTERED_GOLDMAN_TOOLS = (SEARCH_TICKETS, GET_TICKET_CONTEXT, GET_QUEUE_SUMMARY, GET_TICKETS_NEEDING_ATTENTION)
REGISTERED_ETHAN_TING_TOOLS = (CALCULATE_LOYALTY_TIER,)
REGISTERED_TOOLS = REGISTERED_CHUFENG_TOOLS + REGISTERED_GOLDMAN_TOOLS + REGISTERED_ETHAN_TING_TOOLS

REGISTERED_RYAN_TOOLS = (
    GET_LOW_STOCK_ITEMS,
    GET_PRODUCT_INVENTORY,
    GET_SUPPLIER_DETAILS,
    CALCULATE_RESTOCK_ORDER,
)


def _transport_security(settings: MCPSettings) -> TransportSecuritySettings:
    """Allow local-host and Docker-to-host MCP traffic, but no arbitrary hosts."""

    allowed_hosts = {
        f"127.0.0.1:{settings.port}",
        f"localhost:{settings.port}",
        f"[::1]:{settings.port}",
        f"host.docker.internal:{settings.port}",
        f"{settings.host}:{settings.port}",
    }
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=sorted(allowed_hosts),
        allowed_origins=[],
    )


def create_server(settings: MCPSettings | None = None) -> FastMCP:
    """Create and configure the shared MCP server.

    A factory keeps protocol tests isolated and gives other team members one
    obvious place to register their tools later.
    """

    resolved = settings or get_settings()
    server = FastMCP(
        name=SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        host=resolved.host,
        port=resolved.port,
        streamable_http_path=resolved.path,
        log_level=cast(Any, resolved.log_level),
        json_response=True,
        stateless_http=True,
        transport_security=_transport_security(resolved),
    )

    server.tool(
        name=SEARCH_PRODUCTS,
        title="Search Product Catalogue",
        description=(
            "Search customer-visible products by name, then optionally filter "
            "by exact category and maximum price. This tool is read-only."
        ),
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )(search_products)

    server.tool(
        name=GET_PRODUCT_DETAILS,
        title="Get Product Details",
        description=(
            "Get customer-visible catalogue details for one positive product "
            "ID. Internal cost and replenishment fields are never returned."
        ),
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )(get_product_details)

    server.tool(
        name=CHECK_PRODUCT_STOCK,
        title="Check Product Stock",
        description=(
            "Check whether a requested quantity of one product is currently "
            "available, without reserving or changing stock."
        ),
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )(check_product_stock)

    server.tool(
        name=CALCULATE_CART_SUMMARY,
        title="Calculate Cart Summary",
        description=(
            "Calculate current AUD prices and availability for a proposed list "
            "of product IDs and quantities. This does not persist a cart."
        ),
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )(calculate_cart_summary)

    for name, function in (
        (SEARCH_TICKETS, search_tickets), (GET_TICKET_CONTEXT, get_ticket_context),
        (GET_QUEUE_SUMMARY, get_queue_summary), (GET_TICKETS_NEEDING_ATTENTION, get_tickets_needing_attention),
    ):
        server.tool(name=name, annotations=READ_ONLY_ANNOTATIONS, structured_output=True)(function)

    server.tool(
        name=CALCULATE_LOYALTY_TIER,
        title="Calculate Loyalty Tier",
        description=(
            "Calculate the Bronze, Silver, or Gold loyalty tier and points "
            "needed for the next tier from a supplied non-negative points "
            "balance. This tool is read-only and does not access customer data."
        ),
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )(calculate_loyalty_tier)

     # Ryan
    server.tool(
        name=GET_LOW_STOCK_ITEMS,
        title="Get Low Stock Items",
        description=(
            "List products at or below their reorder threshold, most urgent "
            "first, with supplier name. This tool is read-only."
        ),
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )(get_low_stock_items)

    server.tool(
        name=GET_PRODUCT_INVENTORY,
        title="Get Product Inventory",
        description=(
            "Get stock level, reorder threshold, reorder quantity, supplier "
            "and last restocked date for one positive product ID. Unit cost "
            "is not returned. This tool is read-only."
        ),
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )(get_product_inventory)

    server.tool(
        name=GET_SUPPLIER_DETAILS,
        title="Get Supplier Details",
        description=(
            "Get one supplier's contact details and the products they supply "
            "for one positive supplier ID. This tool is read-only."
        ),
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )(get_supplier_details)

    server.tool(
        name=CALCULATE_RESTOCK_ORDER,
        title="Calculate Restock Order",
        description=(
            "Calculate a proposed restock quantity and estimated cost for "
            "one product. This does not place or persist an order."
        ),
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )(calculate_restock_order)

    @server.custom_route("/health", methods=["GET"], name="health")
    async def health(_: Request) -> JSONResponse:
        return JSONResponse(
            {
                "status": "healthy",
                "service": "asd-marketplace-mcp",
                "transport": "streamable-http",
                "mcp_path": resolved.path,
                #"registered_tools": len(REGISTERED_CHUFENG_TOOLS) + len(REGISTERED_RYAN_TOOLS),
                "registered_tools": len(await server.list_tools()),

            }
        )

    return server


mcp = create_server()


def main() -> None:
    """Run the shared MCP service over Streamable HTTP."""

    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger(__name__).info(
        "Starting %s at %s",
        SERVER_NAME,
        settings.endpoint_url,
    )
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
