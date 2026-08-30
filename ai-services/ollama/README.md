# Ollama AI Service

Release 0 uses the locally installed Ollama runtime with the `qwen2.5:0.5b`
model. The model answers Product Catalogue questions in English and does not
modify products, carts, application code, or database records.

Before starting the application, run Ollama on the host computer and confirm
that the model is available:

```bash
ollama pull qwen2.5:0.5b
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

Run Chufeng's Product Catalogue review and choose Database, Endpoints, or
Architecture interactively:

```bash
python ai-services/agentic_loop.py --feature student-Chufeng
```

A review mode can also be selected directly:

```bash
python ai-services/agentic_loop.py --feature student-Chufeng --mode database
python ai-services/agentic_loop.py --feature student-Chufeng --mode endpoints
python ai-services/agentic_loop.py --feature student-Chufeng --mode architecture
```

Endpoint review requires the Docker application to be running. Database and
architecture collection are read-only. Review evidence is saved under
`docs/evidence/agentic/` unless `--no-save` is supplied.
