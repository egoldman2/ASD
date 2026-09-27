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
