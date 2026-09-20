
"""Shared deterministic fixtures for the local RAG service tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys

import pytest


AI_SERVICES_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(AI_SERVICES_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICES_ROOT))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def rag_settings(tmp_path):
    """Return complete settings whose writable state stays under tmp_path."""

    from rag_server.config import RAGSettings

    return RAGSettings(
        enabled=True,
        host="0.0.0.0",
        port=5003,
        product_database_api_url="http://products.test/api/database/products",
        ollama_url="http://ollama.test",
        ollama_model="qwen2.5:0.5b",
        chroma_path=tmp_path / "chroma",
        collection_name=f"rag_test_{tmp_path.name.replace('-', '_')}",
        audit_path=tmp_path / "rag-audit.jsonl",
        request_timeout_seconds=1.0,
        default_top_k=5,
        max_top_k=20,
        min_relevance_score=0.0,
        embedding_dimensions=64,
        log_level="WARNING",
    )


@pytest.fixture
def settings_factory(rag_settings):
    """Make small immutable settings variants without repeating every field."""

    def factory(**changes):
        return replace(rag_settings, **changes)

    return factory
