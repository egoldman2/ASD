# Ethan Goldman Customer Support validation

The shared host runner supports `database`, `implementation`, `architecture`,
`devops`, `mcp` and `rag` for this feature. MCP/RAG acceptance uses actual local
inference; the review model's prose is a separate review of collected evidence.
Feature services remain containerised in deployment. Ollama, the shared MCP
server, shared RAG service and this runner run on the host.

## Seeded acceptance

The persistent configuration targets isolated services using the unchanged
support seed, rather than arbitrary customer data. Expected reads are:

| Read | Expected seed observation |
| --- | --- |
| Delivery search | 2 matching tickets |
| Ticket 2002 context | 3 messages; a two-message read reports truncation |
| Queue summary | 12 total, 9 unresolved, 5 unresolved/unassigned |
| Attention | 9 unresolved tickets; 48-hour inactivity heuristic |
| No-match search | 0 tickets |

Both delivery tickets are assigned. The AI question “Find unassigned delivery
tickets” therefore has an explained zero result; the separate positive delivery
search proves that retrieval works. The four configured model questions cover
search, conversation, workload and attention reasons. Each must record an actual
model-selected call and a model-generated answer from returned observations.
No tools edit tickets or send replies. Counts from a changed live dataset do not
satisfy these seed checks. Never reset an existing customer database merely to
make validation pass.

RAG uses only `ethan_goldman_support` approved Markdown. A supported creation
question must cite retrieved guidance for 5–160 subject and 1–2000 initial
message characters. The unrelated astronomy question must return insufficient
context without generation. Confidence measures retrieval similarity, not
universal correctness of generated prose.

## Host CLI

Install the project and shared host runtime requirements and start the host
model/MCP/RAG services against the intended seeded feature stack. Select an
installed local model; acceptance uses `qwen2.5:3b`.

```bash
export AI_MODE_ENABLED=true MCP_ENABLED=true RAG_ENABLED=true
export OLLAMA_MODEL=qwen2.5:3b MCP_ASSISTANT_MODEL=qwen2.5:3b
python ai-services/agentic_loop.py --feature 'student-Ethan Goldman' --mode mcp
python ai-services/agentic_loop.py --feature 'student-Ethan Goldman' --mode rag
```

Before MCP mode, supply `SUPPORT_VALIDATION_SESSION` in the process environment
from a current admin session for that acceptance stack. Never place its value
in tool arguments, JSON config, prompts, command arguments or saved evidence.
`MCP_SERVER_URL` and `RAG_SERVER_URL` can select isolated local service ports.
`SUPPORT_VALIDATION_ASSISTANT_URL` optionally overrides all four question
requests; its default is `http://127.0.0.1:6005/api/support/admin/mcp/assistant`.
Targets must remain local read-only MCP assistant endpoints. The configured
Origin is `http://localhost:8005`, matching the support frontend.

Actual CLI outputs are saved under `docs/evidence/agentic/` with Ethan Goldman's
name and selected mode. Source markers, discovery, direct probes, application AI
and unsupported handling have separate outcomes. Missing sessions, services,
models or failed seed checks remain failures/limitations. The runner can replace
inadequate review prose with a verified evidence summary; it cannot manufacture
application results. Both integrations disabled in CI keep ordinary CRUD usable;
static collectors can run without live services, while the full review CLI
requires an enabled local review model.

## Repeatable isolated acceptance

Deterministic contracts and opt-in actual inference are separate:

```bash
AI_MODE_ENABLED=false MCP_ENABLED=false RAG_ENABLED=false \
  python -m pytest 'student-Ethan Goldman/tests/test_goldman_release1_validation.py' -q
RUN_LIVE_RELEASE1_VALIDATION=1 \
  python -m pytest 'student-Ethan Goldman/tests/test_goldman_release1_validation.py::test_actual_cli_modes_record_four_native_mcp_examples_and_grounded_rag' -q
```

The opt-in case starts fresh isolated support/auth/database/MCP/RAG services,
runs the exact CLI commands using the persistent configuration, checks native
selection/generation against saved evidence, and verifies that ticket data did
not change. Session values are excluded from outputs. Local native traces and
CLI transcripts are stored in the system temporary directory; generated
engineering Markdown is saved in the repository evidence directory.
