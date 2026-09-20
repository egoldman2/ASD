
"""Tests for Chufeng's backend-side RAG HTTP client."""

from importlib import import_module

import requests
import pytest


rag_client_module = import_module(
    "student-Chufeng.backend.services.rag_client"
)
CHUFENG_RAG_SCOPE = rag_client_module.CHUFENG_RAG_SCOPE
ChufengRAGClient = rag_client_module.ChufengRAGClient
RAGClientError = rag_client_module.RAGClientError
RAGClientSettings = rag_client_module.RAGClientSettings
RAGDisabledError = rag_client_module.RAGDisabledError


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


def settings(enabled=True):
    return RAGClientSettings(
        enabled=enabled,
        server_url="http://127.0.0.1:5003",
        timeout_seconds=2.0,
    )


def envelope(operation, data=None):
    return {
        "success": True,
        "operation": operation,
        "data": data or {},
        "citations": [],
        "confidence": None,
        "insufficient_context": False,
        "error": None,
    }


def test_settings_load_environment(monkeypatch):
    monkeypatch.setenv("RAG_ENABLED", "yes")
    monkeypatch.setenv("RAG_SERVER_URL", "http://localhost:9003/")
    monkeypatch.setenv("RAG_CLIENT_TIMEOUT_SECONDS", "45")

    result = RAGClientSettings.from_environment()

    assert result.enabled is True
    assert result.server_url == "http://localhost:9003"
    assert result.timeout_seconds == 45.0


def test_disabled_client_rejects_request_before_connecting():
    client = ChufengRAGClient(
        settings(enabled=False),
        http_request=lambda **_: pytest.fail("must not connect"),
    )

    with pytest.raises(RAGDisabledError):
        client.health()


def test_client_calls_all_rag_endpoints_with_fixed_chufeng_scope():
    calls = []

    def request(**arguments):
        calls.append(arguments)
        path = arguments["url"].rsplit("/", 1)[-1]
        if path == "health":
            return FakeResponse({"status": "healthy", "enabled": True})
        operations = {
            "refresh": "refresh_corpus",
            "retrieve": "retrieve_context",
            "answer": "answer_question",
        }
        return FakeResponse(envelope(operations[path]))

    client = ChufengRAGClient(settings(), http_request=request)

    client.health()
    client.refresh_corpus()
    client.retrieve_context("keyboard", 3)
    client.answer_question("What is available?", 4)

    assert [call["url"] for call in calls] == [
        "http://127.0.0.1:5003/health",
        "http://127.0.0.1:5003/refresh",
        "http://127.0.0.1:5003/retrieve",
        "http://127.0.0.1:5003/answer",
    ]
    assert all(call["timeout"] == 2.0 for call in calls)
    assert calls[1]["json"]["scope"] == CHUFENG_RAG_SCOPE
    assert calls[2]["json"] == {
        "scope": CHUFENG_RAG_SCOPE,
        "query": "keyboard",
        "top_k": 3,
    }
    assert calls[3]["json"]["scope"] == CHUFENG_RAG_SCOPE


def test_connection_failure_is_converted_to_safe_error():
    def unavailable(**_):
        raise requests.ConnectionError("private socket information")

    client = ChufengRAGClient(settings(), http_request=unavailable)

    with pytest.raises(RAGClientError) as failure:
        client.answer_question("question", 5)

    assert failure.value.code == "RAG_UNAVAILABLE"
    assert failure.value.status_code == 503
    assert "private socket information" not in str(failure.value)


def test_invalid_structured_response_is_rejected():
    client = ChufengRAGClient(
        settings(),
        http_request=lambda **_: FakeResponse({"unexpected": True}),
    )

    with pytest.raises(RAGClientError) as failure:
        client.retrieve_context("keyboard", 5)

    assert failure.value.code == "RAG_INVALID_RESPONSE"
