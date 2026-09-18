# Shared RAG Service Design

## 1. Purpose

Release 1 will extend the integrated ASD application with one team-level Retrieval-Augmented Generation (RAG) service. The shared service will provide common ingestion, indexing, retrieval, grounded answer generation, citations, audit logging, health checks, and Docker integration. Each team member will remain responsible for connecting their own feature to the shared service and for supplying, testing, and documenting their own RAG data source.

The first complete vertical slice will be the Chufeng Product Catalogue RAG integration.

## 2. Requirements and design decisions

The design satisfies the Release 1 requirements to:

- preserve all Release 0 AI-mode and Ollama capabilities;
- integrate a RAG server into the group application;
- produce grounded AI responses using retrieved context;
- run the integrated local application through the shared Docker Compose configuration;
- update each student's CI workflow to validate their MCP and RAG integration;
- provide RAG architecture, retrieval-flow, response, testing, Docker, and UI evidence.

The following decisions are fixed for the initial implementation:

1. The team will maintain one shared RAG service under `ai-services/rag_server/`.
2. Each feature will have a separately owned source adapter and retrieval scope.
3. The RAG service will access business data through existing database APIs rather than opening student SQLite files directly.
4. The final Release 1 configuration will containerise the RAG service and manage it through `docker-compose.yml`.
5. ChromaDB will be used as the persistent vector store.
6. The existing approved Ollama model will generate answers from retrieved context.
7. The implementation will expose explicit refresh, retrieval, and answer operations.
8. Generated vector data and audit logs will not be committed to Git.
9. RAG failures must not corrupt or roll back successful business CRUD operations.

## 3. Responsibility boundaries

### 3.1 Shared team responsibility

The shared RAG foundation owns:

- the HTTP server and request validation;
- source registration and scope dispatch;
- chunk validation and normalisation;
- embedding generation;
- ChromaDB persistence and filtered Top-K retrieval;
- grounded Ollama prompting;
- citation and confidence response formatting;
- audit logging and health reporting;
- the RAG Docker image and shared Compose service;
- shared protocol, boundary, and pipeline tests;
- the Agentic Loop RAG validation mode.

### 3.2 Individual member responsibility

Each member owns:

- one source adapter for their feature data;
- an explicit allow-list of fields permitted to enter the corpus;
- a unique retrieval scope;
- their backend RAG client and routes/controllers;
- their frontend RAG controls and result presentation;
- feature-specific retrieval and grounded-answer tests;
- their CI validation and individual evidence;
- documentation of known limitations for their feature.

### 3.3 Chufeng responsibility

Chufeng will implement the shared foundation and the first source adapter, `chufeng_catalogue`. The personal integration will cover Product Catalogue data, the AI Product Assistant, citations, confidence display, automated tests, CI, and evidence.

## 4. Architecture

```text
Product Catalogue frontend
        |
        v
Shared Flask backend /api/ai/product-assistant
        |
        v
Chufeng RAG client
        |
        v
Shared RAG server :5003
   |          |             |
   |          |             +--> Ollama :11434
   |          +----------------> ChromaDB persistent volume
   +---------------------------> Product Database API :6001
```

The browser will never access the RAG service directly. Browser requests pass through the existing backend so that validation, error handling, and feature boundaries remain under application control.

The RAG server will use a registry to map a scope to its source adapter. Adding another student feature will require registering another adapter, not copying or replacing the shared pipeline.

## 5. Proposed repository structure

```text
ai-services/
  rag_server/
    __init__.py
    app.py
    config.py
    pipeline.py
    embeddings.py
    vector_store.py
    ollama_client.py
    response.py
    audit.py
    registry.py
    requirements.txt
    Dockerfile
    README.md
    sources/
      __init__.py
      base.py
      chufeng_catalogue.py
    tests/
      __init__.py
      conftest.py
      test_server.py
      test_pipeline.py
      test_retrieval.py
      test_chufeng_source.py

student-Chufeng/
  backend/
    services/rag_client.py
    controllers/ai_controller.py
    routes/ai_routes.py
  frontend/
    index.html
    js/products.js
    css/styles.css
  agentic/
    rag_prompt.txt
    review_config.json
  tests/
    test_rag_client.py
    test_rag_routes.py
    test_rag_frontend.py
```

Very small modules can be combined only when the resulting module retains one clear responsibility. Source adapters, HTTP transport, retrieval, and Ollama generation must remain independently testable.

## 6. Source adapter contract

Every source adapter will expose:

- a unique `scope`;
- a human-readable source name;
- a method that retrieves current data from the owning database API;
- a method that converts records into validated chunks;
- an allow-list of fields permitted in chunk text and metadata.

Every normalised chunk will contain:

```json
{
  "chunk_id": "chufeng-product-12",
  "scope": "chufeng_catalogue",
  "source_id": "product-12",
  "title": "Wireless Keyboard",
  "authority_tier": "tier_1",
  "text": "Product: Wireless Keyboard ...",
  "metadata": {
    "product_id": 12,
    "category": "Electronics",
    "status": "active"
  },
  "indexed_at": "ISO-8601 timestamp"
}
```

The Chufeng adapter will include product name, category, description, selling price, public availability, and stock quantity. It must exclude unit cost, secrets, database paths, authentication data, and unrelated supplier-private information.

## 7. RAG operations

### 7.1 Health

`GET /health` reports service status, vector-store availability, registered scopes, and Ollama configuration without exposing secrets.

### 7.2 Refresh corpus

`POST /api/rag/refresh`

Request:

```json
{
  "scope": "chufeng_catalogue"
}
```

The operation retrieves current records, produces chunks, replaces the selected scope's index, and returns the indexed chunk count. Refreshing one scope must not delete another member's collection data.

### 7.3 Retrieve context

`POST /api/rag/retrieve`

Request:

```json
{
  "query": "keyboard under 100 dollars",
  "scope": "chufeng_catalogue",
  "k": 5
}
```

The result returns ranked chunks with distance or relevance information. `k` will be bounded to prevent unbounded context and resource usage.

### 7.4 Answer question

`POST /api/rag/answer`

Request:

```json
{
  "question": "Which keyboard costs less than 100 AUD?",
  "scope": "chufeng_catalogue",
  "k": 5
}
```

Response:

```json
{
  "answer": "The Wireless Keyboard is available for 79.99 AUD.",
  "citations": [
    {
      "source_id": "product-12",
      "title": "Wireless Keyboard"
    }
  ],
  "confidence_category": "high",
  "retrieval_summary": {
    "scope": "chufeng_catalogue",
    "result_count": 3
  }
}
```

When retrieval produces no adequate evidence, the response will state that the available catalogue contains insufficient evidence. The model must not answer from unsupported prior knowledge.

## 8. Retrieval and generation behaviour

The first implementation will use a deterministic local feature-hashing embedding function with ChromaDB. This avoids adding another large model download and keeps Docker and CI reproducible. Lexical overlap can be used as a bounded fallback when the vector store is unavailable, but the degraded state must be visible in the response and audit log.

The Ollama prompt will:

- contain only the selected question and retrieved chunks;
- identify each context item with a citation token;
- instruct the model to use only supplied evidence;
- prohibit invention of products, prices, stock, or features;
- require an insufficient-evidence response when context is inadequate;
- keep internal product IDs out of customer-facing prose;
- require concise English output for the current Product Catalogue UI.

Confidence will be derived from retrieval evidence, not from an unsupported model self-assessment. The initial categories will be:

- `high`: multiple strong results or one exact, unambiguous product match;
- `medium`: relevant context exists but is incomplete or weakly matched;
- `low`: insufficient evidence, fallback retrieval, or degraded dependencies.

## 9. Product Catalogue integration

The public endpoint `/api/ai/product-assistant` will remain stable. Its internal implementation will change from sending the full catalogue directly to Ollama to calling the shared RAG service.

The frontend will add:

- an explicit RAG grounded-mode switch;
- RAG service availability status;
- a `Refresh catalogue knowledge` demonstration control;
- citation titles below the answer;
- confidence and retrieval-count presentation;
- clear unavailable and insufficient-evidence states.

The RAG switch will default to enabled. When it is disabled, the existing Release 0 full-catalogue AI path will remain available for comparison and the UI will label the result as ungrounded. The UI must never represent that response as a RAG answer.

After a successful product create, update, or delete, the application will request a `chufeng_catalogue` scope refresh. A failed refresh will be logged and presented as a warning; it will not roll back the completed database mutation. The manual refresh operation remains available to restore the index.

## 10. Docker and configuration

The shared `docker-compose.yml` will add a `rag-server` service and a persistent `rag-chroma-data` volume. The service will receive:

- `PRODUCT_DATABASE_API_URL=http://product-database:6001/api/database`;
- `OLLAMA_URL=http://ollama:11434`;
- `OLLAMA_MODEL=qwen2.5:0.5b`;
- `RAG_PORT=5003`;
- a mounted path for ChromaDB persistence.

The shared backend will receive `RAG_SERVER_URL=http://rag-server:5003` and a bounded timeout. Compose health and dependency conditions will ensure that the database and Ollama are ready before RAG-dependent demonstrations run.

The final submission configuration will containerise the RAG service, as required by the project specification. Direct host execution will be documented only as a development and debugging option.

## 11. Error handling and safety

- Invalid scope, query, question, or `k` values return a structured `400` response.
- Unknown scopes return `404` without attempting retrieval.
- Database source failures return `502` or `503` and preserve the previous usable index.
- ChromaDB failures produce a clear degraded response; they must not be silently reported as successful vector retrieval.
- Ollama timeouts return `503`; empty or invalid model output returns `502`.
- Refresh replaces a scope only after new chunks have been prepared successfully.
- All external text is treated as untrusted data, not as instructions.
- Prompt and response limits prevent unbounded requests.
- Audit logs exclude secrets and sensitive source fields.
- RAG operations are read-only with respect to business databases.

Each audit record will include a request ID, scope, operation, duration, result count, status, validation outcome, and timestamp. Full hidden prompts and secrets will not be logged.

## 12. Agentic Loop integration

The shared Agentic Loop will add `rag` as review mode 7. It will collect static and bounded live evidence for:

- required RAG files;
- registered Chufeng scope;
- the refresh, retrieve, and answer operations;
- Docker Compose integration;
- frontend-to-backend-to-RAG routing;
- a successful non-empty corpus refresh;
- retrieval result fields;
- grounded-answer citations and confidence;
- exclusion of configured sensitive fields.

The Chufeng review configuration and `rag_prompt.txt` will define the feature-specific boundaries. Reports will continue to be written under `docs/evidence/agentic/`.

## 13. Testing and CI

### 13.1 Shared tests

Shared tests will cover:

- configuration defaults and validation;
- source registry isolation;
- chunk schema validation;
- replacement of only the requested scope;
- bounded Top-K retrieval;
- grounded prompt construction;
- citation and confidence response schemas;
- dependency failure behaviour;
- sensitive-field exclusion;
- health and HTTP protocol behaviour.

### 13.2 Chufeng tests

Chufeng tests will cover:

- transformation of Product Database API records into safe chunks;
- retrieval of a known product query;
- insufficient-evidence behaviour;
- backend RAG client request and timeout handling;
- preservation of the existing Product Assistant endpoint;
- frontend RAG switch, refresh control, citations, and status text;
- absence of `unit_cost` and internal IDs in customer-facing output.

### 13.3 CI

The Chufeng GitHub Actions workflow will run the relevant Python tests and build the updated Docker images. Live Ollama generation will be replaced by deterministic test doubles in CI; local integration evidence will prove the real Ollama workflow.

## 14. Evidence and reporting

The implementation will produce evidence for:

- RAG server health;
- a successful Chufeng corpus refresh with a non-zero chunk count;
- Top-K retrieval for representative catalogue queries;
- a grounded answer with citations and confidence;
- an insufficient-evidence query;
- local Docker Compose execution;
- frontend RAG-enabled screenshots;
- successful Chufeng CI execution;
- Agentic Loop RAG validation;
- retrieval metrics and known limitations.

The technical report will include the shared RAG architecture, retrieval flow, grounded-answer flow, Chufeng implementation summary, request/response examples, testing evidence, and contribution boundaries.

## 15. Delivery sequence

1. Create the shared RAG server configuration, health endpoint, and response schemas.
2. Define the source adapter contract and registry.
3. Implement the Chufeng Product Catalogue source adapter.
4. Implement chunking, embeddings, ChromaDB persistence, and filtered retrieval.
5. Implement refresh, retrieve, and answer endpoints.
6. Add grounded Ollama generation, citations, confidence, and auditing.
7. Replace the Product Assistant's full-catalogue prompt path with the backend RAG client.
8. Add frontend controls and grounded-answer presentation.
9. Add Docker Compose, tests, CI, documentation, and Agentic Loop RAG mode.
10. Run local integration validation and capture Release 1 evidence.

## 16. Non-goals for the first RAG increment

- cloud-hosted RAG;
- a Release 2 multi-agent server;
- automatic web crawling;
- commercial embedding or LLM APIs;
- direct model writes to product or cart data;
- cross-feature retrieval before another member has provided and tested their adapter;
- automatic trust of documents merely because they were indexed.

## 17. Acceptance criteria

The first increment is complete when:

1. Docker Compose starts a healthy shared RAG service.
2. Refreshing `chufeng_catalogue` creates a non-zero isolated corpus.
3. A representative product question retrieves relevant chunks from ChromaDB.
4. The Product Assistant returns an Ollama-generated answer grounded in those chunks.
5. The response contains citations, confidence, and a retrieval summary.
6. An unsupported question produces an insufficient-evidence response.
7. Sensitive fields are absent from chunks, prompts, logs, and customer-visible answers.
8. Product data changes can be reflected by refreshing the Chufeng scope.
9. Shared and Chufeng-specific tests pass.
10. The Chufeng CI workflow validates MCP and RAG integration.
11. Agentic Loop RAG mode produces a saved evidence report.
12. The required report diagrams, request/response evidence, Docker evidence, CI evidence, and screenshots can be produced from the implementation.
