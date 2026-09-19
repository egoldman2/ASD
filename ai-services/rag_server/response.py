"""Stable structured response helpers for the shared RAG service."""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping, Sequence


class ConfidenceCategory(str, Enum):
    """Human-readable confidence categories required by Release 1."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INSUFFICIENT = "insufficient"


class RAGErrorCode(str, Enum):
    """Machine-readable error categories returned by the RAG service."""

    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    SCOPE_NOT_FOUND = "SCOPE_NOT_FOUND"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    SOURCE_DATA_INVALID = "SOURCE_DATA_INVALID"
    INDEX_UNAVAILABLE = "INDEX_UNAVAILABLE"
    OLLAMA_UNAVAILABLE = "OLLAMA_UNAVAILABLE"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    RAG_DISABLED = "RAG_DISABLED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _confidence_value(
    confidence: ConfidenceCategory | str | None,
) -> str | None:
    if confidence is None:
        return None

    try:
        return ConfidenceCategory(confidence).value
    except ValueError as exc:
        allowed = ", ".join(category.value for category in ConfidenceCategory)
        raise ValueError(f"confidence must be one of: {allowed}.") from exc


def _error_code_value(code: RAGErrorCode | str) -> str:
    if isinstance(code, RAGErrorCode):
        return code.value
    return _required_text(code, "code")


def _normalise_citations(
    citations: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    if citations is None:
        return []
    if isinstance(citations, (str, bytes)):
        raise ValueError("citations must be a sequence of mappings.")

    normalised: list[dict[str, Any]] = []
    for citation in citations:
        if not isinstance(citation, Mapping):
            raise ValueError("each citation must be a mapping.")
        normalised.append(dict(citation))
    return normalised


def success_response(
    operation: str,
    data: Any,
    *,
    citations: Sequence[Mapping[str, Any]] | None = None,
    confidence: ConfidenceCategory | str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the common success envelope used by every RAG operation."""

    payload: dict[str, Any] = {
        "success": True,
        "operation": _required_text(operation, "operation"),
        "data": data,
        "citations": _normalise_citations(citations),
        "confidence": _confidence_value(confidence),
        "insufficient_context": False,
        "error": None,
    }
    if metadata is not None:
        payload["metadata"] = dict(metadata)
    return payload


def insufficient_context_response(
    operation: str,
    message: str,
    *,
    citations: Sequence[Mapping[str, Any]] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a successful request that found too little evidence to answer."""

    payload = success_response(
        operation,
        {"answer": _required_text(message, "message")},
        citations=citations,
        confidence=ConfidenceCategory.INSUFFICIENT,
        metadata=metadata,
    )
    payload["insufficient_context"] = True
    return payload


def error_response(
    operation: str,
    code: RAGErrorCode | str,
    message: str,
    *,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a safe, structured failure envelope for a RAG operation."""

    error: dict[str, Any] = {
        "code": _error_code_value(code),
        "message": _required_text(message, "message"),
    }
    if details is not None:
        error["details"] = dict(details)

    return {
        "success": False,
        "operation": _required_text(operation, "operation"),
        "data": None,
        "citations": [],
        "confidence": None,
        "insufficient_context": False,
        "error": error,
    }
