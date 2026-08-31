# Ollama AI Service

Release 0 uses the shared containerised Ollama runtime with the
`qwen2.5:0.5b` model. Product Catalogue and Customer Support call the same
internal service. Customer Support analysis is advisory and cannot directly
modify tickets or send messages.

Start the application from the project root:

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

CI uses mocked AI clients for inference behavior and starts the support service
boundary without downloading the model on every workflow run. Local and
demonstration evidence must use the real containerised model.
