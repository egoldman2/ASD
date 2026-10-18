# S15a — actual local runtime evidence (human review pending)

Captured on 17 October 2026, Australia/Sydney (UTC timestamps in JSON). This is
fresh seeded/synthetic data in `asd-release2-local`. Application source is
`37e859a36492aeaf20994556750d4a5acb66a05a`; the subsequent `d8724d2` pipeline-only
repair leaves every application source directory identical. This checkpoint does
not establish AWS availability, a main deployment, or a human decision.

## Observed results

| Path | Actual result | Evidence |
| --- | --- | --- |
| Integrated application | 13 services running; configured health checks pass | [Runtime](runtime-baseline.json) |
| Customer UI | Shared-home navigation, sign-in, own list, creation/read of #2013 | [Creation](customer-created-ticket.jpg) |
| Staff UI | Explicit Product/Medium/Pending triage and a synthetic staff reply | [Controls](manual-triage-reply.jpg) |
| Advisory analysis | `qwen2.5:0.5b`, HTTP 200, validated source/action codes, no retry | [API](advisory-analysis-api.json), [UI text](advisory-analysis-ui.txt) |
| MCP assistant | Narrow question answered; 3 model requests, 1 real queue-summary tool call | [API](mcp-verified-api.json), [UI](mcp-verified.jpg) |
| Grounded RAG | `qwen2.5:3b`, 5 passages, one generation, approved citation and correct ticket limits | [API](rag-grounded-api.json), [UI](rag-grounded.jpg) |
| Unsupported RAG | Existing `quasar orbital spectroscopy wavelengths` case has no citations/model invocation | [API](rag-insufficient-api.json), [UI](rag-no-generation.jpg) |
| Read-only safety | Exact ticket object unchanged across native advisory/MCP/RAG calls | [Comparison](readonly-business-verification.json) |
| UI workflow | Real Planner/Worker Qwen 3B and Reviewer Llama 3.1 8B; awaiting human review | [Full result](ui-workflow-detail.json), [Controls](ui-reviewer-controls-awaiting-human.jpg) |
| Terminal workflow | Same single HTTP server/log writer, separate actual inference; awaiting human review | [Full result](terminal-workflow-create.json) |
| Workflow safety | Both proposals preserve the already-triaged ticket and two messages | [Comparison](both-workflows-business-verification.json) |
| Persistence | Old admin/customer sessions, ticket and both model outputs survive restart and scoped recreation | [Verification](persistence-verification.json) |
| Cleanup | A separate owned disposable API ticket is deleted and verified 404; #2013 retained | [Verification](disposable-cleanup-verification.json) |
| Local exposure | All 11 published bindings restricted to 127.0.0.1; exact orders rows preserved | [Verification](loopback-hardening-verification.json) |

The first broad MCP question returned **Partial**, with its real tool evidence
still visible: [captured UI](mcp-partial.jpg), [text](mcp-partial-ui.txt). It is not
a passing answer. The later narrow request succeeded. The first unsupported
astronomy phrase retrieved weak context and the model abstained
([UI](rag-model-abstention.jpg)); the existing canonical negative then demonstrated
model-free abstention. These are separate actual requests, not one reconstructed
successful trace. UI and API captures also represent separate inference calls.

Both Worker outputs recommend requesting details that staff have already asked
for; the terminal output does not supply an explicit reply draft. Reviewers
recommend acceptance, but those are model recommendations. The real human
question remains pending. No Accept/Partial accept/Reject record is generated on
Ethan's behalf, and no proposed response is sent automatically.

## Actual host/Compose arrangement

Ollama 0.35.1 was already running on host loopback; its existing process and
installed models were retained. MCP, RAG and Multi-Agent run as three separate
host terminal processes on 127.0.0.1:8765/5003/5004. Docker-to-host access was
verified. No model service is in Compose. RAG uses an isolated temporary index;
Multi-Agent uses the ignored project-local log directory below. Only that one
server writes the workflow JSONL files; the terminal workflow uses HTTP.

```bash
# Root Compose, isolated volumes, private generated session key and loopback ports.
# The private env is deliberately absent from Git; it contains the session key.
docker compose --project-name asd-release2-local \
  --env-file /private/tmp/asd-release2-s15/demo.env \
  --file docker-compose.yml \
  --file /private/tmp/asd-release2-s15/loopback.compose.yml \
  up -d --no-build --wait --wait-timeout 180

PYTHONPATH=ai-services MCP_HOST=127.0.0.1 python -m mcp_server.server

PYTHONPATH=ai-services RAG_HOST=127.0.0.1 AI_MODE_ENABLED=true RAG_ENABLED=true \
  RAG_CHROMA_PATH=/private/tmp/asd-release2-s15/chroma \
  RAG_AUDIT_PATH=/private/tmp/asd-release2-s15/rag-audit.jsonl \
  OLLAMA_MODEL=qwen2.5:3b RAG_REQUEST_TIMEOUT_SECONDS=90 \
  python -m rag_server.rag_http_server

PYTHONPATH=ai-services MULTI_AGENT_HOST=127.0.0.1 \
  MULTI_AGENT_LOG_DIR="$PWD/.aws-deployment/release2-local-multi-agent" \
  OLLAMA_PLANNER_MODEL=qwen2.5:3b OLLAMA_WORKER_MODEL=qwen2.5:3b \
  OLLAMA_REVIEWER_MODEL=llama3.1:8b OLLAMA_TIMEOUT_SECONDS=90 \
  python -m multi_agent_server.app
```

Use the fresh Python 3.11 environment described in the ledger. The safe
[as-run override](loopback.compose.yml) requires Compose's supported `!override`
port replacement (observed Compose 5.3.1). Root Compose initially published on all
interfaces. Before recreation, SQLite's backup API preserved the owned orders
file, verified integrity and row hashes, then mounted it at `/data/orders.db`.
Other application databases retained their project-specific named volumes.
Root Compose source and the three unrelated user containers were preserved.
Always include the override when operating this demo; omitting it restores the
base binding/storage configuration. Private env/cookies/backups are never copied
into this evidence folder. These commands use localhost demo data, not AWS.

## Preliminary Agentic Loop and native records

The real CLI ran selected workflow `3a970ca5-0b90-4e7f-ab84-cd7beb089c28` through
`multi-agent` mode with `qwen2.5:3b`. Only the two log paths were temporarily set
to `.aws-deployment/release2-local-multi-agent/`; the original config was restored
byte-for-byte. The exact runtime-config hash and command are in the capture.

- [Native generated report](../../agentic/ethan-goldman-customer-support-multi-agent-20261017-114350-732739.md)
- [Full console](preliminary-agentic-console.txt) and [deterministic evidence](preliminary-agentic-validation.json)
- [Original history bytes](workflow_history-before-human.jsonl) and [audit bytes](coordination_audit-before-human.jsonl)

API scope/evidence, all three agents, history and audit validate. Human review is
absent and `review_evidence_complete=false`. CLI exit 0 means execution completed,
not human acceptance or a passing release. Model source-citation grounding failed;
the guard retained a deterministic final summary and the original model drafts
remain in the report. This preliminary result must be rerun after actual human
review and is not the final S17 review.

## Remaining boundaries

The browser permanent-delete button was not exercised; cleanup used the existing
API on a separate owned disposable record. Keep #2013 for genuine human review.
Suppliers have 5 seeded rows; the owner must resolve the required minimum. The
legacy/current cart tables contain 10/0 rows and need owner clarification. Accounts
and Inventory do not declare Multi-Agent flags in root Compose; their integration
is not inferred. Other owners still supply their missing operation/report evidence.
The homepage retains legacy Release 0/group7 labels; these do not confirm official
allocation. No attendance, video, final PDF or release decision is claimed.

The [manifest](s15a-manifest.json) identifies each artifact/hash. Screenshots are
unaltered browser JPEGs. Native JSON excludes cookies/response headers; credential
substring checks and a separate all-files detector review precede commit.
