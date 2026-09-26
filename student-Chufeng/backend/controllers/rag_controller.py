
"""HTTP-facing orchestration for Chufeng's personal RAG integration."""

from __future__ import annotations

import logging
from typing import Any, Callable

from ..services.rag_client import (
    CHUFENG_RAG_SCOPE,
    MAX_TOP_K,
    ChufengRAGClient,
    RAGClientError,
    RAGDisabledError,
)


LOGGER = logging.getLogger(__name__)
DEFAULT_TOP_K = 5
MAX_QUESTION_LENGTH = 1000

RAG_ERROR_HTTP_STATUS = {
    "INVALID_ARGUMENT": 400,
    "SCOPE_NOT_FOUND": 404,
    "SOURCE_DATA_INVALID": 502,
    "UPSTREAM_ERROR": 502,
    "SOURCE_UNAVAILABLE": 503,
    "INDEX_UNAVAILABLE": 503,
    "OLLAMA_UNAVAILABLE": 503,
    "RAG_DISABLED": 503,
    "INTERNAL_ERROR": 500,
}


def _create_client() -> ChufengRAGClient:
    return ChufengRAGClient()


def _safe_internal_error() -> tuple[dict[str, Any], int]:
    return {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "The RAG request could not be completed.",
        }
    }, 500


def _validated_request(
    data: Any,
    text_field: str,
) -> tuple[tuple[str, int] | None, tuple[dict[str, Any], int] | None]:
    if not isinstance(data, dict):
        return None, (
            {
                "error": {
                    "code": "INVALID_ARGUMENT",
                    "message": "A JSON request body is required.",
                }
            },
            400,
        )

    text = data.get(text_field)
    if not isinstance(text, str) or not text.strip():
        return None, (
            {
                "error": {
                    "code": "INVALID_ARGUMENT",
                    "message": f"{text_field} must be a non-empty string.",
                }
            },
            400,
        )
    cleaned_text = text.strip()
    if len(cleaned_text) > MAX_QUESTION_LENGTH:
        return None, (
            {
                "error": {
                    "code": "INVALID_ARGUMENT",
                    "message": (
                        f"{text_field} must not exceed "
                        f"{MAX_QUESTION_LENGTH} characters."
                    ),
                }
            },
            400,
        )

    top_k = data.get("top_k", DEFAULT_TOP_K)
    if (
        isinstance(top_k, bool)
        or not isinstance(top_k, int)
        or not 1 <= top_k <= MAX_TOP_K
    ):
        return None, (
            {
                "error": {
                    "code": "INVALID_ARGUMENT",
                    "message": f"top_k must be an integer between 1 and {MAX_TOP_K}.",
                }
            },
            400,
        )
    return (cleaned_text, top_k), None


def _execute(
    operation: Callable[[ChufengRAGClient], dict[str, Any]],
) -> tuple[dict[str, Any], int]:
    try:
        payload = operation(_create_client())
    except RAGClientError as exc:
        return exc.to_dict(), exc.status_code
    except Exception:
        LOGGER.exception("Unexpected Chufeng RAG controller failure")
        return _safe_internal_error()

    if payload.get("success") is False:
        error = payload.get("error")
        code = error.get("code") if isinstance(error, dict) else None
        return payload, RAG_ERROR_HTTP_STATUS.get(code, 502)
    return payload, 200


def get_rag_status() -> tuple[dict[str, Any], int]:
    """Return a UI-friendly health snapshot without making failure fatal."""

    try:
        health = _create_client().health()
    except RAGDisabledError as exc:
        return {
            "success": True,
            "enabled": False,
            "available": False,
            "scope": CHUFENG_RAG_SCOPE,
            "error": {"code": exc.code, "message": exc.message},
        }, 200
    except RAGClientError as exc:
        return {
            "success": True,
            "enabled": True,
            "available": False,
            "scope": CHUFENG_RAG_SCOPE,
            "error": {"code": exc.code, "message": exc.message},
        }, 200
    except Exception:
        LOGGER.exception("Unexpected failure while checking RAG status")
        return {
            "success": True,
            "enabled": True,
            "available": False,
            "scope": CHUFENG_RAG_SCOPE,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "The RAG status could not be checked.",
            },
        }, 200

    available = health.get("status") == "healthy"
    return {
        "success": True,
        "enabled": health.get("enabled") is True,
        "available": available,
        "scope": CHUFENG_RAG_SCOPE,
        "ollama_model": health.get("ollama_model"),
        "error": None if available else {
            "code": "RAG_UNAVAILABLE",
            "message": "The RAG server is not ready.",
        },
    }, 200


def refresh_rag_corpus() -> tuple[dict[str, Any], int]:
    return _execute(lambda client: client.refresh_corpus())


def retrieve_rag_context(data: Any) -> tuple[dict[str, Any], int]:
    validated, failure = _validated_request(data, "query")
    if failure is not None:
        return failure
    assert validated is not None
    query, top_k = validated
    return _execute(lambda client: client.retrieve_context(query, top_k))


def answer_rag_question(data: Any) -> tuple[dict[str, Any], int]:
    validated, failure = _validated_request(data, "question")
    if failure is not None:
        return failure
    assert validated is not None
    question, top_k = validated
    return _execute(lambda client: client.answer_question(question, top_k))
