"""Essential configuration and response-contract tests for shared RAG."""

import pytest

from rag_server.config import ConfigurationError, RAGSettings
from rag_server.response import (
    ConfidenceCategory,
    RAGErrorCode,
    error_response,
    insufficient_context_response,
    success_response,
)


def test_settings_read_and_normalise_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("RAG_HOST", "0.0.0.0")
    monkeypatch.setenv("RAG_PORT", "9124")
    monkeypatch.setenv(
        "PRODUCT_DATABASE_API_URL",
        "http://localhost:7001/api/database/products/",
    )
    monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434/")
    monkeypatch.setenv("RAG_CHROMA_PATH", str(tmp_path / "vectors"))
    monkeypatch.setenv("RAG_AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("RAG_DEFAULT_TOP_K", "4")
    monkeypatch.setenv("RAG_MAX_TOP_K", "12")
    monkeypatch.setenv("RAG_LOG_LEVEL", "debug")

    settings = RAGSettings.from_environment()

    assert settings.host == "0.0.0.0"
    assert settings.port == 9124
    assert settings.endpoint_url == "http://127.0.0.1:9124"
    assert settings.product_database_api_url.endswith("/products")
    assert settings.ollama_url == "http://localhost:11434"
    assert settings.chroma_path == (tmp_path / "vectors").resolve()
    assert settings.default_top_k == 4
    assert settings.max_top_k == 12
    assert settings.log_level == "DEBUG"


def test_invalid_top_k_configuration_fails_early(monkeypatch):
    monkeypatch.setenv("RAG_DEFAULT_TOP_K", "10")
    monkeypatch.setenv("RAG_MAX_TOP_K", "5")

    with pytest.raises(ConfigurationError, match="must not be greater"):
        RAGSettings.from_environment()


def test_response_envelopes_keep_a_stable_shape():
    success = success_response(
        "retrieve_context",
        {"results": []},
        citations=[{"source_id": "product:1"}],
        confidence=ConfidenceCategory.HIGH,
    )
    insufficient = insufficient_context_response(
        "answer_question",
        "Not enough evidence.",
    )
    failure = error_response(
        "answer_question",
        RAGErrorCode.OLLAMA_UNAVAILABLE,
        "Ollama is unavailable.",
    )

    expected_keys = {
        "success",
        "operation",
        "data",
        "citations",
        "confidence",
        "insufficient_context",
        "error",
    }
    assert set(success) == expected_keys
    assert success["confidence"] == "high"
    assert insufficient["insufficient_context"] is True
    assert insufficient["confidence"] == "insufficient"
    assert failure["error"]["code"] == "OLLAMA_UNAVAILABLE"
