"""Flask routes connecting Ryan's Inventory feature to the shared Multi-Agent Server.

Release 2 flow:
Frontend UI -> this blueprint -> Multi-Agent Server
(Planner -> Worker -> Reviewer) -> Human Review -> Frontend UI.

The backend collects the inventory evidence itself (the Multi-Agent Server
never reads the database) and always sends feature="inventory".

Workflows can take several minutes on slower machines, and long-held
connections from the container to the host can be dropped. The workflow
therefore runs as a background job: POST /workflows returns a job_id
immediately and the frontend polls GET /jobs/<job_id>. If the connection
to the server is lost mid-run, the job recovers the finished workflow from
the server's history by matching its unique evidence timestamp.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import socket

import requests
from flask import Blueprint, g, jsonify, request
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection

from multi_agent_client import (
    INVENTORY_FEATURE,
    InventoryMultiAgentClient,
    MultiAgentClientError,
    MultiAgentDisabledError,
)


LOGGER = logging.getLogger(__name__)

multi_agent_blueprint = Blueprint(
    "inventory_multi_agent",
    __name__,
    url_prefix="/api/inventory/multi-agent",
)

SERVICE_NAME = "inventory-backend"
DEFAULT_DATABASE_API_URL = "http://localhost:6001/api/database"
DATABASE_TIMEOUT_SECONDS = 5
MAX_QUESTION_LENGTH = 1000
MAX_REASON_LENGTH = 2000
MAX_LOW_STOCK_ITEMS = 15
REVIEW_DECISIONS = {"accept", "partially_accept", "reject"}

PRODUCT_FIELDS = (
    "id",
    "name",
    "category",
    "stock_quantity",
    "reorder_threshold",
    "reorder_quantity",
    "unit_cost",
    "supplier_id",
)
SUPPLIER_FIELDS = ("id", "name", "contact_name", "email", "phone")

# Background job settings
RECOVERY_POLL_SECONDS = 10
RECOVERY_LIMIT_SECONDS = 150 * 60
MAX_STORED_JOBS = 50

_JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _error(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _database_url() -> str:
    return os.getenv("PRODUCT_DATABASE_API_URL", DEFAULT_DATABASE_API_URL).rstrip("/")


def _fetch_list(path: str) -> list[Any]:
    response = requests.get(
        f"{_database_url()}{path}", timeout=DATABASE_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise ValueError(f"Expected a list from {path}.")
    return data


def _pick(record: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {key: record[key] for key in fields if key in record}


def _is_low_stock(product: dict[str, Any]) -> bool:
    stock = product.get("stock_quantity")
    threshold = product.get("reorder_threshold")
    return (
        isinstance(stock, (int, float))
        and isinstance(threshold, (int, float))
        and stock <= threshold
    )


def _source(endpoint: str, retrieved_at: str) -> dict[str, str]:
    return {
        "service": SERVICE_NAME,
        "endpoint": endpoint,
        "retrieved_at": retrieved_at,
    }


def _collect_evidence(product_id: int | None) -> list[dict[str, Any]]:
    """Build Multi-Agent evidence from the live inventory data."""

    retrieved_at = _utc_timestamp()
    products = [p for p in _fetch_list("/products") if isinstance(p, dict)]
    suppliers = {
        s["id"]: s
        for s in _fetch_list("/suppliers")
        if isinstance(s, dict) and isinstance(s.get("id"), int)
    }

    if product_id is not None:
        product = next((p for p in products if p.get("id") == product_id), None)
        if product is None:
            raise LookupError("product_not_found")
        # One evidence item only: the agents must cite every evidence ID, and
        # small models often skip one when given several. The supplier is
        # nested inside the product so its details are still available.
        data = _pick(product, PRODUCT_FIELDS)
        supplier = suppliers.get(product.get("supplier_id"))
        if supplier is not None:
            data["supplier"] = _pick(supplier, SUPPLIER_FIELDS)
        return [
            {
                "evidence_id": f"inventory-product-{product_id}",
                "source": _source(
                    f"/api/inventory/products/{product_id}", retrieved_at
                ),
                "data": data,
            }
        ]

    low_stock = []
    for product in products:
        if not _is_low_stock(product):
            continue
        item = _pick(product, PRODUCT_FIELDS)
        supplier = suppliers.get(product.get("supplier_id"))
        if supplier is not None:
            item["supplier"] = _pick(supplier, SUPPLIER_FIELDS)
        low_stock.append(item)
        if len(low_stock) >= MAX_LOW_STOCK_ITEMS:
            break
    if not low_stock:
        raise LookupError("no_low_stock")

    return [
        {
            "evidence_id": "inventory-low-stock-snapshot",
            "source": _source(
                "/api/inventory/products?filter=low_stock", retrieved_at
            ),
            "data": {"low_stock_products": low_stock},
        }
    ]


def _reviewer_identity(user: Any) -> str | None:
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

def _new_job() -> str:
    job_id = uuid.uuid4().hex
    with _JOBS_LOCK:
        if len(_JOBS) >= MAX_STORED_JOBS:
            finished = [
                key for key, job in _JOBS.items()
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


def _update_job(job_id: str, **changes: Any) -> None:
    with _JOBS_LOCK:
        if job_id in _JOBS:
            _JOBS[job_id].update(changes)


def _get_job(job_id: str) -> dict[str, Any] | None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job is not None else None


def _find_recovered_workflow(
    client: InventoryMultiAgentClient, fingerprint: str
) -> dict[str, Any] | None:
    """Find our workflow in the server history by its unique evidence timestamp."""

    for workflow in reversed(client.list_workflows()["workflows"]):
        evidence = (workflow.get("request") or {}).get("evidence") or []
        first = evidence[0] if evidence and isinstance(evidence[0], dict) else {}
        if (first.get("source") or {}).get("retrieved_at") == fingerprint:
            return workflow
    return None


class _KeepAliveAdapter(HTTPAdapter):
    """Send TCP keep-alive probes so a long idle request is not dropped."""

    def init_poolmanager(self, *args: Any, **kwargs: Any) -> None:
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


def _long_request_client() -> InventoryMultiAgentClient:
    session = requests.Session()
    session.mount("http://", _KeepAliveAdapter())
    session.mount("https://", _KeepAliveAdapter())
    return InventoryMultiAgentClient(http_request=session.request)


def _run_workflow_job(job_id: str, payload: dict[str, Any], fingerprint: str) -> None:
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

    # The connection dropped, but the server keeps working. Check its history
    # until the finished workflow appears or the recovery limit is reached.
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
    """UI-friendly availability snapshot. Never fatal (always 200)."""

    try:
        health = InventoryMultiAgentClient().health()
    except MultiAgentDisabledError as exc:
        return jsonify(
            {
                "enabled": False,
                "available": False,
                "feature": INVENTORY_FEATURE,
                "error": {"code": exc.code, "message": exc.message},
            }
        ), 200
    except MultiAgentClientError as exc:
        return jsonify(
            {
                "enabled": True,
                "available": False,
                "feature": INVENTORY_FEATURE,
                "error": {"code": exc.code, "message": exc.message},
            }
        ), 200
    except Exception:
        LOGGER.exception("Unexpected failure while checking Multi-Agent status")
        return jsonify(
            {
                "enabled": True,
                "available": False,
                "feature": INVENTORY_FEATURE,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "The Multi-Agent status could not be checked.",
                },
            }
        ), 200

    return jsonify(
        {
            "enabled": True,
            "available": health.get("status") == "ok",
            "feature": INVENTORY_FEATURE,
            "service": health.get("service"),
            "error": None,
        }
    ), 200


@multi_agent_blueprint.post("/workflows")
def create_multi_agent_workflow():
    """POST /api/inventory/multi-agent/workflows  Body: { question, product_id? }"""

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _error("INVALID_ARGUMENT", "A JSON request body is required.", 400)

    question = body.get("question")
    if not isinstance(question, str) or not question.strip():
        return _error("INVALID_ARGUMENT", "question must be a non-empty string.", 400)
    question = question.strip()
    if len(question) > MAX_QUESTION_LENGTH:
        return _error(
            "INVALID_ARGUMENT",
            f"question must not exceed {MAX_QUESTION_LENGTH} characters.",
            400,
        )

    product_id = body.get("product_id")
    if product_id is not None and (
        isinstance(product_id, bool)
        or not isinstance(product_id, int)
        or product_id <= 0
    ):
        return _error("INVALID_ARGUMENT", "product_id must be a positive integer.", 400)

    try:
        evidence = _collect_evidence(product_id)
    except LookupError as exc:
        if str(exc) == "product_not_found":
            return _error("PRODUCT_NOT_FOUND", "Product was not found.", 404)
        return _error(
            "NO_LOW_STOCK_PRODUCTS",
            "No products are currently at or below their reorder threshold.",
            409,
        )
    except (requests.RequestException, ValueError):
        LOGGER.warning("Inventory evidence could not be collected")
        return _error(
            "INVENTORY_DATABASE_UNAVAILABLE",
            "Inventory evidence is unavailable.",
            503,
        )

    # Fail fast if the server is disabled or down, before starting a job.
    try:
        InventoryMultiAgentClient().health()
    except MultiAgentClientError as exc:
        return jsonify(exc.to_dict()), exc.status_code
    except Exception:
        LOGGER.exception("Unexpected failure while checking Multi-Agent health")
        return _error(
            "INTERNAL_ERROR", "The Multi-Agent request could not be completed.", 500
        )

    payload = {
        "user_request": question,
        "feature": INVENTORY_FEATURE,
        "evidence": evidence,
    }
    fingerprint = evidence[0]["source"]["retrieved_at"]
    job_id = _new_job()
    threading.Thread(
        target=_run_workflow_job,
        args=(job_id, payload, fingerprint),
        daemon=True,
    ).start()
    return jsonify(_get_job(job_id)), 202


@multi_agent_blueprint.get("/jobs/<job_id>")
def get_multi_agent_job(job_id: str):
    """GET /api/inventory/multi-agent/jobs/<job_id>  Poll a running workflow."""

    job = _get_job(job_id)
    if job is None:
        return _error("JOB_NOT_FOUND", "Workflow job was not found.", 404)
    return jsonify(job), 200


@multi_agent_blueprint.post("/workflows/<workflow_id>/review")
def review_multi_agent_workflow(workflow_id: str):
    """POST /api/inventory/multi-agent/workflows/<id>/review  Body: { decision, reason }"""

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _error("INVALID_ARGUMENT", "A JSON request body is required.", 400)

    decision = body.get("decision")
    if decision not in REVIEW_DECISIONS:
        return _error(
            "INVALID_ARGUMENT",
            "decision must be accept, partially_accept, or reject.",
            400,
        )

    reason = body.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return _error("INVALID_ARGUMENT", "reason must be a non-empty string.", 400)
    reason = reason.strip()
    if len(reason) > MAX_REASON_LENGTH:
        return _error(
            "INVALID_ARGUMENT",
            f"reason must not exceed {MAX_REASON_LENGTH} characters.",
            400,
        )

    reviewed_by = _reviewer_identity(getattr(g, "authenticated_user", None))
    if reviewed_by is None:
        return _error(
            "AUTHENTICATION_REQUIRED", "An authenticated reviewer is required.", 401
        )

    review = {"decision": decision, "reason": reason, "reviewed_by": reviewed_by}
    try:
        result = InventoryMultiAgentClient().submit_human_review(workflow_id, review)
    except MultiAgentClientError as exc:
        return jsonify(exc.to_dict()), exc.status_code
    except ValueError:
        return _error("INVALID_ARGUMENT", "workflow_id is invalid.", 400)
    except Exception:
        LOGGER.exception("Unexpected failure while submitting human review")
        return _error(
            "INTERNAL_ERROR", "The human review could not be submitted.", 500
        )
    return jsonify(result), 200