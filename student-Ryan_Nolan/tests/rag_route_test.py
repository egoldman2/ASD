import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_status_when_disabled_is_not_fatal(client, monkeypatch):
    monkeypatch.setenv("RAG_ENABLED", "false")
    response = client.get("/api/inventory/rag/status")
    body = response.get_json()
    assert response.status_code == 200
    assert body["enabled"] is False
    assert body["error"]["code"] == "RAG_DISABLED"


def test_answer_when_disabled_returns_rag_disabled(client, monkeypatch):
    monkeypatch.setenv("RAG_ENABLED", "false")
    monkeypatch.setenv("RAG_SERVER_URL", "http://127.0.0.1:5003")
    response = client.post(
        "/api/inventory/rag/answer",
        json={"question": "low stock"},
    )
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "RAG_DISABLED"


def test_header_can_switch_rag_off_per_request(client):
    response = client.post(
        "/api/inventory/rag/answer",
        headers={"X-RAG-Mode": "off"},
        json={"question": "low stock"},
    )
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "RAG_DISABLED"


def test_missing_question_is_invalid(client):
    response = client.post("/api/inventory/rag/answer", json={})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_ARGUMENT"


def test_top_k_out_of_range_is_invalid(client):
    response = client.post(
        "/api/inventory/rag/answer",
        json={"question": "low stock", "top_k": 500},
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_ARGUMENT"