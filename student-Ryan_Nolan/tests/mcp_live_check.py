"""Live check: Flask route -> real MCP server -> Product Database.

Needs the Product Database (6001) and MCP server (8765) running.
Run from the repo root:
    python3 student-Ryan_Nolan/tests/mcp_live_check.py
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

os.environ["MCP_ENABLED"] = "true"
os.environ.setdefault("MCP_SERVER_URL", "http://127.0.0.1:8765/mcp")

from app import create_app  # noqa: E402

app = create_app()
app.config["TESTING"] = True
client = app.test_client()

CHECKS = [
    ("GET", "/api/inventory/mcp/status", None),
    ("GET", "/api/inventory/mcp/tools", None),
    ("POST", "/api/inventory/mcp/tools/call",
     {"tool": "ryan_get_low_stock_items", "arguments": {"limit": 3}}),
    ("POST", "/api/inventory/mcp/tools/call",
     {"tool": "ryan_calculate_restock_order", "arguments": {"product_id": 13}}),
    ("POST", "/api/inventory/mcp/tools/call",
     {"tool": "ryan_get_product_inventory", "arguments": {"product_id": 0}}),
    ("POST", "/api/inventory/mcp/tools/call",
     {"tool": "chufeng_search_products", "arguments": {}}),
]

for method, path, body in CHECKS:
    print("=" * 70)
    print(f"{method} {path}")
    if body:
        print(f"body: {json.dumps(body)}")
    response = client.open(path, method=method, json=body)
    print(f"HTTP {response.status_code}")
    print(json.dumps(response.get_json(), indent=2))