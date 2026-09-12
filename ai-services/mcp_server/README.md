# ASD Marketplace MCP Server

This is the single shared, non-containerised MCP server used by the student
features. It exposes Streamable HTTP at `http://127.0.0.1:8765/mcp` and a
health endpoint at `http://127.0.0.1:8765/health` by default.

## Run locally

Start the Product Database API first. Then, from the repository root:

```powershell
python -m pip install -r ai-services/mcp_server/requirements.txt
Set-Location ai-services
python -m mcp_server.server
```

When the application microservices run through Docker Compose, publish the
Product Database API and bind the host-side MCP server to all local interfaces:

```powershell
docker compose up --build -d
$env:MCP_HOST = "0.0.0.0"
$env:PRODUCT_DATABASE_API_URL = "http://127.0.0.1:6001/api/database"
Set-Location ai-services
python -m mcp_server.server
```

The MCP process still runs directly on the host. It is intentionally not a
Docker Compose service. The containerised shared backend reaches it through
`http://host.docker.internal:8765/mcp`. DNS rebinding protection remains
enabled and permits only the configured local/Docker host names.

The service can be configured with these environment variables:

| Variable | Default |
| --- | --- |
| `MCP_HOST` | `127.0.0.1` |
| `MCP_PORT` | `8765` |
| `MCP_PATH` | `/mcp` |
| `PRODUCT_DATABASE_API_URL` | `http://127.0.0.1:6001/api/database` |
| `MCP_REQUEST_TIMEOUT_SECONDS` | `10` |
| `MCP_LOG_LEVEL` | `INFO` |

## Registered Chufeng tools

- `chufeng_search_products`
- `chufeng_get_product_details`
- `chufeng_check_product_stock`
- `chufeng_calculate_cart_summary`

All four tools are read-only and use the Product Database API rather than
opening the database directly. Other student-owned tools should be added to
their matching module under `tools/` and registered in `server.py`.
