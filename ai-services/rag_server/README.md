# Shared local RAG service

Run this single service on the host. Application backends remain containerised
and use `http://host.docker.internal:5003`; host checks use port 5003 directly.
The embedded Chroma index stays local and is rebuilt from approved sources.

From the repository root:

```bash
python -m pip install -r ai-services/rag_server/requirements.txt
PYTHONPATH=ai-services python -m rag_server.rag_http_server
```

`RAG_ENABLED=false` disables retrieval and generation. `AI_MODE_ENABLED=false`
also stops model generation; deterministic retrieval does not require Ollama.
The default HTTP bind is `0.0.0.0` for the Docker host bridge. `RAG_HOST`,
`RAG_PORT`, `RAG_CHROMA_PATH`, `RAG_MIN_RELEVANCE_SCORE`, `RAG_DEFAULT_TOP_K`,
`RAG_MAX_TOP_K`, `OLLAMA_URL` and `OLLAMA_MODEL` are configurable. The shared
request timeout defaults to 45 seconds and must be finite, positive and at most
90 seconds.

Registered scopes:

- `chufeng_catalogue`: catalogue data from the existing Product Database API.
- `ethan_goldman_support`: curated Markdown workflow knowledge under
  `knowledge/ethan_goldman/`. This corpus contains implemented application facts;
  it does not index customer tickets or establish business entitlements.

Refresh a scope before querying it, and refresh again after its source changes:

```bash
curl -X POST http://127.0.0.1:5003/refresh -H 'Content-Type: application/json' \
  -d '{"scope":"ethan_goldman_support"}'
curl -X POST http://127.0.0.1:5003/retrieve -H 'Content-Type: application/json' \
  -d '{"scope":"ethan_goldman_support","query":"subject initial message customer ticket characters","top_k":5}'
```

`GET /health` lists registered scopes. `/retrieve` returns the existing envelope
with source citations, bounded chunks, cosine relevance and confidence. A query
with no usable evidence returns `insufficient_context=true` and no results.
This is retrieval output, not a generated answer. The existing `/answer` endpoint
handles generation, whose model/citation acceptance is validated separately.
HTTP bodies must be JSON objects containing only declared fields; queries cap at
1000 characters and `top_k` defaults to five, with a configured maximum of 20.

Curated Markdown loading accepts regular UTF-8 files only, with at most 40 files,
64 KiB per file and 200 chunks per scope. Paragraphs split into 1000-character
pieces with heading attribution. Documents carry scope-prefixed IDs, source
filenames, section labels and content revisions. Refresh removes stale documents
only within its scope; unreadable or invalid sources preserve the previous index.
Other owners can register their approved knowledge with the same adapter rather
than creating another service. Local index/audit files stay ignored by Git.

Run retrieval, isolation, refresh and HTTP checks without model inference:

```bash
python -m pytest ai-services/rag_server/tests -q
```

Grounded generation uses the installed local `qwen2.5:3b` by default; select
another installed model with `OLLAMA_MODEL`. The smaller `qwen2.5:0.5b` failed
support citation acceptance and is not the RAG default. This setting does not
change other features' existing advisory models. No model runs in the containers.

```bash
curl -X POST http://127.0.0.1:5003/answer -H 'Content-Type: application/json' \
  -d '{"scope":"ethan_goldman_support","question":"What subject and initial message lengths are required when creating a customer support ticket?"}'
```

`/answer` retrieves within the selected scope, supplies complete numbered chunks
to the actual model, and validates the returned source numbers and answer size.
The catalogue keeps its product-specific grounding rules; support uses its own
workflow prompt. Every answer paragraph must cite a supplied source. Missing or
invented citations trigger at most one correction using the original evidence;
the service never attaches an inferred source to an uncited model answer.
Generation shares a configured deadline across both attempts, caps the original
context prompt at 16,000 characters, and requests at most 512 output tokens.
HTTP model bodies cap at 64 KiB and displayed answers at 150 words/2000 characters.
Incomplete, malformed, oversized or late replies become explicit failures.

Answers retain actual model identity, retrieved count, used citations and
`model_invoked`/`generation_attempts` metadata. Confidence is a retrieval similarity
label: high at 0.60+, medium at 0.40+, otherwise low for usable context. It is not
a calibrated probability that the answer is correct. Citation validation checks
source identity and presence, not a proof that every statement follows from its
source; staff can inspect the underlying knowledge before acting.

No usable context skips the model and returns the exact insufficient-context
sentence with no claimed citations. A model can also abstain after examining
context. Model outages return `OLLAMA_UNAVAILABLE`, never a successful fabricated
answer. AI-disabled answers stop before retrieval or generation.

The live check records actual retrieved chunks and model requests/responses in
`/tmp/asd-support-rag-generation-live.json` using curated workflow knowledge:

```bash
RUN_LIVE_RAG_AI=1 python -m pytest \
  ai-services/rag_server/tests/test_grounded_generation.py -q
```

Customer Support uses staff-authorised `POST /api/support/admin/rag/answer` with
only `question` and optional integer `top_k`. The backend fixes the support scope;
client-supplied scope, paths or credentials are rejected. It forwards no staff
session or private ticket context to the knowledge service. The HTTP adapter
requires actual model identity for answered results and rejects citations outside
approved support Markdown files. AI/RAG-disabled requests stop before HTTP calls.
Container configuration uses `RAG_SERVER_URL=http://host.docker.internal:5003`
and a 60-second client timeout (finite, positive, maximum 120 seconds).

Staff can read cited files at `/api/support/admin/rag/sources/<filename>` after
normal authentication. Sources are returned as plain text, never rendered HTML.
Backend images bundle the same approved knowledge files; after changing knowledge,
refresh the host index and rebuild the backend to keep the displayed sources current.
Representative questions include the ticket subject/message limits, allowed triage
states, queue count definitions and attention reasons. Refund/warranty entitlements
are absent; unrelated astronomy queries demonstrate insufficient context.

The staff queue and ticket workspace include the Support knowledge assistant.
Answers show used source numbers, passage locations, retrieval confidence and
actual model identity. Citation links open staff-authorised escaped previews at
`/api/support/ui/admin/rag/sources/<filename>`; the plain-text source API remains
available for programmatic review. The form retains the question through loading
and failures so staff can retry, and insufficient context displays no fabricated
answer or source list. Example buttons prefill questions without submitting them.
