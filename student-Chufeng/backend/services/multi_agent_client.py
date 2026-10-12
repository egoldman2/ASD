"""HTTP client connecting Chufeng's backend to the shared Multi-Agent service."""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from typing import Any, Callable
from urllib.parse import quote, urlparse

import requests


DEFAULT_MULTI_AGENT_SERVER_URL = "http://127.0.0.1:5004"
DEFAULT_MULTI_AGENT_CLIENT_TIMEOUT_SECONDS = 180.0
CHUFENG_FEATURE = "product_catalogue"

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}

HttpRequest = Callable[..., Any]


class MultiAgentClientError(Exception):
    """Safe failure raised by Chufeng's Multi-Agent adapter."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "MULTI_AGENT_CLIENT_ERROR",
        status_code: int = 502,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)

    def to_dict(self) -> dict[str, dict[str, str]]:
        return {"error": {"code": self.code, "message": self.message}}


class MultiAgentConfigurationError(MultiAgentClientError):
    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code="MULTI_AGENT_CONFIGURATION_ERROR",
            status_code=500,
        )


class MultiAgentDisabledError(MultiAgentClientError):
    def __init__(self) -> None:
        super().__init__(
            "Multi-Agent integration is disabled.",
            code="MULTI_AGENT_DISABLED",
            status_code=503,
        )


def _boolean_setting(value: str, setting_name: str) -> bool:
    cleaned = value.strip().lower()
    if cleaned in _TRUE_VALUES:
        return True
    if cleaned in _FALSE_VALUES:
        return False
    raise MultiAgentConfigurationError(
        f"{setting_name} must be one of: true, false, 1, 0, yes, no, on, off."
    )


def _positive_timeout(value: str) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise MultiAgentConfigurationError(
            "MULTI_AGENT_CLIENT_TIMEOUT_SECONDS must be a number."
        ) from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise MultiAgentConfigurationError(
            "MULTI_AGENT_CLIENT_TIMEOUT_SECONDS must be greater than zero."
        )
    return timeout


def _server_url(value: str) -> str:
    cleaned = value.strip().rstrip("/")
    parsed = urlparse(cleaned)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise MultiAgentConfigurationError(
            "MULTI_AGENT_SERVER_URL must be an absolute HTTP or HTTPS URL "
            "without credentials, a query, or fragment."
        )
    return cleaned


@dataclass(frozen=True, slots=True)
class MultiAgentClientSettings:
    enabled: bool
    server_url: str
    timeout_seconds: float

    @classmethod
    def from_environment(cls) -> "MultiAgentClientSettings":
        return cls(
            enabled=_boolean_setting(
                os.getenv("MULTI_AGENT_ENABLED", "true"),
                "MULTI_AGENT_ENABLED",
            ),
            server_url=_server_url(
                os.getenv(
                    "MULTI_AGENT_SERVER_URL",
                    DEFAULT_MULTI_AGENT_SERVER_URL,
                )
            ),
            timeout_seconds=_positive_timeout(
                os.getenv(
                    "MULTI_AGENT_CLIENT_TIMEOUT_SECONDS",
                    str(DEFAULT_MULTI_AGENT_CLIENT_TIMEOUT_SECONDS),
                )
            ),
        )


class ChufengMultiAgentClient:
    """Validated synchronous adapter restricted to Product Catalogue workflows."""

    def __init__(
        self,
        settings: MultiAgentClientSettings | None = None,
        *,
        http_request: HttpRequest | None = None,
    ) -> None:
        self.settings = settings or MultiAgentClientSettings.from_environment()
        self._http_request = http_request or requests.request

    def _ensure_enabled(self) -> None:
        if not self.settings.enabled:
            raise MultiAgentDisabledError()

    def _send(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_enabled()
        arguments: dict[str, Any] = {
            "method": method,
            "url": f"{self.settings.server_url}{path}",
            "timeout": self.settings.timeout_seconds,
        }
        if payload is not None:
            arguments["json"] = payload

        try:
            response = self._http_request(**arguments)
        except requests.Timeout as exc:
            raise MultiAgentClientError(
                "The Multi-Agent server timed out.",
                code="MULTI_AGENT_TIMEOUT",
                status_code=504,
            ) from exc
        except requests.ConnectionError as exc:
            raise MultiAgentClientError(
                "The Multi-Agent server is unavailable.",
                code="MULTI_AGENT_UNAVAILABLE",
                status_code=503,
            ) from exc
        except requests.RequestException as exc:
            raise MultiAgentClientError(
                "The Multi-Agent server request failed.",
                code="MULTI_AGENT_REQUEST_FAILED",
                status_code=502,
            ) from exc

        status_code = getattr(response, "status_code", None)
        if not isinstance(status_code, int):
            raise self._invalid_response()
        try:
            result = response.json()
        except (TypeError, ValueError) as exc:
            raise self._invalid_response() from exc
        if not isinstance(result, dict):
            raise self._invalid_response()

        if not 200 <= status_code < 300:
            error = result.get("error")
            code = error.get("code") if isinstance(error, dict) else None
            message = error.get("message") if isinstance(error, dict) else None
            safe_code = code if isinstance(code, str) and code else "MULTI_AGENT_ERROR"
            safe_message = (
                message
                if isinstance(message, str) and 0 < len(message) <= 500
                else "The Multi-Agent server rejected the request."
            )
            safe_status = status_code if 400 <= status_code <= 599 else 502
            raise MultiAgentClientError(
                safe_message,
                code=safe_code,
                status_code=safe_status,
            )
        return result

    @staticmethod
    def _invalid_response() -> MultiAgentClientError:
        return MultiAgentClientError(
            "The Multi-Agent server returned an invalid response.",
            code="MULTI_AGENT_INVALID_RESPONSE",
            status_code=502,
        )

    @classmethod
    def _product_workflow(cls, result: Any) -> dict[str, Any]:
        if not isinstance(result, dict):
            raise cls._invalid_response()
        workflow_id = result.get("workflow_id")
        status = result.get("status")
        workflow_request = result.get("request")
        feature = (
            workflow_request.get("feature")
            if isinstance(workflow_request, dict)
            else None
        )
        if (
            not isinstance(workflow_id, str)
            or not workflow_id
            or not isinstance(status, str)
            or not status
            or feature != CHUFENG_FEATURE
        ):
            raise cls._invalid_response()
        return result

    def health(self) -> dict[str, Any]:
        result = self._send("GET", "/health")
        if result.get("status") != "ok" or not isinstance(
            result.get("service"), str
        ):
            raise self._invalid_response()
        return result

    def create_workflow(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("feature") != CHUFENG_FEATURE:
            raise ValueError(f"feature must be {CHUFENG_FEATURE}.")
        return self._product_workflow(
            self._send("POST", "/api/workflows", payload=payload)
        )

    def list_workflows(self) -> dict[str, Any]:
        result = self._send("GET", "/api/workflows")
        workflows = result.get("workflows")
        if not isinstance(workflows, list):
            raise self._invalid_response()
        product_workflows = []
        for workflow in workflows:
            if not isinstance(workflow, dict):
                raise self._invalid_response()
            request_data = workflow.get("request")
            if (
                isinstance(request_data, dict)
                and request_data.get("feature") == CHUFENG_FEATURE
            ):
                product_workflows.append(self._product_workflow(workflow))
        return {"count": len(product_workflows), "workflows": product_workflows}

    def latest_workflow(self) -> dict[str, Any]:
        workflows = self.list_workflows()["workflows"]
        if not workflows:
            raise MultiAgentClientError(
                "No Product Catalogue workflows have been recorded.",
                code="workflow_not_found",
                status_code=404,
            )
        return workflows[-1]

    @staticmethod
    def _workflow_path_id(workflow_id: str) -> str:
        if not isinstance(workflow_id, str) or not workflow_id.strip():
            raise ValueError("workflow_id must be a non-empty string.")
        return quote(workflow_id.strip(), safe="")

    @staticmethod
    def _is_other_feature(result: Any) -> bool:
        if not isinstance(result, dict):
            return False
        workflow_request = result.get("request")
        feature = (
            workflow_request.get("feature")
            if isinstance(workflow_request, dict)
            else None
        )
        return isinstance(feature, str) and feature != CHUFENG_FEATURE

    def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        result = self._send(
            "GET", f"/api/workflows/{self._workflow_path_id(workflow_id)}"
        )
        if self._is_other_feature(result):
            raise MultiAgentClientError(
                "Product Catalogue workflow was not found.",
                code="workflow_not_found",
                status_code=404,
            )
        return self._product_workflow(result)

    def submit_human_review(
        self,
        workflow_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        safe_id = self._workflow_path_id(workflow_id)
        self.get_workflow(workflow_id)
        result = self._send(
            "POST",
            f"/api/workflows/{safe_id}/review",
            payload=payload,
        )
        return self._product_workflow(result)
