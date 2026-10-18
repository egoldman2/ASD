"""Feature-scoped HTTP client for the shared Multi-Agent service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
import os
from typing import Any, Callable
from urllib.parse import quote, urlparse

import requests

from shared.feature_flags import feature_enabled


DEFAULT_MULTI_AGENT_SERVER_URL = "http://127.0.0.1:5004"
DEFAULT_MULTI_AGENT_CLIENT_TIMEOUT_SECONDS = 180.0

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}

HttpRequest = Callable[..., Any]


class MultiAgentClientError(Exception):
    """Safe failure raised by the Multi-Agent adapter."""

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
    if not math.isfinite(timeout) or not 0 < timeout <= 360:
        raise MultiAgentConfigurationError(
            "MULTI_AGENT_CLIENT_TIMEOUT_SECONDS must be greater than zero and at most 360."
        )
    return timeout


def _server_url(value: str) -> str:
    cleaned = value.strip().rstrip("/")
    try:
        parsed = urlparse(cleaned)
        port = parsed.port
    except ValueError as exc:
        raise MultiAgentConfigurationError(
            "MULTI_AGENT_SERVER_URL is invalid."
        ) from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or (port is not None and not 1 <= port <= 65_535)
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


class MultiAgentClient:
    """Validated synchronous adapter restricted to one feature."""

    def __init__(
        self,
        feature: str,
        settings: MultiAgentClientSettings | None = None,
        *,
        http_request: HttpRequest | None = None,
    ) -> None:
        if feature not in {
            "product_catalogue",
            "inventory",
            "customer_loyalty",
            "order_returns",
            "customer_support",
        }:
            raise ValueError("Unknown Multi-Agent feature.")
        self.feature = feature
        self.settings = settings or MultiAgentClientSettings.from_environment()
        self._http_request = http_request or requests.request

    def _ensure_enabled(self) -> None:
        if not self.settings.enabled or not feature_enabled():
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
            "allow_redirects": False,
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

    def _workflow(self, result: Any) -> dict[str, Any]:
        if not isinstance(result, dict):
            raise self._invalid_response()
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
            or feature != self.feature
        ):
            raise self._invalid_response()
        if self.feature == "customer_support":
            self._support_workflow(result)
        return result

    def _support_workflow(self, result: dict[str, Any]) -> None:
        """Keep the catalogue's legacy response contract; validate support snapshots."""

        def text(value, limit=10_000):
            return isinstance(value, str) and 0 < len(value.strip()) <= limit

        def timestamp(value):
            if not text(value, 64):
                return False
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed.utcoffset() is not None
            except ValueError:
                return False

        request = result["request"]
        evidence = request.get("evidence")
        if (
            not text(request.get("user_request"), 4_000)
            or not timestamp(result.get("timestamp"))
            or not isinstance(evidence, list)
            or not 1 <= len(evidence) <= 20
        ):
            raise self._invalid_response()
        ids = []
        for item in evidence:
            if not isinstance(item, dict):
                raise self._invalid_response()
            source = item.get("source")
            if (
                not text(item.get("evidence_id"), 128)
                or not isinstance(item.get("data"), dict)
                or not item["data"]
                or not isinstance(source, dict)
                or not text(source.get("service"), 128)
                or not text(source.get("endpoint"), 2_048)
                or not timestamp(source.get("retrieved_at"))
            ):
                raise self._invalid_response()
            ids.append(item["evidence_id"])
        if len(set(ids)) != len(ids):
            raise self._invalid_response()
        for agent, output in (
            ("planner", "plan"),
            ("worker", "output"),
            ("reviewer", "review"),
        ):
            stage = result.get(f"{agent}_result")
            if (
                not isinstance(stage, dict)
                or stage.get("agent") != agent
                or stage.get("status") != "completed"
                or not text(stage.get("model"), 128)
                or not text(stage.get(output))
                or stage.get("evidence_ids") != ids
                or stage.get("human_approval_required") is not True
            ):
                raise self._invalid_response()
        decisions = {
            "accepted": "accept",
            "partially_accepted": "partially_accept",
            "rejected": "reject",
        }
        if "human_review" not in result:
            raise self._invalid_response()
        status, review = result["status"], result["human_review"]
        if status == "awaiting_human_review":
            if review is not None:
                raise self._invalid_response()
        elif (
            status not in decisions
            or not isinstance(review, dict)
            or review.get("decision") != decisions[status]
            or not text(review.get("reason"), 2_000)
            or not text(review.get("reviewed_by"), 128)
            or not timestamp(review.get("reviewed_at"))
        ):
            raise self._invalid_response()

    def health(self) -> dict[str, Any]:
        result = self._send("GET", "/health")
        if result.get("status") != "ok" or not isinstance(result.get("service"), str):
            raise self._invalid_response()
        return result

    def create_workflow(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("feature") != self.feature:
            raise ValueError(f"feature must be {self.feature}.")
        return self._workflow(self._send("POST", "/api/workflows", payload=payload))

    def list_workflows(self) -> dict[str, Any]:
        result = self._send("GET", "/api/workflows")
        workflows = result.get("workflows")
        if not isinstance(workflows, list):
            raise self._invalid_response()
        feature_workflows = []
        for workflow in workflows:
            if not isinstance(workflow, dict):
                raise self._invalid_response()
            request_data = workflow.get("request")
            if (
                isinstance(request_data, dict)
                and request_data.get("feature") == self.feature
            ):
                feature_workflows.append(self._workflow(workflow))
        return {"count": len(feature_workflows), "workflows": feature_workflows}

    def latest_workflow(self) -> dict[str, Any]:
        workflows = self.list_workflows()["workflows"]
        if not workflows:
            raise MultiAgentClientError(
                "No workflows for this feature have been recorded.",
                code="workflow_not_found",
                status_code=404,
            )
        return workflows[-1]

    @staticmethod
    def _workflow_path_id(workflow_id: str) -> str:
        if not isinstance(workflow_id, str) or not workflow_id.strip():
            raise ValueError("workflow_id must be a non-empty string.")
        return quote(workflow_id.strip(), safe="")

    def _is_other_feature(self, result: Any) -> bool:
        if not isinstance(result, dict):
            return False
        workflow_request = result.get("request")
        feature = (
            workflow_request.get("feature")
            if isinstance(workflow_request, dict)
            else None
        )
        return isinstance(feature, str) and feature != self.feature

    def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        result = self._send(
            "GET", f"/api/workflows/{self._workflow_path_id(workflow_id)}"
        )
        if self._is_other_feature(result):
            raise MultiAgentClientError(
                "Workflow was not found.",
                code="workflow_not_found",
                status_code=404,
            )
        if result.get("workflow_id") != workflow_id.strip():
            raise self._invalid_response()
        return self._workflow(result)

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
        if result.get("workflow_id") != workflow_id.strip():
            raise self._invalid_response()
        return self._workflow(result)
