# Release 1 Shared MCP Integration Design

## Purpose

Extend the Release 0 marketplace with one shared, local, non-containerised MCP server. Each student contributes tools for their own feature, while every frontend invokes the shared MCP server only through its backend/API. This design covers the shared server framework and Chufeng's Product Catalogue and Shopping Cart integration.

## Constraints

- Preserve all Release 0 functionality and AI-Mode behaviour.
- Run one shared MCP server outside Docker Compose.
- Keep student frontend, backend/API, and database services containerised.
- Do not permit a browser to call the MCP server directly.
- Retain MCP integration code but disable live MCP access during CI/CD.
- Return structured tool results and document tool inputs, outputs, boundaries, and failure behaviour.
- Capture terminal, frontend, backend, protocol, and Agentic Loop validation evidence.

## Architecture

```text
Chufeng Frontend (:8001)
        |
        | HTTP JSON
        v
Shared Backend/API (:5000, Docker)
        |
        | MCP client over Streamable HTTP
        v
Shared MCP Server (:8765/mcp, host process)
        |
        | bounded HTTP request
        v
Product Database API (:6001, Docker; localhost-bound host port)
```

The backend reaches the host MCP server through `host.docker.internal`. The MCP server reaches the Product Database API through a port bound only to `127.0.0.1`. The MCP server is not defined as a Docker Compose service.

## Shared MCP Server

The server uses the official Python MCP SDK and exposes a stateless Streamable HTTP endpoint with JSON responses. `server.py` owns server construction, transport configuration, health reporting, and registration of tool modules.

Each student owns one module under `ai-services/mcp_server/tools/`:

- `chufeng_catalogue.py`
- `ryan_inventory.py`
- `ethan_ting_customer.py`
- `howard_orders.py`
- `ethan_goldman_support.py`

Tool modules use lowercase snake_case filenames without spaces. All tools return the shared success/error response shape and validate arguments before contacting a downstream service.

## Chufeng Tools

The initial Chufeng tool set is read-only:

1. `search_products`: filter catalogue products by text and optional bounded criteria.
2. `get_product_details`: return one existing product by positive integer ID.
3. `check_product_stock`: compare a positive requested quantity with current stock.
4. `calculate_cart_summary`: optional deterministic calculation for supplied product IDs and quantities; it does not mutate a cart.

These tools may read catalogue data but may not create, update, or delete products, carts, orders, files, or configuration. They may not invent products or expose internal errors.

## Chufeng Backend Integration

The Chufeng backend adds:

- `services/mcp_client.py`: MCP connection, tool discovery, tool invocation, timeout, and protocol error translation.
- `controllers/mcp_controller.py`: request validation, Chufeng tool allowlist, response mapping, and safe error handling.
- `routes/mcp_routes.py`: a JSON API used by the frontend.

The root `app.py` registers the new blueprint. `MCP_ENABLED=false` prevents all live MCP connections and returns a stable disabled response. The backend never accepts an arbitrary tool name outside the Chufeng allowlist.

## Frontend Integration

`student-Chufeng/frontend/js/mcp-tools.js` owns MCP form behaviour and calls only the Chufeng backend. The existing catalogue page gains an MCP Product Tools panel with tool selection, bounded inputs, loading state, structured result display, disabled state, and safe error messages. Existing catalogue, cart, and AI Product Assistant behaviour remains unchanged.

## Error Handling

The integration distinguishes:

- invalid or missing arguments: HTTP 400;
- disallowed tool: HTTP 403;
- tool or record not found: HTTP 404 where applicable;
- MCP disabled: HTTP 503 with a stable configuration message;
- MCP connection/timeout/protocol failure: HTTP 502 or 503;
- downstream Product Database API failure: structured tool failure without stack traces.

Logs record timestamp, tool name, outcome, and duration. Logs do not include secrets, authentication cookies, or unnecessary customer data.

## Testing

Shared MCP tests cover tool discovery, protocol invocation, response structure, argument validation, tool boundaries, missing records, stock edge cases, timeouts, and downstream failures.

Chufeng tests cover the backend route, allowlist, disabled mode, mocked MCP client, invalid MCP responses, and unavailable server. A live integration test is opt-in through `RUN_LIVE_MCP=1`; CI runs deterministic tests with `MCP_ENABLED=false`.

The existing Release 0 catalogue, cart, AI, Docker build, and Agentic Loop tests must continue to pass.

## Agentic Validation and Evidence

The shared Agentic Loop gains an `mcp` mode. It collects registered-tool metadata and real execution evidence, checks tool boundaries and structured results, and saves an evidence-based review. Chufeng receives `student-Chufeng/agentic/mcp_prompt.txt` and corresponding configuration.

Evidence is stored under `docs/evidence/mcp/` and covers terminal validation, frontend/backend integration, tool-boundary analysis, Agentic validation, risks, corrections, and retesting. Architecture and request-flow documentation is stored under `docs/architecture/`.

## Planned File Changes

New shared server files:

```text
ai-services/mcp_server/__init__.py
ai-services/mcp_server/README.md
ai-services/mcp_server/requirements.txt
ai-services/mcp_server/server.py
ai-services/mcp_server/config.py
ai-services/mcp_server/response.py
ai-services/mcp_server/tools/__init__.py
ai-services/mcp_server/tools/chufeng_catalogue.py
ai-services/mcp_server/tools/ryan_inventory.py
ai-services/mcp_server/tools/ethan_ting_customer.py
ai-services/mcp_server/tools/howard_orders.py
ai-services/mcp_server/tools/ethan_goldman_support.py
ai-services/mcp_server/tests/__init__.py
ai-services/mcp_server/tests/conftest.py
ai-services/mcp_server/tests/test_server_protocol.py
ai-services/mcp_server/tests/test_tool_boundaries.py
ai-services/mcp_server/tests/test_catalogue_tools.py
```

New Chufeng files:

```text
student-Chufeng/backend/services/__init__.py
student-Chufeng/backend/services/mcp_client.py
student-Chufeng/backend/controllers/mcp_controller.py
student-Chufeng/backend/routes/mcp_routes.py
student-Chufeng/frontend/js/mcp-tools.js
student-Chufeng/tests/test_mcp_client.py
student-Chufeng/tests/test_mcp_routes.py
student-Chufeng/agentic/mcp_prompt.txt
```

Existing files to update during implementation:

```text
app.py
requirements.txt
docker-compose.yml
.github/workflows/Chufeng.yml
student-Chufeng/frontend/index.html
student-Chufeng/frontend/css/styles.css
student-Chufeng/tests/conftest.py
student-Chufeng/tests/test_agentic_loop.py
student-Chufeng/agentic/review_config.json
ai-services/agentic_loop.py
```

Documentation/evidence scaffolding:

```text
docs/architecture/release1-mcp-architecture.md
docs/architecture/release1-mcp-request-flow.md
docs/evidence/mcp/README.md
docs/evidence/mcp/tool-boundary-analysis.md
docs/evidence/mcp/terminal-validation.md
docs/evidence/mcp/frontend-integration.md
docs/evidence/mcp/agentic-validation.md
docs/evidence/mcp/integration-report.md
```

## Ownership

Chufeng owns the shared server framework, response contract, Chufeng catalogue tools, Chufeng backend/frontend integration, tests, and MCP validation scaffolding. Other students own the implementation and feature-specific tests of their tool modules. Shared changes are reviewed and merged through the group repository so each contribution remains identifiable.
