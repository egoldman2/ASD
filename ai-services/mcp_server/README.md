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
| `MCP_SUPPORT_API_URL` | `http://127.0.0.1:6005` |
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

## Registered Ethan Goldman tools

- `ethan_goldman_search_tickets`: filtered ticket summaries; default 20,
  maximum 50 rows, offset at most 10,000, no conversation bodies.
- `ethan_goldman_get_ticket_context`: positive ticket ID and the latest
  messages; default 20, maximum 50, displayed chronologically.
- `ethan_goldman_get_queue_summary`: full-set status/priority totals,
  unresolved and unresolved-unassigned counts, with optional category/assignee.
- `ethan_goldman_get_tickets_needing_attention`: unresolved tickets with every
  applicable review reason, ordered by urgent/high/medium/low/unclassified,
  oldest activity, then ticket ID before paging. Activity includes ticket updates
  and messages. Solved tickets are excluded. Inactivity defaults to 48 hours
  (allowed 1–720); this is a review heuristic, not a promised SLA.

All four tools require an `ethan_session` cookie on the MCP HTTP request. The host
server forwards that request's cookie to protected Customer Support API reads;
the API verifies the session and admin role again. Cookies are never accepted
as tool arguments or stored between requests. The backend removes customer
identity fields and redacts message/subject content before returning results.
Search results include total matches and continuation metadata; context
includes the full message count and a truncation flag. SQL limits are applied
inside the independent database service. Existing ticket CRUD is unchanged.

## Support model-driven assistant

The support backend exposes staff-only `POST /api/support/admin/mcp/assistant`
with JSON `{"question": "How does our support workload look?"}` and an optional
positive `ticket_id`. Both `AI_MODE_ENABLED` and `MCP_ENABLED` must be enabled.
`MCP_ASSISTANT_MODEL` defaults to the host Ollama model `qwen2.5:3b`; install
that model locally before using this endpoint. `OLLAMA_URL` selects the host
runtime, with `host.docker.internal` used by the containerised backend.

The model receives the four discovered support schemas, chooses real MCP calls,
and generates an answer from their returned evidence. A request permits at most
three tool calls and four model requests, with one correction and a total
`MCP_ASSISTANT_TIMEOUT_SECONDS` deadline (default 75, maximum 90 seconds).
Assistant reads cap at ten tickets or six conversation messages per call.
Final scalar citations and ticket references are checked against observations;
the response includes those observations and actual call counts. Unavailable,
partial, disabled and timeout states return explicit errors without a fabricated
successful answer. This assistant cannot edit tickets or send replies.

The staff queue (`staff.html`) provides the question form and direct search,
summary and attention controls. The ticket workspace (`staff-ticket.html`)
adds the conversation read and selected-ticket question. HTMX requests use
staff-authenticated support UI routes; example buttons only fill the question.
Generated answers show the actual read results and verified scalar references.
Conversation model input excludes timestamps to keep summaries focused on
message content and state; the full read evidence still displays timestamps.
Scalar/reference validation does not prove every prose sentence true, so staff
should review the data before acting. Existing reply/edit/triage controls remain
separate from these read-only helpers.
Labelled numeric queue counts and duplicate ticket-reference lists are also
checked in generated prose. A native draft can lead to a separate structured
generation request; that draft is never displayed as an answer, and all requests
still share the four-request limit and one verification correction.

The deterministic contract suite runs without a model. To also test actual
host inference through temporary authenticated support and MCP services:

```bash
RUN_LIVE_MCP_AI=1 python -m pytest 'student-Ethan Goldman/tests/test_goldman_mcp_assistant.py' -q
```

## Feature-aware runner validation

MCP mode in `ai-services/agentic_loop.py` uses the selected feature's
`mcp_rules.required_tools` allowlist with the shared protocol client. Configure
`source_files` roles (`server`, `tools`, `client`, `frontend`, `routes`, optional
`controller`, `compose`), `frontend_route_prefix` and `backend_client_marker`
for source checks. The runner inspects the configured trusted local server
factory's SDK definitions without starting a server or executing tools; those
checks remain source evidence, including when MCP is disabled.

`probes` accepts at most ten objects with `name`, `tool`, `arguments` and an
optional `expect` list of exact typed `{ "path": "result.total", "value": 12 }`
checks. Paths address response dictionaries and numeric list indexes. Every
configured call must be allowlisted, discovered as read-only/non-destructive,
and return a matching successful read-only envelope. Each outcome is retained
independently, so a failed check does not hide later probes. Existing
`probe_tool`/`probe_arguments` configuration remains supported.

Private feature reads can configure `request_context` with a `cookie_name` and
`cookie_env` identifying an environment variable containing a current staff
session. Supply that value locally; never put it in JSON configuration, prompts
or evidence files. The same separate HTTP context is used for protocol calls
and optional application probes. Missing/expired/customer sessions cannot
validate protected support reads. Saved evidence redacts session values and
private identity/conversation fields; bounded direct-call outcomes include
expected/observed checks and a response digest.

An optional `assistant_probes` list supplies `url`, `origin`, question `payload`,
`expected_tools` and optional `expect` checks. It targets a local read-only
`/mcp/assistant` endpoint and verifies an answered application trace: actual
model name, two to four model requests, one to three allowlisted tool calls,
matching observations and exact scalar fact references. The support endpoint
implements this trace contract. Other feature owners must provide equivalent
application evidence before their AI integration can pass. URLs must be local,
contain no credentials/query parameters, and HTTP redirects are never followed.
Each application probe has a bounded timeout (default/maximum 95 seconds).

Runtime evidence separates `required_tools_discovered`, `probe_complete`,
`all_required_tools_probed` and `assistant_verified`. Discovery proves no tool
execution; a catalogue single-probe success does not mean all four tools ran.
`MCP_ENABLED=false` skips live validation while retaining source checks.
`AI_MODE_ENABLED=false` skips assistant inference while allowing configured
read-only protocol checks when MCP is enabled. Unavailable, skipped and failed
probes remain evidence limitations. Review-model prose is separate from the
application model's observed tool selections and generated answer.

The opt-in support runner acceptance captures actual host-model outputs and
real protocol/application results from isolated seeded services:

```bash
RUN_LIVE_MCP_AI=1 python -m pytest 'student-Ethan Goldman/tests/test_agentic_mcp_validation.py' -q
```

Goldman's persistent runner configuration and mode prompts are added in the
following feature configuration stage; the shared runner is already tested
against both catalogue and support configurations.

## Registered Ethan Ting tools

- `ethan_ting_calculate_loyalty_tier`

This read-only tool accepts a non-negative `points_balance` and returns the
Bronze, Silver, or Gold tier and progress to the next tier. It uses the same
500/1000-point thresholds as the customer database service. It does not fetch
or expose customer account records. Frontend/backend integration is a
separate step.
