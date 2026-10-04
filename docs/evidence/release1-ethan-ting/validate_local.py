"""Read-only integration evidence. Run from the repo with Python 3.11.

Uses existing local demo admin credentials unless supplied through environment.
Never prints credentials, cookies, customer names or email addresses.
Refresh changes the approved RAG index, not application records.
"""
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[3]
session = requests.Session()
base = os.getenv("ETHAN_VALIDATION_API", "http://127.0.0.1:6002")
customer_id = int(os.getenv("ETHAN_VALIDATION_CUSTOMER_ID", "187"))
results = {"checked_at": datetime.now(ZoneInfo("Australia/Sydney")).isoformat()}


def call(method, path, body=None, expected=200):
    response = session.request(method, base + path, json=body, timeout=90)
    assert response.status_code == expected, f"{method} {path}: {response.status_code} {response.text[:300]}"
    return response.json()


login = call("POST", "/api/login", {
    "email": os.getenv("ETHAN_VALIDATION_EMAIL", "admin@asd.local"),
    "password": os.getenv("ETHAN_VALIDATION_PASSWORD", "AdminPass!2026"),
})
results["admin_login_status"] = 200
before = call("GET", f"/api/admin/loyalty/{customer_id}/history")
results["history_before"] = before
results["mcp_progress"] = call("POST", "/api/admin/mcp/loyalty-tier", {"user_id": customer_id})
results["mcp_history"] = call("POST", "/api/admin/mcp/loyalty-history", {"user_id": customer_id, "limit": 5})
refresh = call("POST", "/api/admin/rag/refresh", {})
results["rag_refresh"] = refresh
results["rag_answer"] = call("POST", "/api/admin/rag/answer", {"question": "What total points balance is the Gold threshold? Do not assume a current customer balance."})
results["rag_insufficient"] = call("POST", "/api/admin/rag/answer", {"question": "quasar orbital spectroscopy wavelengths"})
assert results["mcp_progress"]["result"]["points_balance"] == 720
assert results["mcp_progress"]["result"]["tier"] == "Silver"
assert results["mcp_progress"]["result"]["points_to_next_tier"] == 280
assert results["rag_answer"]["citations"] and not results["rag_answer"]["insufficient_context"]
assert "1,000" in results["rag_answer"]["answer"] or "1000" in results["rag_answer"]["answer"]
assert results["rag_answer"]["confidence"] in {"low", "medium", "high"}
assert results["rag_insufficient"]["insufficient_context"] and not results["rag_insufficient"]["citations"]
after = call("GET", f"/api/admin/loyalty/{customer_id}/history")
assert before == after, "Read-only validation changed transaction history"
results["history_unchanged"] = True
compose = json.loads(subprocess.check_output(["docker", "compose", "config", "--format", "json"], cwd=ROOT))
env = compose["services"]["ethan-backend"]["environment"]
results["docker_host_configuration"] = {
    key: env[key] for key in ("DATABASE_API_URL", "OLLAMA_URL", "OLLAMA_MODEL", "MCP_SERVER_URL", "RAG_SERVER_URL", "MCP_ENABLED", "RAG_ENABLED")
}
results["host_services_not_containerised"] = not any(
    name in compose["services"] for name in ("ollama", "ollama-init", "mcp", "mcp-server", "rag", "rag-server", "agentic-loop")
)
# Retain only validation fields. Application envelopes can include demo names;
# discard those recursively so the evidence stays free of customer identity.
def redact(value):
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items() if k not in {"email", "full_name", "admin_name", "created_by_admin_name", "customer_name", "password", "token", "session"}}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value

results["mcp_history"].pop("answer", None)
results = redact(results)
print(json.dumps(results, indent=2))
out = Path(__file__).parent / "final-local-validation.json"
out.write_text(json.dumps(results, indent=2) + "\n")
print("PASS: protected backend MCP/RAG calls, unchanged history and Docker-to-host configuration")
