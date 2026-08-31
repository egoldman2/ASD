# Ollama AI Service

Release 0 uses the locally installed Ollama runtime with approved Qwen and
Llama models. The Product Catalogue runtime feature currently uses
`qwen2.5:0.5b`. The shared agentic loop can use either installed model for
read-only software reviews and never modifies application data or code.

Before starting the application, run Ollama on the host computer and confirm
that the model is available:

```bash
ollama pull qwen2.5:0.5b
ollama pull llama3.1:8b
ollama list
```

Then start the application from the project root:

```bash
docker compose up --build -d
```

The backend container accesses the host Ollama service through
`http://host.docker.internal:11434`. No Ollama Docker image or duplicate model
volume is downloaded.

To verify that the Product Catalogue backend is running:

```bash
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

Run a configured feature review and choose Database, Endpoints, or Architecture
interactively:

```bash
python ai-services/agentic_loop.py --feature student-Chufeng
```

A review mode can also be selected directly:

```bash
python ai-services/agentic_loop.py --feature student-Chufeng --mode database
python ai-services/agentic_loop.py --feature student-Chufeng --mode endpoints
python ai-services/agentic_loop.py --feature student-Chufeng --mode architecture
```

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
