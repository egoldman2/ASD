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
