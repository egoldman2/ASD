# Ollama AI Service

Release 1 uses the locally installed, non-containerised Ollama runtime with
approved Qwen and Llama models. Backend containers access Ollama on the host
computer through `http://host.docker.internal:11434`. Product Catalogue,
Customer Support, and Inventory use `qwen2.5:0.5b`; Customer Accounts and
Loyalty uses `llama3.1:8b`. AI assistance remains advisory and cannot directly
modify application data.

Before starting Docker Compose, start Ollama on the host computer and make sure
the required models are available:

```bash
ollama pull qwen2.5:0.5b
ollama pull llama3.1:8b
ollama list
```

Then start the application from the project root:

```bash
docker compose up --build -d
```

Ollama, MCP, RAG, and the shared agentic loop remain outside Docker Compose.
Compose starts only the containerised student frontend, backend/API, and
database microservices. It does not download models.

To verify the host runtime and the Product Catalogue backend:

```bash
curl http://localhost:11434/api/tags
docker compose ps
docker compose logs shared-backend
```

## Shared Agentic Review Loop

The shared review loop loads a feature-specific prompt, collects read-only
evidence, asks Qwen for an initial review, reviews that response, and adapts it
when required. Student prompts and evidence scopes remain in each student's
feature directory.

List the configured student features:

```bash
python ai-services/agentic_loop.py --list-features
```

Run a configured feature review and choose Database, Endpoints, Architecture,
Implementation, or DevOps interactively:

```bash
python ai-services/agentic_loop.py --feature student-Chufeng
```

A review mode can also be selected directly:

```bash
python ai-services/agentic_loop.py --feature student-Chufeng --mode database
python ai-services/agentic_loop.py --feature student-Chufeng --mode endpoints
python ai-services/agentic_loop.py --feature student-Chufeng --mode architecture
```

Chufeng's Release 1 integration also provides MCP and RAG validation modes:

```bash
python ai-services/agentic_loop.py --feature student-Chufeng --mode mcp
python ai-services/agentic_loop.py --feature student-Chufeng --mode rag
```

The MCP mode requires the host MCP server and Product Database API. The RAG
mode requires the Product Database API, host RAG server, local Ollama, and the
configured `qwen2.5:0.5b` model. Both modes retain static evidence if their
runtime integration is disabled, as it is during CI.

## Ethan Goldman - Customer Support

Ethan Goldman's configuration covers the four assessed review areas: database,
implementation, microservices architecture, and DevOps. Prepare the ignored,
local review database from the real schema and seed data:

```bash
python "student-Ethan Goldman/database_service/init_db.py" \
  --database-path "student-Ethan Goldman/database_service/support_tickets.db" \
  --reset
```

Run and retain all four reviews:

```bash
python ai-services/agentic_loop.py \
  --feature "student-Ethan Goldman" --mode database
python ai-services/agentic_loop.py \
  --feature "student-Ethan Goldman" --mode implementation
python ai-services/agentic_loop.py \
  --feature "student-Ethan Goldman" --mode architecture
python ai-services/agentic_loop.py \
  --feature "student-Ethan Goldman" --mode devops
```

The source collectors are bounded, redacted, and read-only. The database
collector opens SQLite in read-only mode. `EthanGoldman.yml` is the accepted
project name for Ethan's assigned workflow; the DevOps review assesses its
content and explicitly does not treat that filename as a defect.

## Ethan Ting - Customer Accounts and Loyalty

Ethan's review configuration covers the customer/loyalty SQLite schema,
signed-out endpoint protection, and the frontend/backend/database architecture.
The Ethan backend also exposes the administrator-only, read-only Customer
Insight endpoint at `POST /api/admin/ai/customer-insight`. It uses
`llama3.1:8b`, sends only allow-listed customer and loyalty fields, validates
model citations and rankings, and cannot call any customer or loyalty mutation
route. The prompt asset is stored at
`student-Ethan Ting/agentic/customer_insight_prompt.txt`.

Start the application and open `http://localhost:8003/admin.html`, then sign in
with the seeded administrator account to demonstrate the AI from the frontend.
The response includes visible Plan -> Act -> Observe -> Adapt metadata, while
all account edits and point adjustments remain separate manual admin actions.

Prepare the ignored local review database from the seeded schema after building
the database image:

```bash
docker compose build ethan-database
docker run --rm \
  -v "$PWD:/project" \
  -w /project \
  -e "DATABASE_PATH=/project/student-Ethan Ting/database/users.db" \
  asd-ethan-database \
  python "student-Ethan Ting/database/init_db.py"
```

Run the three Ethan reviews:

```bash
python ai-services/agentic_loop.py \
  --feature "student-Ethan Ting" --mode database

OLLAMA_MODEL="llama3.1:8b" python ai-services/agentic_loop.py \
  --feature "student-Ethan Ting" --mode endpoints

OLLAMA_MODEL="llama3.1:8b" python ai-services/agentic_loop.py \
  --feature "student-Ethan Ting" --mode architecture
```

The report deliberately keeps the initial model review, reviewer feedback, and
final adapted review. This makes the Plan -> Act -> Observe -> Adapt process
visible. When a model contradicts collected evidence, deterministic grounding
checks replace the final answer with a verified summary. Password hashes and
other secret-like sample fields are redacted before model input and report
generation.

Endpoint review requires the Docker application to be running. Database and
architecture collection are read-only. Review evidence is saved under
`docs/evidence/agentic/` unless `--no-save` is supplied.

CI uses mocked AI clients for inference behavior and does not start or download
Ollama. Local and demonstration evidence must use the real host runtime.
