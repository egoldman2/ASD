"""Flask routes connecting Howard's Orders and Returns feature to the shared Multi-Agent Server.

Release 2 flow:
Frontend UI -> this blueprint -> Multi-Agent Server
(Planner -> Worker -> Reviewer) -> Human Review -> Frontend UI.

The backend collects the order/return evidence itself (the Multi-Agent Server
never reads the database) and always sends feature="order_returns".

Workflows can take minutes on slower machines and a long-held connection from
the container to the host can be dropped, so the workflow runs as a background
job: POST /workflows returns a job_id immediately and the frontend polls
GET /jobs/<job_id>.
"""

from __future__ import annotations

import logging
import math
import os
import socket
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import quote, urlparse

import requests
from flask import Blueprint, g, jsonify, request
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection


LOGGER = logging.getLogger(__name__)

ORDER_RETURNS_FEATURE = "order_returns"
SERVICE_NAME = "order-returns-backend"

DEFAULT_MULTI_AGENT_SERVER_URL = "http://127.0.0.1:5004"
DEFAULT_MULTI_AGENT_CLIENT_TIMEOUT_SECONDS = 360.0

MAX_QUESTION_LENGTH = 1000
MAX_REASON_LENGTH = 2000
REVIEW_DECISIONS = {"accept", "partially_accept", "reject"}

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}

RECOVERY_POLL_SECONDS = 10
RECOVERY_LIMIT_SECONDS = 150 * 60
MAX_STORED_JOBS = 50

_JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()

multi_agent_blueprint = Blueprint(
    "order_returns_multi_agent",
    __name__,
    url_prefix="/api/order-returns/multi-agent",
)

DB = os.environ.get("ORDERS_DATABASE_PATH") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "database", "orders.db"
)


# --------------------------------------------------------------------------
# Inline Multi-Agent client (feature-locked to order_returns)
# --------------------------------------------------------------------------

class MultiAgentClientError(Exception):
    def __init__(self, message, *, code="MULTI_AGENT_CLIENT_ERROR", status_code=502):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)

    def to_dict(self):
        return {"error": {"code": self.code, "message": self.message}}


class MultiAgentConfigurationError(MultiAgentClientError):
    def __init__(self, message):
        super().__init__(message, code="MULTI_AGENT_CONFIGURATION_ERROR", status_code=500)


class MultiAgentDisabledError(MultiAgentClientError):
    def __init__(self):
        super().__init__(
            "Multi-Agent integration is disabled.",
            code="MULTI_AGENT_DISABLED",
            status_code=503,
        )


def _boolean_setting(value, name):
    cleaned = value.strip().lower()
    if cleaned in _TRUE_VALUES:
        return True
    if cleaned in _FALSE_VALUES:
        return False
    raise MultiAgentConfigurationError(f"{name} must be true or false.")


def _positive_timeout(value):
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


def _server_url(value):
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
            "MULTI_AGENT_SERVER_URL must be a plain HTTP or HTTPS URL."
        )
    return cleaned


@dataclass(frozen=True)
class MultiAgentClientSettings:
    enabled: bool
    server_url: str
    timeout_seconds: float

    @classmethod
    def from_environment(cls):
        return cls(
            enabled=_boolean_setting(
                os.getenv("MULTI_AGENT_ENABLED", "true"), "MULTI_AGENT_ENABLED"
            ),
            server_url=_server_url(
                os.getenv("MULTI_AGENT_SERVER_URL", DEFAULT_MULTI_AGENT_SERVER_URL)
            ),
            timeout_seconds=_positive_timeout(
                os.getenv(
                    "MULTI_AGENT_CLIENT_TIMEOUT_SECONDS",
                    str(DEFAULT_MULTI_AGENT_CLIENT_TIMEOUT_SECONDS),
                )
            ),
        )


class OrderReturnsMultiAgentClient:
    def __init__(self, settings=None, *, http_request=None):
        self.settings = settings or MultiAgentClientSettings.from_environment()
        self._http_request = http_request or requests.request

    def _ensure_enabled(self):
        if not self.settings.enabled:
            raise MultiAgentDisabledError()

    def _send(self, method, path, *, payload=None):
        self._ensure_enabled()
        arguments = {
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
            raise MultiAgentClientError(
                message
                if isinstance(message, str) and 0 < len(message) <= 500
                else "The Multi-Agent server rejected the request.",
                code=code if isinstance(code, str) and code else "MULTI_AGENT_ERROR",
                status_code=status_code if 400 <= status_code <= 599 else 502,
            )
        return result

    @staticmethod
    def _invalid_response():
        return MultiAgentClientError(
            "The Multi-Agent server returned an invalid response.",
            code="MULTI_AGENT_INVALID_RESPONSE",
            status_code=502,
        )

    @classmethod
    def _order_returns_workflow(cls, result):
        if not isinstance(result, dict):
            raise cls._invalid_response()
        workflow_id = result.get("workflow_id")
        status = result.get("status")
        req = result.get("request")
        feature = req.get("feature") if isinstance(req, dict) else None
        if (
            not isinstance(workflow_id, str)
            or not workflow_id
            or not isinstance(status, str)
            or not status
            or feature != ORDER_RETURNS_FEATURE
        ):
            raise cls._invalid_response()
        return result

    def health(self):
        result = self._send("GET", "/health")
        if result.get("status") != "ok" or not isinstance(result.get("service"), str):
            raise self._invalid_response()
        return result

    def create_workflow(self, payload):
        if payload.get("feature") != ORDER_RETURNS_FEATURE:
            raise ValueError(f"feature must be {ORDER_RETURNS_FEATURE}.")
        return self._order_returns_workflow(
            self._send("POST", "/api/workflows", payload=payload)
        )

    def list_workflows(self):
        result = self._send("GET", "/api/workflows")
        workflows = result.get("workflows")
        if not isinstance(workflows, list):
            raise self._invalid_response()
        ours = []
        for workflow in workflows:
            if not isinstance(workflow, dict):
                raise self._invalid_response()
            req = workflow.get("request")
            if isinstance(req, dict) and req.get("feature") == ORDER_RETURNS_FEATURE:
                ours.append(self._order_returns_workflow(workflow))
        return {"count": len(ours), "workflows": ours}

    @staticmethod
    def _workflow_path_id(workflow_id):
        if not isinstance(workflow_id, str) or not workflow_id.strip():
            raise ValueError("workflow_id must be a non-empty string.")
        return quote(workflow_id.strip(), safe="")

    def get_workflow(self, workflow_id):
        result = self._send(
            "GET", f"/api/workflows/{self._workflow_path_id(workflow_id)}"
        )
        req = result.get("request") if isinstance(result, dict) else None
        feature = req.get("feature") if isinstance(req, dict) else None
        if isinstance(feature, str) and feature != ORDER_RETURNS_FEATURE:
            raise MultiAgentClientError(
                "Order and Returns workflow was not found.",
                code="workflow_not_found",
                status_code=404,
            )
        return self._order_returns_workflow(result)

    def submit_human_review(self, workflow_id, payload):
        safe_id = self._workflow_path_id(workflow_id)
        self.get_workflow(workflow_id)
        return self._order_returns_workflow(
            self._send("POST", f"/api/workflows/{safe_id}/review", payload=payload)
        )


# --------------------------------------------------------------------------
# Evidence from the live orders database
# --------------------------------------------------------------------------

def _error(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


def _utc_timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def _source(endpoint, retrieved_at):
    return {"service": SERVICE_NAME, "endpoint": endpoint, "retrieved_at": retrieved_at}


def _collect_evidence(return_id, order_id):
    retrieved_at = _utc_timestamp()
    conn = _db()
    try:
        if return_id is not None:
            ret = conn.execute(
                "SELECT return_id, order_id, reason, status, created_at "
                "FROM returns WHERE return_id = ?",
                (return_id,),
            ).fetchone()
            if ret is None:
                raise LookupError("return_not_found")
            ret = dict(ret)
            order = conn.execute(
                "SELECT order_id, customer_id, order_date, status, total "
                "FROM orders WHERE order_id = ?",
                (ret["order_id"],),
            ).fetchone()
            item_count = conn.execute(
                "SELECT COUNT(*) FROM order_items WHERE order_id = ?",
                (ret["order_id"],),
            ).fetchone()[0]
            data = {
                "return": ret,
                "order": dict(order) if order is not None else None,
                "order_item_count": item_count,
            }
            return [
                {
                    "evidence_id": f"order-returns-return-{return_id}",
                    "source": _source(
                        f"/api/order-returns/returns/{return_id}", retrieved_at
                    ),
                    "data": data,
                }
            ]

        order = conn.execute(
            "SELECT order_id, customer_id, order_date, status, total "
            "FROM orders WHERE order_id = ?",
            (order_id,),
        ).fetchone()
        if order is None:
            raise LookupError("order_not_found")
        order = dict(order)
        order["item_count"] = conn.execute(
            "SELECT COUNT(*) FROM order_items WHERE order_id = ?",
            (order_id,),
        ).fetchone()[0]
        return [
            {
                "evidence_id": f"order-returns-order-{order_id}",
                "source": _source(
                    f"/api/order-returns/orders/{order_id}", retrieved_at
                ),
                "data": {"order": order},
            }
        ]
    finally:
        conn.close()


def _reviewer_identity(user):
    if not isinstance(user, dict):
        return None
    email = user.get("email")
    if isinstance(email, str) and 0 < len(email.strip()) <= 128:
        return email.strip()
    user_id = user.get("id")
    if isinstance(user_id, int) and not isinstance(user_id, bool):
        return f"user:{user_id}"
    return None


# --------------------------------------------------------------------------
# Background workflow jobs
# --------------------------------------------------------------------------

def _new_job():
    job_id = uuid.uuid4().hex
    with _JOBS_LOCK:
        if len(_JOBS) >= MAX_STORED_JOBS:
            finished = [
                key
                for key, job in _JOBS.items()
                if job["status"] in {"completed", "failed"}
            ]
            for key in finished[: len(_JOBS) - MAX_STORED_JOBS + 1]:
                del _JOBS[key]
        _JOBS[job_id] = {
            "job_id": job_id,
            "status": "running",
            "started_at": _utc_timestamp(),
            "workflow": None,
            "error": None,
        }
    return job_id


def _update_job(job_id, **changes):
    with _JOBS_LOCK:
        if job_id in _JOBS:
            _JOBS[job_id].update(changes)


def _get_job(job_id):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job is not None else None


def _find_recovered_workflow(client, fingerprint):
    for workflow in reversed(client.list_workflows()["workflows"]):
        evidence = (workflow.get("request") or {}).get("evidence") or []
        first = evidence[0] if evidence and isinstance(evidence[0], dict) else {}
        if (first.get("source") or {}).get("retrieved_at") == fingerprint:
            return workflow
    return None


class _KeepAliveAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        options = list(HTTPConnection.default_socket_options)
        options.append((socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1))
        for name, value in (
            ("TCP_KEEPIDLE", 30),
            ("TCP_KEEPINTVL", 15),
            ("TCP_KEEPCNT", 8),
        ):
            option = getattr(socket, name, None)
            if option is not None:
                options.append((socket.IPPROTO_TCP, option, value))
        kwargs["socket_options"] = options
        super().init_poolmanager(*args, **kwargs)


def _long_request_client():
    session = requests.Session()
    session.mount("http://", _KeepAliveAdapter())
    session.mount("https://", _KeepAliveAdapter())
    return OrderReturnsMultiAgentClient(http_request=session.request)


def _run_workflow_job(job_id, payload, fingerprint):
    client = _long_request_client()
    try:
        result = client.create_workflow(payload)
        _update_job(job_id, status="completed", workflow=result)
        return
    except MultiAgentClientError as exc:
        if exc.code not in {"MULTI_AGENT_UNAVAILABLE", "MULTI_AGENT_TIMEOUT"}:
            _update_job(job_id, status="failed", error=exc.to_dict()["error"])
            return
        LOGGER.warning("Connection to the Multi-Agent server dropped; recovering")
        _update_job(job_id, status="recovering")
    except Exception:
        LOGGER.exception("Unexpected failure while running Multi-Agent workflow")
        _update_job(
            job_id,
            status="failed",
            error={
                "code": "INTERNAL_ERROR",
                "message": "The Multi-Agent request could not be completed.",
            },
        )
        return

    deadline = time.monotonic() + RECOVERY_LIMIT_SECONDS
    while time.monotonic() < deadline:
        time.sleep(RECOVERY_POLL_SECONDS)
        try:
            workflow = _find_recovered_workflow(client, fingerprint)
        except MultiAgentClientError:
            continue
        except Exception:
            LOGGER.exception("Unexpected failure while recovering workflow")
            continue
        if workflow is not None:
            _update_job(job_id, status="completed", workflow=workflow)
            return

    _update_job(
        job_id,
        status="failed",
        error={
            "code": "WORKFLOW_NOT_RECOVERED",
            "message": (
                "The agents did not return a result. The workflow may have "
                "failed on the Multi-Agent server (check its terminal log)."
            ),
        },
    )


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@multi_agent_blueprint.get("/status")
def get_multi_agent_status():
    try:
        health = OrderReturnsMultiAgentClient().health()
    except MultiAgentDisabledError as exc:
        return jsonify(
            {"enabled": False, "available": False, "feature": ORDER_RETURNS_FEATURE,
             "error": {"code": exc.code, "message": exc.message}}
        ), 200
    except MultiAgentClientError as exc:
        return jsonify(
            {"enabled": True, "available": False, "feature": ORDER_RETURNS_FEATURE,
             "error": {"code": exc.code, "message": exc.message}}
        ), 200
    except Exception:
        LOGGER.exception("Unexpected failure while checking Multi-Agent status")
        return jsonify(
            {"enabled": True, "available": False, "feature": ORDER_RETURNS_FEATURE,
             "error": {"code": "INTERNAL_ERROR",
                       "message": "The Multi-Agent status could not be checked."}}
        ), 200
    return jsonify(
        {"enabled": True, "available": health.get("status") == "ok",
         "feature": ORDER_RETURNS_FEATURE, "service": health.get("service"), "error": None}
    ), 200


@multi_agent_blueprint.post("/workflows")
def create_multi_agent_workflow():
    """Body: { question, return_id? , order_id? }  (one of return_id/order_id required)"""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _error("INVALID_ARGUMENT", "A JSON request body is required.", 400)

    question = body.get("question")
    if not isinstance(question, str) or not question.strip():
        return _error("INVALID_ARGUMENT", "question must be a non-empty string.", 400)
    question = question.strip()
    if len(question) > MAX_QUESTION_LENGTH:
        return _error("INVALID_ARGUMENT",
                      f"question must not exceed {MAX_QUESTION_LENGTH} characters.", 400)

    return_id = body.get("return_id")
    order_id = body.get("order_id")
    for label, value in (("return_id", return_id), ("order_id", order_id)):
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value <= 0):
            return _error("INVALID_ARGUMENT", f"{label} must be a positive integer.", 400)
    if return_id is None and order_id is None:
        return _error("INVALID_ARGUMENT", "return_id or order_id is required.", 400)

    try:
        evidence = _collect_evidence(return_id, order_id)
    except LookupError as exc:
        reason = str(exc)
        if reason == "return_not_found":
            return _error("RETURN_NOT_FOUND", "Return was not found.", 404)
        return _error("ORDER_NOT_FOUND", "Order was not found.", 404)
    except sqlite3.Error:
        LOGGER.warning("Order/return evidence could not be collected")
        return _error("ORDERS_DATABASE_UNAVAILABLE", "Order evidence is unavailable.", 503)

    try:
        OrderReturnsMultiAgentClient().health()
    except MultiAgentClientError as exc:
        return jsonify(exc.to_dict()), exc.status_code
    except Exception:
        LOGGER.exception("Unexpected failure while checking Multi-Agent health")
        return _error("INTERNAL_ERROR", "The Multi-Agent request could not be completed.", 500)

    payload = {
        "user_request": question,
        "feature": ORDER_RETURNS_FEATURE,
        "evidence": evidence,
    }
    fingerprint = evidence[0]["source"]["retrieved_at"]
    job_id = _new_job()
    threading.Thread(
        target=_run_workflow_job, args=(job_id, payload, fingerprint), daemon=True
    ).start()
    return jsonify(_get_job(job_id)), 202


@multi_agent_blueprint.get("/jobs/<job_id>")
def get_multi_agent_job(job_id):
    job = _get_job(job_id)
    if job is None:
        return _error("JOB_NOT_FOUND", "Workflow job was not found.", 404)
    return jsonify(job), 200


@multi_agent_blueprint.post("/workflows/<workflow_id>/review")
def review_multi_agent_workflow(workflow_id):
    """Body: { decision, reason }"""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _error("INVALID_ARGUMENT", "A JSON request body is required.", 400)

    decision = body.get("decision")
    if decision not in REVIEW_DECISIONS:
        return _error("INVALID_ARGUMENT",
                      "decision must be accept, partially_accept, or reject.", 400)

    reason = body.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return _error("INVALID_ARGUMENT", "reason must be a non-empty string.", 400)
    reason = reason.strip()
    if len(reason) > MAX_REASON_LENGTH:
        return _error("INVALID_ARGUMENT",
                      f"reason must not exceed {MAX_REASON_LENGTH} characters.", 400)

    reviewed_by = _reviewer_identity(getattr(g, "authenticated_user", None))
    if reviewed_by is None:
        return _error("AUTHENTICATION_REQUIRED", "An authenticated reviewer is required.", 401)

    review = {"decision": decision, "reason": reason, "reviewed_by": reviewed_by}
    try:
        result = OrderReturnsMultiAgentClient().submit_human_review(workflow_id, review)
    except MultiAgentClientError as exc:
        return jsonify(exc.to_dict()), exc.status_code
    except ValueError:
        return _error("INVALID_ARGUMENT", "workflow_id is invalid.", 400)
    except Exception:
        LOGGER.exception("Unexpected failure while submitting human review")
        return _error("INTERNAL_ERROR", "The human review could not be submitted.", 500)
    return jsonify(result), 200
