# Ethan Ting Release 1: local run and validation

The three Ethan feature services run in Docker Compose. Ollama, the one shared
MCP server, the one shared RAG server, and the shared review loop run directly
on the host. The browser uses port 8003 and calls Ethan's backend on port 6002.
The backend reaches the host services through `host.docker.internal`.

## Prepare the host

Use Python 3.11. From the repository root on macOS:

```bash
brew install python@3.11
/opt/homebrew/bin/python3.11 -m venv .venv311
.venv311/bin/python -m pip install -r requirements.txt -r ai-services/rag_server/requirements.txt
ollama list
```

The local `llama3.1:8b` model is used for this feature's RAG answers and
reviews. If it is absent, install it with `ollama pull llama3.1:8b` first.
Leave Ollama running. Start each of the next long-running host processes in
its own terminal from the repository root:

```bash
MCP_HOST=0.0.0.0 PYTHONPATH=ai-services .venv311/bin/python -m mcp_server.server
OLLAMA_MODEL=llama3.1:8b PYTHONPATH=ai-services .venv311/bin/python -m rag_server.rag_http_server
```

The MCP bind permits the Docker host bridge to reach port 8765. Keep it on a
trusted local machine. RAG uses port 5003. Refresh its approved Ethan scope
after starting it and whenever the source guide changes:

```bash
curl -X POST http://127.0.0.1:5003/refresh \
  -H 'Content-Type: application/json' \
  -d '{"scope":"ethan_ting_accounts_loyalty"}'
docker compose up -d --build ethan-database ethan-backend ethan-frontend
docker compose ps
```

Open `http://localhost:8003/admin-loyalty.html` as an administrator to check
the MCP tier for a selected customer. The protected backend reads the current
balance and sends only that integer to the shared tool. Open
`http://localhost:8003/admin.html` and use the Accounts and loyalty guide for
RAG. A Gold-tier question should show a cited answer and retrieval confidence.
An unrelated astronomy question should show insufficient context with no
citations. The assistant's original Customer Insight AI must still work.

Accounts and Loyalty now reuse `frontend/js/customer-assistant.js` rather than
copying the assistant into each page. Select a customer once; the selection is
retained within the browser tab when moving between the two pages. The compact
tabs separate Customer tools, Ask AI and Ask the guide. Customer tools provide
Check progress and Point history, with loading messages, empty states and retry.
Only an edit proposal displays a confirmation step. Suggested customer questions
use the selected account rather than a hard-coded demo address.

The same RAG guide covers registration, profile edits, password-change requirements,
sign-in limitations, tier thresholds, manual point adjustments and viewing history.
Guide example buttons help administrators find those instructions. It explicitly
distinguishes password changes from unimplemented password recovery, and manual
points from unimplemented purchase rewards. It contains no customer records or
passwords. After changing approved Markdown, use Refresh guide to re-index it.
Retrieval confidence describes source matching, not a guarantee of answer accuracy.

HTMX uses the existing `shared/js/htmx.min.js` asset to fetch an administrator-only
HTML fragment every 30 seconds and when Check connections is pressed. The feature
Nginx configuration proxies `/api/admin/assistant/service-status` to Ethan's
backend on the same origin, preserving the signed session cookie. The backend
performs bounded, read-only health checks without sending customer data or
cookies to MCP/RAG. Badges show Reachable, Unavailable or Disabled. Reachable
means the service responded; it does not guarantee tool execution, model
availability, retrieval quality or answer correctness. Status requests are
not cached and background-tab polls are skipped.

The same assistant now supports a second MCP tool: ask "Show the last 5 point
changes for Customer #2", or identify a customer by exact full name or email.
It shows the recorded history in a read-only table. The history tool needs an
active admin session, forwards it only through HTTP transport, and exposes
only dates, point changes and reasons. It does not generate transactions with
Ollama. The MCP host uses `MCP_CUSTOMER_API_URL=http://127.0.0.1:6002` by default.

The Point history quick action uses `POST /api/admin/mcp/loyalty-history` with
`user_id` and an optional bounded `limit` (1 to 20; default 5). It shares the
chat's history validation and admin checks, but works without AI Mode when MCP
is enabled. Explicit history questions in the original AI chat still work.

Check progress with AI sends `use_ai: true` to the existing MCP tier endpoint.
After the MCP result passes validation, local Ollama independently calculates
the tier, next tier and points remaining from the balance and fixed rules.
Only the balance is sent to the model, not customer identity or session data.
The backend accepts the AI calculation only when its strict integer values
match the validated rule-based result. The UI identifies a verified calculation
and actual model; disabled, unavailable or incorrect AI clearly falls back to
the MCP result and offers retry where appropriate. Point history remains a
read-only database lookup, not AI-generated records. No points are awarded.

## Reproduce validation

```bash
.venv311/bin/python -m pytest 'student-Ethan Ting/tests' ai-services/mcp_server/tests ai-services/rag_server/tests -q
```

The MCP review includes an authenticated history probe for the seeded Customer
#2. Supply an active administrator cookie through `ETHAN_VALIDATION_SESSION`
in the review process environment, never in committed files or tool arguments.
For the local demo seed account, this command signs in and captures the cookie
without printing it (replace credentials if the local seed password changed):

```bash
export ETHAN_VALIDATION_SESSION="$(.venv311/bin/python - <<'PY'
import http.cookiejar, json, urllib.request
jar = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
request = urllib.request.Request('http://127.0.0.1:6002/api/login',
    data=json.dumps({'email': 'admin@asd.local', 'password': 'AdminPass!2026'}).encode(),
    headers={'Content-Type': 'application/json'})
with client.open(request, timeout=10):
    pass
print(next(cookie.value for cookie in jar if cookie.name == 'ethan_session'))
PY
)"
OLLAMA_MODEL=llama3.1:8b .venv311/bin/python ai-services/agentic_loop.py \
  --feature 'student-Ethan Ting' --mode mcp
unset ETHAN_VALIDATION_SESSION
OLLAMA_MODEL=llama3.1:8b .venv311/bin/python ai-services/agentic_loop.py \
  --feature 'student-Ethan Ting' --mode rag
```

The loop saves its reports to `docs/evidence/agentic/`. Check the MCP report
for all five threshold probes and the authenticated history probe, and the RAG report for a real cited answer plus
a model-free insufficient-context response. These direct service checks and
browser interactions are separate evidence. Both checks read approved sources;
neither changes customer balances or account data. The confidence label is a
retrieval similarity category, not a guarantee that every generated sentence
is true.

CI uses the assigned `.github/workflows/student-3.yml`, displayed as Ethan Ting - Customer
Accounts and Loyalty CI. It disables live AI, MCP and RAG calls while still
running deterministic contract tests and building all three feature images.
