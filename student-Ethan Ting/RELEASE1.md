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

## Reproduce validation

```bash
.venv311/bin/python -m pytest 'student-Ethan Ting/tests' ai-services/mcp_server/tests ai-services/rag_server/tests -q
OLLAMA_MODEL=llama3.1:8b .venv311/bin/python ai-services/agentic_loop.py \
  --feature 'student-Ethan Ting' --mode mcp
OLLAMA_MODEL=llama3.1:8b .venv311/bin/python ai-services/agentic_loop.py \
  --feature 'student-Ethan Ting' --mode rag
```

The loop saves its reports to `docs/evidence/agentic/`. Check the MCP report
for all five threshold probes and the RAG report for a real cited answer plus
a model-free insufficient-context response. These direct service checks and
browser interactions are separate evidence. Both checks read approved sources;
neither changes customer balances or account data. The confidence label is a
retrieval similarity category, not a guarantee that every generated sentence
is true.

CI uses `.github/workflows/student-3.yml`, displayed as Ethan Ting - Customer
Accounts and Loyalty CI. It disables live AI, MCP and RAG calls while still
running deterministic contract tests and building all three feature images.
