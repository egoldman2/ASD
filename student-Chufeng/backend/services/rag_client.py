
"""HTTP client connecting Chufeng's backend to the shared local RAG service."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Callable
from urllib.parse import urlparse

import requests


DEFAULT_RAG_SERVER_URL = "http://127.0.0.1:5003"
DEFAULT_RAG_CLIENT_TIMEOUT_SECONDS = 60.0
CHUFENG_RAG_SCOPE = "chufeng_catalogue"
MAX_TOP_K = 20

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}

HttpRequest = Callable[..., Any]


class RAGClientError(Exception):
    """Safe failure raised by Chufeng's backend RAG adapter."""

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


def _boolean_setting(value: str, setting_name: str) -> bool:
    cleaned = value.strip().lower()
    if cleaned in _TRUE_VALUES:
        return True
    if cleaned in _FALSE_VALUES:
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


@dataclass(frozen=True, slots=True)
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
                    str(DEFAULT_RAG_CLIENT_TIMEOUT_SECONDS),
                )
            ),
        )


class ChufengRAGClient:
    """Validated synchronous adapter for Flask request handlers."""

    def __init__(
        self,
        settings: RAGClientSettings | None = None,
        *,
        http_request: HttpRequest | None = None,
    ) -> None:
        self.settings = settings or RAGClientSettings.from_environment()
        self._http_request = http_request or requests.request

    def _ensure_enabled(self) -> None:
        if not self.settings.enabled:
            raise RAGDisabledError()

    def _send(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        expected_operation: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_enabled()
        request_arguments: dict[str, Any] = {
            "method": method,
            "url": f"{self.settings.server_url}{path}",
            "timeout": self.settings.timeout_seconds,
        }
        if payload is not None:
            request_arguments["json"] = payload

        try:
            response = self._http_request(**request_arguments)
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise RAGClientError(
                "The RAG server is unavailable.",
                code="RAG_UNAVAILABLE",
                status_code=503,
            ) from exc
        except requests.RequestException as exc:
            raise RAGClientError(
                "The RAG server request failed.",
                code="RAG_REQUEST_FAILED",
                status_code=502,
            ) from exc

        status_code = getattr(response, "status_code", None)
        if not isinstance(status_code, int):
            raise RAGClientError(
                "The RAG server returned an invalid HTTP response.",
                code="RAG_INVALID_RESPONSE",
                status_code=502,
            )
        try:
            result = response.json()
        except (TypeError, ValueError) as exc:
            raise RAGClientError(
                "The RAG server returned invalid JSON.",
                code="RAG_INVALID_RESPONSE",
                status_code=502,
            ) from exc
        if not isinstance(result, dict):
            raise RAGClientError(
                "The RAG server returned an invalid response.",
                code="RAG_INVALID_RESPONSE",
                status_code=502,
            )

        if expected_operation is None:
            if status_code not in {200, 503}:
                raise RAGClientError(
                    "The RAG server health check failed.",
                    code="RAG_UNAVAILABLE",
                    status_code=503,
                )
            return result

        if (
            not isinstance(result.get("success"), bool)
            or result.get("operation") != expected_operation
            or not isinstance(result.get("citations"), list)
            or not isinstance(result.get("insufficient_context"), bool)
        ):
            raise RAGClientError(
                "The RAG server returned an invalid structured response.",
                code="RAG_INVALID_RESPONSE",
                status_code=502,
            )
        return result

    def health(self) -> dict[str, Any]:
        return self._send("GET", "/health")

    def refresh_corpus(self) -> dict[str, Any]:
        return self._send(
            "POST",
            "/refresh",
            payload={"scope": CHUFENG_RAG_SCOPE},
            expected_operation="refresh_corpus",
        )

    def retrieve_context(self, query: str, top_k: int) -> dict[str, Any]:
        return self._send(
            "POST",
            "/retrieve",
            payload={
                "scope": CHUFENG_RAG_SCOPE,
                "query": query,
                "top_k": top_k,
            },
            expected_operation="retrieve_context",
        )

    def answer_question(self, question: str, top_k: int) -> dict[str, Any]:
        return self._send(
            "POST",
            "/answer",
            payload={
                "scope": CHUFENG_RAG_SCOPE,
                "question": question,
                "top_k": top_k,
            },
            expected_operation="answer_question",
        )
