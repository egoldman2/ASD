import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "http://127.0.0.1:8765/mcp"


async def main():
    async with streamablehttp_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("REGISTERED TOOLS:")
            for t in tools.tools:
                print(f"  - {t.name}")

            print("\nCALLING howard_get_order_status(order_id=1):")
            res = await session.call_tool(
                "howard_get_order_status", {"order_id": 1}
            )
            if res.structuredContent is not None:
                print(json.dumps(res.structuredContent, indent=2))
            for block in res.content:
                if getattr(block, "type", None) == "text":
                    print(block.text)


asyncio.run(main())
