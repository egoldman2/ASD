"""Reliable Ollama client shared by every workflow agent."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from time import monotonic
from typing import Any, Mapping

import requests

from multi_agent_server.config import MultiAgentSettings


DEFAULT_TEMPERATURE = 0.1


class AgentRole(str, Enum):
    """Model-using roles in the shared multi-agent workflow."""

    PLANNER = "planner"
    WORKER = "worker"
    REVIEWER = "reviewer"


class ModelClientError(RuntimeError):
    """Base class for safe, categorised Ollama client failures."""

    code = "model_client_error"

    def __init__(self, message: str, *, role: AgentRole, model: str) -> None:
        self.role = role
        self.model = model
        self.message = message
        super().__init__(message)

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Return an API-safe error without prompt or response contents."""

        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "role": self.role.value,
                "model": self.model,
            }
        }


class ModelConnectionError(ModelClientError):
    """Raised when the configured Ollama server cannot be reached."""

    code = "model_connection_error"


class ModelTimeoutError(ModelClientError):
    """Raised when Ollama does not finish within the configured timeout."""

    code = "model_timeout"


class ModelHTTPError(ModelClientError):
    """Raised when Ollama returns an unsuccessful HTTP status."""

    code = "model_http_error"

    def __init__(
        self,
        message: str,
        *,
        role: AgentRole,
        model: str,
        status_code: int,
    ) -> None:
        self.status_code = status_code
        super().__init__(message, role=role, model=model)

    def to_dict(self) -> dict[str, dict[str, Any]]:
        payload = super().to_dict()
        payload["error"]["status_code"] = self.status_code
        return payload


class ModelResponseError(ModelClientError):
    """Raised when Ollama returns an unusable success response."""

    code = "model_response_error"


@dataclass(frozen=True, slots=True)
class ModelGeneration:
    """Normalised result returned to Planner, Worker, or Reviewer."""

    role: AgentRole
    model: str
    text: str
    elapsed_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "model": self.model,
            "response": self.text,
            "elapsed_ms": self.elapsed_ms,
        }


def _normalise_role(role: AgentRole | str) -> AgentRole:
    cause: ValueError | None = None
    if isinstance(role, AgentRole):
        return role
    if isinstance(role, str):
        try:
            return AgentRole(role.strip().lower())
        except ValueError as error:
            cause = error
    allowed = ", ".join(item.value for item in AgentRole)
    raise ValueError(f"role must be one of: {allowed}.") from cause


class OllamaModelClient:
    """Call the configured local Ollama server through one tested boundary."""

    def __init__(
        self,
        settings: MultiAgentSettings,
        session: requests.Session | None = None,
    ) -> None:
        self._settings = settings
        self._session = session if session is not None else requests.Session()

    def model_for(self, role: AgentRole | str) -> str:
        """Return the configured model name for an agent role."""

        normalised_role = _normalise_role(role)
        return {
            AgentRole.PLANNER: self._settings.planner_model,
            AgentRole.WORKER: self._settings.worker_model,
            AgentRole.REVIEWER: self._settings.reviewer_model,
        }[normalised_role]

    def generate(self, role: AgentRole | str, prompt: str) -> ModelGeneration:
        """Generate one non-streaming response or raise a categorised failure."""

        normalised_role = _normalise_role(role)
        model = self.model_for(normalised_role)
        if not isinstance(prompt, str):
            raise TypeError("prompt must be a string.")
        if not prompt.strip():
            raise ValueError("prompt must not be empty.")

        started_at = monotonic()
        try:
            response = self._session.post(
                self._settings.ollama_generate_url,
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": DEFAULT_TEMPERATURE},
                },
                timeout=self._settings.timeout_seconds,
            )
        except requests.Timeout as exc:
            raise ModelTimeoutError(
                "Ollama generation timed out.",
                role=normalised_role,
                model=model,
            ) from exc
        except requests.ConnectionError as exc:
            raise ModelConnectionError(
                "Could not connect to the Ollama server.",
                role=normalised_role,
                model=model,
            ) from exc
        except requests.RequestException as exc:
            raise ModelConnectionError(
                "The request to the Ollama server failed.",
                role=normalised_role,
                model=model,
            ) from exc

        if not 200 <= response.status_code < 300:
            raise ModelHTTPError(
                f"Ollama returned HTTP {response.status_code}.",
                role=normalised_role,
                model=model,
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise ModelResponseError(
                "Ollama returned invalid JSON.",
                role=normalised_role,
                model=model,
            ) from exc
        if not isinstance(payload, Mapping):
            raise ModelResponseError(
                "Ollama response must be a JSON object.",
                role=normalised_role,
                model=model,
            )

        text = payload.get("response")
        if not isinstance(text, str) or not text.strip():
            raise ModelResponseError(
                "Ollama response is missing generated text.",
                role=normalised_role,
                model=model,
            )

        elapsed_ms = max(0, round((monotonic() - started_at) * 1_000))
        return ModelGeneration(
            role=normalised_role,
            model=model,
            text=text.strip(),
            elapsed_ms=elapsed_ms,
        )
