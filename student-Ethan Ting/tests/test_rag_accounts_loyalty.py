"""Admin boundary tests for the accounts and loyalty RAG guide."""

import importlib.util
from pathlib import Path

import pytest


APP_PATH = Path(__file__).resolve().parents[1] / "backend" / "app.py"
SCOPE = "ethan_ting_accounts_loyalty"


@pytest.fixture
def backend(monkeypatch):
    spec = importlib.util.spec_from_file_location("ethan_rag_app", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.config.update(TESTING=True, SECRET_KEY="rag-test-key")
    monkeypatch.setenv("AI_MODE_ENABLED", "true")
    monkeypatch.setenv("RAG_ENABLED", "true")

    def fake_database(path, method="GET", payload=None):
        if path == "/internal/users/1":
            return {"user": {"id": 1, "email": "admin@asd.local", "full_name": "Admin",
                             "role": "admin", "is_active": 1}}
        raise AssertionError(f"Unexpected database call: {path}")

    monkeypatch.setattr(module, "database_request", fake_database)
    return module


def sign_in(client, role="admin"):
    with client.session_transaction() as current:
        current["user"] = {"id": 1, "email": "admin@asd.local", "full_name": "Admin", "role": role}


def answer_payload(question, *, insufficient=False):
    return {
        "success": True, "operation": "answer_question",
        "data": {"scope": SCOPE, "question": question,
                 "answer": ("Insufficient context to answer this question." if insufficient
                            else "Gold begins at 1,000 points. [1]"),
                 "model": None if insufficient else "qwen2.5:3b"},
        "citations": [] if insufficient else [{"scope": SCOPE,
            "source_id": f"{SCOPE}/accounts_and_loyalty.md", "rank": 1,
            "label": "Customer accounts and loyalty: implemented guide: Loyalty tiers"}],
        "confidence": "insufficient" if insufficient else "high",
        "insufficient_context": insufficient,
    }


@pytest.mark.parametrize("route,body", [
    ("/api/admin/rag/answer", {"question": "How do tiers work?"}),
    ("/api/admin/rag/refresh", None),
])
def test_routes_require_admin(backend, route, body):
    with backend.app.test_client() as client:
        anonymous = client.post(route, json=body)
        sign_in(client, "customer")
        customer = client.post(route, json=body)
    assert anonymous.status_code == 401
    assert customer.status_code == 403


def test_disabled_flags_stop_before_rag_call(backend, monkeypatch):
    monkeypatch.setattr(backend, "rag_request", lambda *args: pytest.fail("RAG called"))
    with backend.app.test_client() as client:
        sign_in(client)
        monkeypatch.setenv("RAG_ENABLED", "false")
        assert client.post("/api/admin/rag/answer", json={"question": "tiers"}).status_code == 503
        assert client.post("/api/admin/rag/refresh").status_code == 503
        monkeypatch.setenv("RAG_ENABLED", "true")
        monkeypatch.setenv("AI_MODE_ENABLED", "false")
        assert client.post("/api/admin/rag/answer", json={"question": "tiers"}).status_code == 503


@pytest.mark.parametrize("body", [{}, {"question": ""}, {"question": "x" * 401},
                                  {"question": "customer@example.test"},
                                  {"question": "tiers", "scope": "other"}])
def test_question_validation(backend, monkeypatch, body):
    monkeypatch.setattr(backend, "rag_request", lambda *args: pytest.fail("RAG called"))
    with backend.app.test_client() as client:
        sign_in(client)
        assert client.post("/api/admin/rag/answer", json=body).status_code == 400


def test_cited_answer_uses_fixed_scope_and_no_database_records(backend, monkeypatch):
    calls = []
    question = "How many points for Gold?"

    def fake_rag(path, payload):
        calls.append((path, payload))
        return answer_payload(question)

    monkeypatch.setattr(backend, "rag_request", fake_rag)
    with backend.app.test_client() as client:
        sign_in(client)
        response = client.post("/api/admin/rag/answer", json={"question": question})
    assert response.status_code == 200
    assert calls == [("/answer", {"question": question, "top_k": 5})]
    assert response.json["confidence"] == "high"
    assert response.json["citations"][0]["rank"] == 1


def test_insufficient_context_has_no_invented_sources(backend, monkeypatch):
    monkeypatch.setattr(backend, "rag_request", lambda *args: answer_payload("Unknown?", insufficient=True))
    with backend.app.test_client() as client:
        sign_in(client)
        response = client.post("/api/admin/rag/answer", json={"question": "Unknown?"})
    assert response.status_code == 200
    assert response.json["insufficient_context"] is True
    assert response.json["citations"] == []


def test_cross_scope_citation_rejected(backend, monkeypatch):
    payload = answer_payload("How many points for Gold?")
    payload["citations"][0]["scope"] = "ethan_goldman_support"
    monkeypatch.setattr(backend, "rag_request", lambda *args: payload)
    with backend.app.test_client() as client:
        sign_in(client)
        response = client.post("/api/admin/rag/answer", json={"question": "How many points for Gold?"})
    assert response.status_code == 502


@pytest.mark.parametrize("source_id,rank,answer", [
    (f"{SCOPE}/different_guide.md", 1, "Gold begins at 1,000 points. [1]"),
    (f"{SCOPE}/accounts_and_loyalty.md", 2, "Gold begins at 1,000 points. [1]"),
    (f"{SCOPE}/accounts_and_loyalty.md", 1, "Gold begins at 1,000 points. [2]"),
])
def test_invented_or_mismatched_citations_rejected(
    backend, monkeypatch, source_id, rank, answer
):
    question = "How many points for Gold?"
    payload = answer_payload(question)
    payload["citations"][0].update(source_id=source_id, rank=rank)
    payload["data"]["answer"] = answer
    monkeypatch.setattr(backend, "rag_request", lambda *args: payload)
    with backend.app.test_client() as client:
        sign_in(client)
        response = client.post("/api/admin/rag/answer", json={"question": question})
    assert response.status_code == 502


def test_refresh_and_unavailable_service(backend, monkeypatch):
    monkeypatch.setattr(backend, "rag_request", lambda *args: {
        "success": True, "operation": "refresh_corpus",
        "data": {"scope": SCOPE, "document_count": 5},
    })
    with backend.app.test_client() as client:
        sign_in(client)
        response = client.post("/api/admin/rag/refresh")
        assert response.status_code == 200
        assert response.json["document_count"] == 5
        monkeypatch.setattr(backend, "rag_request", lambda *args: (_ for _ in ()).throw(OSError()))
        assert client.post("/api/admin/rag/refresh").status_code == 503
        assert client.post("/api/admin/rag/answer", json={"question": "tiers"}).status_code == 503
