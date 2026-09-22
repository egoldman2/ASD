# RAG Agentic Validation Mode Design

## Objective

Extend the shared `ai-services/agentic_loop.py` review loop with a `rag` mode
that mirrors the existing MCP validation structure. The mode must collect
bounded static and live evidence for Chufeng's shared RAG integration, review
that evidence with the local Ollama model, deterministically reject unsupported
claims, and save an auditable Plan–Act–Observe–Adapt Markdown report.

This change validates the existing RAG implementation. It does not change the
catalogue, shopping cart, RAG HTTP API, frontend workflow, ChromaDB schema, or
Docker deployment model.

## Architecture

The RAG mode follows the same structure as the MCP mode:

1. `review_config.json` declares the prompt, bounded evidence files, runtime
   endpoint, probe inputs, and static source checks.
2. `collect_rag_evidence()` reuses the generic file collector and adds
   RAG-specific deterministic checks.
3. Runtime collection respects `RAG_ENABLED`. When enabled, a bounded probe
   uses Chufeng's existing backend RAG client to contact the host-side RAG
   server.
4. The shared Ollama review loop generates an initial review, evaluates it
   against deterministic evidence, adapts it when necessary, and saves the
   complete evidence report.

The host-side RAG server remains outside Docker Compose. The runtime probe may
refresh the local vector index and audit log, but it is read-only with respect
to catalogue application data.

## Configuration

`student-Chufeng/agentic/review_config.json` will add:

- `rag` in `mode_prompt_files`;
- `rag_files` covering the RAG server, pipeline, catalogue source, Chufeng RAG
  client/controller/routes/frontend, Compose configuration, workflow, and
  focused tests;
- `rag_server_url` with the host default `http://127.0.0.1:5003`;
- `rag_rules` containing the required scope, required operations, fixed probe
  query, and bounded Top-K value;
- `source_checks.rag` for API-based source ingestion, ChromaDB retrieval,
  grounded answer controls, insufficient-context handling, backend-only
  frontend access, host-side Docker wiring, and CI runtime disablement.

`student-Chufeng/agentic/rag_prompt.txt` will instruct the model to separate
static evidence from live evidence and to assess only configured RAG
boundaries. It must not infer successful runtime, GitHub Actions, deployment,
retrieval quality, citations, or model behaviour when those facts were not
collected.

## Live Runtime Probe

When `RAG_ENABLED` is true, the collector will load the existing Chufeng RAG
client and perform this bounded sequence:

1. call the health endpoint and verify the expected service status, scope,
   operations, and configured Ollama model;
2. refresh the `chufeng_catalogue` corpus from the Product Database API;
3. retrieve a bounded Top-K result set for a fixed catalogue question;
4. request one grounded answer for that same question;
5. retain compact summaries of document counts, retrieved source identifiers,
   confidence, citations, model, and insufficient-context state.

The collector will not retain full catalogue payloads in the review summary.
Runtime exceptions will be captured as bounded error text rather than aborting
the static review.

When `RAG_ENABLED` is false, the collector will record that live validation was
skipped and will continue with static evidence. This is the expected CI mode.

## Deterministic Review Controls

RAG-specific grounding checks will reject or flag a model review when it:

- claims successful live validation although the runtime collector did not
  connect;
- treats static source markers as proof of a live refresh, retrieval, or answer;
- omits the configured RAG scope and required operations;
- claims a grounded live answer when retrieval sources or answer citations were
  not collected;
- ignores a failed or incomplete runtime probe;
- cites too few configured files to support a system-level RAG conclusion.

The deterministic fallback will report static checks and runtime observations
separately. When live validation is unavailable it will state that limitation
and recommend starting the Product Database API, Ollama, and host RAG server
before rerunning the mode.

## Testing

Focused tests in `student-Chufeng/tests/test_agentic_loop.py` will cover:

- loading the RAG prompt and rules;
- static evidence when live RAG is disabled;
- successful injected live evidence without requiring network services;
- rejection of invented live RAG success;
- separation of static and runtime facts in the fallback review;
- acceptance of `--mode rag` by the command-line parser.

The existing Chufeng, MCP, and RAG test suites will then be run together to
check for regressions. Live Ollama and RAG execution remains a local evidence
step rather than a CI dependency.

## Success Criteria

The implementation is complete when:

- `python ai-services/agentic_loop.py --feature student-Chufeng --mode rag`
  is accepted;
- the mode produces static evidence while `RAG_ENABLED=false`;
- with the local services running, it records a successful corpus refresh,
  Top-K retrieval, and grounded answer with sources and confidence;
- unsupported model claims are corrected by deterministic checks;
- a timestamped RAG Agentic Review Evidence report is saved under
  `docs/evidence/agentic/`;
- focused and combined automated tests pass.
