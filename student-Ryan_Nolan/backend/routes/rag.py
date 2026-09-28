"""Flask routes exposing Ryan's RAG integration to the inventory frontend.

The RAG client, settings and request handling live in this one module,
matching the other inventory blueprints. The knowledge scope is fixed to
ryan_inventory so this feature can never query another student's data.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests
from flask import Blueprint, g, jsonify, request


LOGGER = logging.getLogger(__name__)

rag_blueprint = Blueprint(
    "inventory_rag",
    __name__,
    url_prefix="/api/inventory/rag",
)

RAG_SCOPE = "ryan_inventory"
DEFAULT_RAG_SERVER_URL = "http://127.0.0.1:5003"
DEFAULT_RAG_TIMEOUT_SECONDS = 90.0

RAG_MODE_HEADER = "X-RAG-Mode"
RAG_MODE_ON_VALUES = {"1", "true", "yes", "on"}

MAX_QUESTION_LENGTH = 1000
MAX_TOP_K = 20

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------

class RAGClientError(Exception):
    """Safe failure raised by the inventory RAG adapter."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "RAG_CLIENT_ERROR",
        status_code: int = 502,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code

    def to_dict(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message}}


class RAGConfigurationError(RAGClientError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="RAG_CONFIGURATION_ERROR", status_code=500)


class RAGDisabledError(RAGClientError):
    def __init__(self) -> None:
        super().__init__(
            "RAG integration is disabled.",
            code="RAG_DISABLED",
            status_code=503,
        )


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------

def _boolean_setting(value: str, setting_name: str) -> bool:
    normalised = value.strip().lower()
    if normalised in _TRUE_VALUES:
        return True
    if normalised in _FALSE_VALUES:
        return False
    raise RAGConfigurationError(
        f"{setting_name} must be one of: true, false, 1, 0, yes, no, on, off."
    )


def _positive_timeout(value: str) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise RAGConfigurationError(
            "RAG_CLIENT_TIMEOUT_SECONDS must be a number."
        ) from exc
    if timeout <= 0:
        raise RAGConfigurationError(
            "RAG_CLIENT_TIMEOUT_SECONDS must be greater than zero."
        )
    return timeout


def _server_url(value: str) -> str:
    cleaned = value.strip().rstrip("/")
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RAGConfigurationError(
            "RAG_SERVER_URL must be an absolute HTTP or HTTPS URL."
        )
    return cleaned


@dataclass(frozen=True)
class RAGClientSettings:
    enabled: bool
    server_url: str
    timeout_seconds: float

    @classmethod
    def from_environment(cls) -> "RAGClientSettings":
        return cls(
            enabled=_boolean_setting(os.getenv("RAG_ENABLED", "true"), "RAG_ENABLED"),
            server_url=_server_url(
                os.getenv("RAG_SERVER_URL", DEFAULT_RAG_SERVER_URL)
            ),
            timeout_seconds=_positive_timeout(
                os.getenv(
                    "RAG_CLIENT_TIMEOUT_SECONDS",
                    str(DEFAULT_RAG_TIMEOUT_SECONDS),
                )
            ),
        )


# --------------------------------------------------------------------------
# RAG client
# --------------------------------------------------------------------------

class InventoryRAGClient:
    """Small HTTP adapter around the shared local RAG server."""

    def __init__(self, settings: RAGClientSettings | None = None) -> None:
        self.settings = settings or RAGClientSettings.from_environment()

    def _ensure_enabled(self) -> None:
        if not self.settings.enabled:
            raise RAGDisabledError()

    def _send(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_enabled()
        try:
            response = requests.request(
                method,
                f"{self.settings.server_url}{path}",
                json=body,
                timeout=self.settings.timeout_seconds,
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise RAGClientError(
                "The RAG server is unavailable.",
                code="RAG_UNAVAILABLE",
                status_code=503,
            ) from exc
        except requests.RequestException as exc:
            raise RAGClientError(
                "The RAG server request failed.",
                code="RAG_UNAVAILABLE",
                status_code=503,
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise RAGClientError(
                "The RAG server returned an invalid response.",
                code="RAG_INVALID_RESPONSE",
                status_code=502,
            ) from exc

        if not isinstance(payload, dict):
            raise RAGClientError(
                "The RAG server returned an invalid response.",
                code="RAG_INVALID_RESPONSE",
                status_code=502,
            )

        # Attach the upstream HTTP status so the route can pass it through.
        payload.setdefault("_http_status", response.status_code)
        return payload

    def health(self) -> dict[str, Any]:
        return self._send("GET", "/health")

    def refresh_corpus(self) -> dict[str, Any]:
        return self._send("POST", "/refresh", {"scope": RAG_SCOPE})

    def retrieve_context(self, query: str, top_k: int) -> dict[str, Any]:
        return self._send(
            "POST",
            "/retrieve",
            {"scope": RAG_SCOPE, "query": query, "top_k": top_k},
        )

    def answer_question(self, question: str, top_k: int) -> dict[str, Any]:
        return self._send(
            "POST",
            "/answer",
            {"scope": RAG_SCOPE, "question": question, "top_k": top_k},
        )


# --------------------------------------------------------------------------
# Request helpers
# --------------------------------------------------------------------------

def _create_client() -> InventoryRAGClient:
    """Create a client per request so environment overrides remain testable."""
    return InventoryRAGClient()


def _require_admin():
    if g.authenticated_user.get("role") != "admin":
        return jsonify({"error": "Administrator access required."}), 403
    return None


def _request_rag_mode_enabled() -> bool:
    value = request.headers.get(RAG_MODE_HEADER, "on")
    return value.strip().lower() in RAG_MODE_ON_VALUES


def _rag_mode_disabled_response():
    return jsonify(
        {
            "error": {
                "code": "RAG_DISABLED",
                "message": "RAG mode is disabled for this request.",
            }
        }
    ), 403


def _invalid(message: str):
    return jsonify(
        {"error": {"code": "INVALID_ARGUMENT", "message": message}}
    ), 400


def _safe_internal_error():
    return jsonify(
        {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "The RAG request could not be completed.",
            }
        }
    ), 500


def _pass_through(payload: dict[str, Any]):
    """Return the RAG envelope with the upstream status code."""
    status_code = payload.pop("_http_status", 200)
    return jsonify(payload), status_code


def _validated_top_k(value: Any) -> int | None:
    """Return a valid top_k, or None if it is invalid. Missing means default."""
    if value is None:
        return 5
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if not 1 <= value <= MAX_TOP_K:
        return None
    return value


def _question_from_body(body: Any, field: str):
    """Validate the JSON body. Returns (text, top_k, error_response)."""
    if not isinstance(body, dict):
        return None, None, _invalid("A JSON request body is required.")

    text = body.get(field)
    if not isinstance(text, str) or not text.strip():
        return None, None, _invalid(f"{field} must be a non-empty string.")
    text = text.strip()
    if len(text) > MAX_QUESTION_LENGTH:
        return None, None, _invalid(
            f"{field} must not exceed {MAX_QUESTION_LENGTH} characters."
        )

    top_k = _validated_top_k(body.get("top_k"))
    if top_k is None:
        return None, None, _invalid(
            f"top_k must be an integer between 1 and {MAX_TOP_K}."
        )
    return text, top_k, None


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@rag_blueprint.get("/status")
def get_rag_status():
    """UI-friendly snapshot. Status failures are never fatal (always 200)."""
    if (error := _require_admin()) is not None:
        return error

    try:
        health = _create_client().health()
    except RAGDisabledError as exc:
        return jsonify(
            {
                "success": True,
                "enabled": False,
                "available": False,
                "scope": RAG_SCOPE,
                "error": {"code": exc.code, "message": exc.message},
            }
        ), 200
    except RAGClientError as exc:
        return jsonify(
            {
                "success": True,
                "enabled": True,
                "available": False,
                "scope": RAG_SCOPE,
                "error": {"code": exc.code, "message": exc.message},
            }
        ), 200
    except Exception:
        LOGGER.exception("Unexpected failure while checking RAG status")
        return jsonify(
            {
                "success": True,
                "enabled": True,
                "available": False,
                "scope": RAG_SCOPE,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "The RAG status could not be checked.",
                },
            }
        ), 200

    scope_available = RAG_SCOPE in health.get("available_scopes", [])
    return jsonify(
        {
            "success": True,
            "enabled": True,
            "available": health.get("status") == "healthy" and scope_available,
            "scope": RAG_SCOPE,
            "model": health.get("ollama_model"),
            "error": None,
        }
    ), 200


@rag_blueprint.post("/refresh")
def refresh_rag_corpus():
    """Rebuild the ryan_inventory vector index from the live database."""
    if (error := _require_admin()) is not None:
        return error
    if not _request_rag_mode_enabled():
        return _rag_mode_disabled_response()

    try:
        payload = _create_client().refresh_corpus()
    except RAGClientError as exc:
        return jsonify(exc.to_dict()), exc.status_code
    except Exception:
        LOGGER.exception("Unexpected failure while refreshing RAG corpus")
        return _safe_internal_error()
    return _pass_through(payload)


@rag_blueprint.post("/retrieve")
def retrieve_rag_context():
    """POST /api/inventory/rag/retrieve  Body: { query, top_k? }"""
    if (error := _require_admin()) is not None:
        return error
    if not _request_rag_mode_enabled():
        return _rag_mode_disabled_response()

    query, top_k, failure = _question_from_body(
        request.get_json(silent=True), "query"
    )
    if failure is not None:
        return failure

    try:
        payload = _create_client().retrieve_context(query, top_k)
    except RAGClientError as exc:
        return jsonify(exc.to_dict()), exc.status_code
    except Exception:
        LOGGER.exception("Unexpected failure while retrieving RAG context")
        return _safe_internal_error()
    return _pass_through(payload)


@rag_blueprint.post("/answer")
def answer_rag_question():
    """POST /api/inventory/rag/answer  Body: { question, top_k? }

    Returns a grounded answer with citations and a confidence category, or
    an insufficient-context response when nothing relevant is retrieved.
    """
    if (error := _require_admin()) is not None:
        return error
    if not _request_rag_mode_enabled():
        return _rag_mode_disabled_response()

    question, top_k, failure = _question_from_body(
        request.get_json(silent=True), "question"
    )
    if failure is not None:
        return failure

    try:
        payload = _create_client().answer_question(question, top_k)
    except RAGClientError as exc:
        return jsonify(exc.to_dict()), exc.status_code
    except Exception:
        LOGGER.exception("Unexpected failure while answering RAG question")
        return _safe_internal_error()
    return _pass_through(payload)