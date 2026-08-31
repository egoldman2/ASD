# Ollama AI Service

Release 0 uses approved Qwen and Llama models through Ollama. Product Catalogue
and Customer Support call the shared containerised Ollama service using
`qwen2.5:0.5b`. Customer Support analysis is advisory and cannot directly
modify tickets or send messages. Ethan Ting's Customer Accounts and Loyalty AI
connects to Ollama on the host computer using `llama3.1:8b`. It prepares
read-only insights and customer-change proposals; changes are saved only after
an administrator reviews and confirms them through the protected API.

Before starting the application, make sure the host model used by Customer
Accounts and Loyalty is available:

```bash
ollama pull llama3.1:8b
ollama list
```

Then start the application from the project root:

```bash
docker compose up --build -d
```

The one-shot `ollama-init` service pulls the model into the persistent
`ollama-models` volume and verifies it before dependent backends start. A fresh
volume requires a one-time download; later starts reuse it.

To verify that the Product Catalogue backend is running:

```bash
docker compose ps
docker compose logs ollama-init ollama
docker compose exec ollama ollama show qwen2.5:0.5b
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

CI uses mocked AI clients for inference behavior and starts the support service
boundary without downloading the model on every workflow run. Local and
demonstration evidence must use the real containerised model.
