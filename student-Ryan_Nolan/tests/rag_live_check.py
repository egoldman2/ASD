"""Live check: Flask route -> real RAG server -> Chroma + Ollama.

Needs the Product Database (6001), RAG server (5003) and Ollama running.
Run from the repo root:
    python3 student-Ryan_Nolan/tests/rag_live_check.py
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

os.environ["RAG_ENABLED"] = "true"
os.environ.setdefault("RAG_SERVER_URL", "http://127.0.0.1:5003")

from app import create_app  # noqa: E402

app = create_app()
app.config["TESTING"] = True
client = app.test_client()

CHECKS = [
    ("GET", "/api/inventory/rag/status", None),
    ("POST", "/api/inventory/rag/refresh", {}),
    ("POST", "/api/inventory/rag/retrieve", {"query": "reorder"}),
    ("POST", "/api/inventory/rag/answer", {"question": "Fitness Watch supplier"}),
    ("POST", "/api/inventory/rag/answer",
     {"question": "What is the customer loyalty points policy?"}),
    ("POST", "/api/inventory/rag/answer", {"question": ""}),
]

for method, path, body in CHECKS:
    print("=" * 70)
    print(f"{method} {path}")
    if body is not None:
        print(f"body: {json.dumps(body)}")
    response = client.open(path, method=method, json=body)
    print(f"HTTP {response.status_code}")
    print(json.dumps(response.get_json(), indent=2))