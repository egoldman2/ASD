"""Small validated client for the local Ollama chat API."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import time
from typing import Any, Callable

import requests
from shared.feature_flags import feature_enabled

from rag_server.config import RAGSettings, get_settings


MAX_PROMPT_LENGTH = 50_000
MAX_RESPONSE_LENGTH = 10_000
MAX_RESPONSE_BYTES = 64 * 1024

HttpPost = Callable[..., Any]


class OllamaUnavailableError(RuntimeError):
    """Raised when the configured local Ollama service cannot be reached."""


class OllamaResponseError(RuntimeError):
    """Raised when Ollama returns an invalid or unusable response."""


def _required_text(value: Any, field_name: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    cleaned = value.strip()
    if len(cleaned) > maximum:
        raise ValueError(f"{field_name} must not exceed {maximum} characters.")
    return cleaned


@dataclass(frozen=True, slots=True)
class OllamaAnswer:
    """Validated content returned by the configured local model."""

    content: str
    model: str


class OllamaClient:
    """Send deterministic, non-streaming grounded-answer requests to Ollama."""

    def __init__(
        self,
        *,
        settings: RAGSettings | None = None,
        http_post: HttpPost | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._http_post = http_post

    def generate_answer(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        timeout_seconds: float | None = None,
    ) -> OllamaAnswer:
        """Return one validated local chat completion."""

        if not self.settings.enabled or not feature_enabled():
            raise OllamaUnavailableError("AI or RAG mode is disabled.")

        cleaned_system_prompt = _required_text(
            system_prompt,
            "system_prompt",
            MAX_PROMPT_LENGTH,
        )
        cleaned_user_prompt = _required_text(
            user_prompt,
            "user_prompt",
            MAX_PROMPT_LENGTH,
        )
        post = self._http_post or requests.post
        budget = self.settings.request_timeout_seconds if timeout_seconds is None else timeout_seconds
        if isinstance(budget, bool) or not isinstance(budget, (int, float)) or not math.isfinite(budget) or not 0 < budget <= 90:
            raise ValueError("Generation timeout must be finite, positive and at most 90 seconds.")
        deadline = time.monotonic() + budget

        try:
            response = post(
                f"{self.settings.ollama_url}/api/chat",
                json={
                    "model": self.settings.ollama_model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": cleaned_system_prompt},
                        {"role": "user", "content": cleaned_user_prompt},
                    ],
                    "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 512},
                },
                timeout=budget,
                stream=True,
                allow_redirects=False,
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise OllamaUnavailableError(
                "The local Ollama service is currently unavailable."
            ) from exc
        except requests.RequestException as exc:
            raise OllamaUnavailableError(
                "The local Ollama request failed."
            ) from exc

        try:
            status_code = getattr(response, "status_code", None)
            if isinstance(status_code, bool) or not isinstance(status_code, int):
                raise OllamaResponseError("The local Ollama service returned an invalid HTTP response.")
            if status_code >= 500:
                raise OllamaUnavailableError("The local Ollama service returned a server error.")
            if not 200 <= status_code < 300:
                raise OllamaResponseError("The local Ollama service rejected the generation request.")
            raw = bytearray()
            for chunk in response.iter_content(chunk_size=4096):
                if time.monotonic() > deadline:
                    raise OllamaUnavailableError("The local Ollama generation deadline expired.")
                raw.extend(chunk)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise OllamaResponseError("The local Ollama response exceeded its size limit.")
            payload = json.loads(raw)
        except requests.RequestException as exc:
            raise OllamaUnavailableError("The local Ollama response could not be received.") from exc
        except (TypeError, ValueError, UnicodeError) as exc:
            raise OllamaResponseError(
                "The local Ollama service returned invalid JSON."
            ) from exc
        finally:
            response.close()
        if not isinstance(payload, dict):
            raise OllamaResponseError(
                "The local Ollama service returned an invalid payload."
            )
        if payload.get("done") is not True or payload.get("done_reason") == "length":
            raise OllamaResponseError("The local model did not finish a complete answer.")

        message = payload.get("message")
        if not isinstance(message, dict):
            raise OllamaResponseError(
                "The local Ollama service returned an invalid message."
            )
        try:
            content = _required_text(
                message.get("content"),
                "Ollama response content",
                MAX_RESPONSE_LENGTH,
            )
        except ValueError as exc:
            raise OllamaResponseError(str(exc)) from exc

        returned_model = payload.get("model")
        if not isinstance(returned_model, str) or not returned_model.strip() or len(returned_model) > 160:
            raise OllamaResponseError("The local model returned an invalid model identity.")
        return OllamaAnswer(content=content, model=returned_model.strip())
