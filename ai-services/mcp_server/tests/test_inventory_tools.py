"""Terminal validation for Ryan's inventory MCP tools.

Run from ai-services/ with the MCP server and Product Database running:
    python -m mcp_server.validate_ryan_tools
"""

from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL = "http://127.0.0.1:8765/mcp"

CASES = [
    ("1. Low stock list", "ryan_get_low_stock_items", {"limit": 20}, True),
    ("2. Product inventory", "ryan_get_product_inventory", {"product_id": 3}, True),
    ("3. Supplier details", "ryan_get_supplier_details", {"supplier_id": 5}, True),
    ("4. Restock order", "ryan_calculate_restock_order", {"product_id": 13}, True),
    ("5. Bad product_id (0)", "ryan_get_product_inventory", {"product_id": 0}, False),
    ("6. Missing product (99999)", "ryan_get_product_inventory", {"product_id": 99999}, False),
    ("7. Limit too large (500)", "ryan_get_low_stock_items", {"limit": 500}, False),
    ("8. Bad supplier_id (-1)", "ryan_get_supplier_details", {"supplier_id": -1}, False),
]


def _envelope(result) -> dict:
    """Extract the tool's response envelope from an MCP call result."""
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        # FastMCP may wrap dict returns as {"result": {...}}
        if "success" in structured:
            return structured
        if isinstance(structured.get("result"), dict):
            return structured["result"]
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            return json.loads(text)
    raise ValueError("No parsable content in tool result.")


async def main() -> int:
    failures = 0
    async with streamablehttp_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            print("Registered tools:")
            for name in names:
                print(f"  - {name}")
            print()

            for label, tool, args, expect_success in CASES:
                print("=" * 70)
                print(f"{label}\n  tool: {tool}\n  args: {json.dumps(args)}")
                try:
                    result = await session.call_tool(tool, args)
                    envelope = _envelope(result)
                except Exception as exc:  # protocol-level rejection
                    if not expect_success:
                        print(f"  REJECTED at protocol level (expected): {exc}")
                        print("  PASS")
                        continue
                    print(f"  ERROR: {exc}")
                    print("  FAIL")
                    failures += 1
                    continue

                print(json.dumps(envelope, indent=2))
                ok = envelope.get("success") is expect_success
                print("  PASS" if ok else "  FAIL")
                failures += 0 if ok else 1

    print("=" * 70)
    print(f"{len(CASES) - failures}/{len(CASES)} cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))