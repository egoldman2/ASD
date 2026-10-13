"""Flask routes connecting Ryan's Inventory feature to the shared Multi-Agent Server.

Release 2 flow:
Frontend UI -> this blueprint -> Multi-Agent Server
(Planner -> Worker -> Reviewer) -> Human Review -> Frontend UI.

The backend collects the inventory evidence itself (the Multi-Agent Server
never reads the database) and always sends feature="inventory".
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import requests
from flask import Blueprint, g, jsonify, request

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
        evidence = [
            {
                "evidence_id": f"inventory-product-{product_id}",
                "source": _source(
                    f"/api/inventory/products/{product_id}", retrieved_at
                ),
                "data": _pick(product, PRODUCT_FIELDS),
            }
        ]
        supplier = suppliers.get(product.get("supplier_id"))
        if supplier is not None:
            evidence.append(
                {
                    "evidence_id": f"inventory-supplier-{supplier['id']}",
                    "source": _source(
                        f"/api/inventory/suppliers/{supplier['id']}", retrieved_at
                    ),
                    "data": _pick(supplier, SUPPLIER_FIELDS),
                }
            )
        return evidence

    low_stock = [
        _pick(p, PRODUCT_FIELDS) for p in products if _is_low_stock(p)
    ][:MAX_LOW_STOCK_ITEMS]
    if not low_stock:
        raise LookupError("no_low_stock")

    evidence = [
        {
            "evidence_id": "inventory-low-stock-snapshot",
            "source": _source(
                "/api/inventory/products?filter=low_stock", retrieved_at
            ),
            "data": {"low_stock_products": low_stock},
        }
    ]
    supplier_ids = sorted(
        {p.get("supplier_id") for p in low_stock if p.get("supplier_id") in suppliers}
    )
    if supplier_ids:
        evidence.append(
            {
                "evidence_id": "inventory-suppliers-snapshot",
                "source": _source("/api/inventory/suppliers", retrieved_at),
                "data": {
                    "suppliers": [
                        _pick(suppliers[supplier_id], SUPPLIER_FIELDS)
                        for supplier_id in supplier_ids
                    ]
                },
            }
        )
    return evidence


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

    payload = {
        "user_request": question,
        "feature": INVENTORY_FEATURE,
        "evidence": evidence,
    }
    try:
        result = InventoryMultiAgentClient().create_workflow(payload)
    except MultiAgentClientError as exc:
        return jsonify(exc.to_dict()), exc.status_code
    except Exception:
        LOGGER.exception("Unexpected failure while creating Multi-Agent workflow")
        return _error(
            "INTERNAL_ERROR", "The Multi-Agent request could not be completed.", 500
        )
    return jsonify(result), 201


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