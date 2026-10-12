"""Product Catalogue evidence orchestration for the shared Multi-Agent server."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Callable

from ..models import product_model
from ..models.database import DatabaseAPIError
from ..services.multi_agent_client import (
    CHUFENG_FEATURE,
    ChufengMultiAgentClient,
    MultiAgentClientError,
    MultiAgentDisabledError,
)


LOGGER = logging.getLogger(__name__)
MAX_QUESTION_LENGTH = 1_000
MAX_REASON_LENGTH = 2_000
REVIEW_DECISIONS = {"accept", "partially_accept", "reject"}


def _create_client() -> ChufengMultiAgentClient:
    return ChufengMultiAgentClient()


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _error(code: str, message: str, status: int) -> tuple[dict[str, Any], int]:
    return {"error": {"code": code, "message": message}}, status


def _safe_internal_error() -> tuple[dict[str, Any], int]:
    return _error(
        "INTERNAL_ERROR",
        "The Product Catalogue Multi-Agent request could not be completed.",
        500,
    )


def _execute(
    operation: Callable[[ChufengMultiAgentClient], dict[str, Any]],
    *,
    success_status: int = 200,
) -> tuple[dict[str, Any], int]:
    try:
        return operation(_create_client()), success_status
    except MultiAgentClientError as exc:
        return exc.to_dict(), exc.status_code
    except Exception:
        LOGGER.exception("Unexpected Chufeng Multi-Agent controller failure")
        return _safe_internal_error()


def get_status() -> tuple[dict[str, Any], int]:
    """Return a non-fatal availability snapshot for the frontend."""

    try:
        client = _create_client()
        health = client.health()
    except MultiAgentDisabledError as exc:
        return {
            "enabled": False,
            "available": False,
            "feature": CHUFENG_FEATURE,
            "error": {"code": exc.code, "message": exc.message},
        }, 200
    except MultiAgentClientError as exc:
        return {
            "enabled": True,
            "available": False,
            "feature": CHUFENG_FEATURE,
            "error": {"code": exc.code, "message": exc.message},
        }, 200
    except Exception:
        LOGGER.exception("Unexpected failure while checking Multi-Agent status")
        return {
            "enabled": True,
            "available": False,
            "feature": CHUFENG_FEATURE,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "The Multi-Agent status could not be checked.",
            },
        }, 200

    return {
        "enabled": True,
        "available": health.get("status") == "ok",
        "feature": CHUFENG_FEATURE,
        "service": health.get("service"),
        "error": None,
    }, 200


def _validated_creation(data: Any) -> tuple[dict[str, Any] | None, Any | None]:
    if not isinstance(data, dict):
        return None, _error(
            "INVALID_ARGUMENT", "A JSON request body is required.", 400
        )
    if set(data) - {"question", "product_id"}:
        return None, _error(
            "INVALID_ARGUMENT",
            "Only question and optional product_id fields are accepted.",
            400,
        )

    question = data.get("question")
    if not isinstance(question, str) or not question.strip():
        return None, _error(
            "INVALID_ARGUMENT", "question must be a non-empty string.", 400
        )
    question = question.strip()
    if len(question) > MAX_QUESTION_LENGTH:
        return None, _error(
            "INVALID_ARGUMENT",
            f"question must not exceed {MAX_QUESTION_LENGTH} characters.",
            400,
        )

    product_id = data.get("product_id")
    if product_id is not None and (
        isinstance(product_id, bool)
        or not isinstance(product_id, int)
        or product_id <= 0
    ):
        return None, _error(
            "INVALID_ARGUMENT", "product_id must be a positive integer.", 400
        )
    return {"question": question, "product_id": product_id}, None


def _database_evidence(product_id: int | None) -> dict[str, Any]:
    retrieved_at = _utc_timestamp()
    if product_id is not None:
        product = product_model.get_product(product_id)
        if product is None:
            raise LookupError("product_not_found")
        return {
            "evidence_id": f"catalogue-product-{product_id}",
            "source": {
                "service": "product-catalogue-backend",
                "endpoint": f"/api/database/products/{product_id}",
                "retrieved_at": retrieved_at,
            },
            "data": product,
        }

    products = product_model.get_products()
    if not isinstance(products, list) or not products:
        raise LookupError("catalogue_empty")
    return {
        "evidence_id": "catalogue-products-snapshot",
        "source": {
            "service": "product-catalogue-backend",
            "endpoint": "/api/database/products",
            "retrieved_at": retrieved_at,
        },
        "data": {"products": products},
    }


def create_workflow(data: Any) -> tuple[dict[str, Any], int]:
    validated, failure = _validated_creation(data)
    if failure is not None:
        return failure
    assert validated is not None

    try:
        evidence = _database_evidence(validated["product_id"])
    except LookupError as exc:
        if str(exc) == "product_not_found":
            return _error("PRODUCT_NOT_FOUND", "Product was not found.", 404)
        return _error(
            "CATALOGUE_EMPTY", "No catalogue products are available.", 409
        )
    except DatabaseAPIError as exc:
        LOGGER.warning("Product database evidence request failed")
        status = 503 if exc.status_code == 503 else 502
        return _error(
            "PRODUCT_DATABASE_UNAVAILABLE",
            "Product catalogue evidence is unavailable.",
            status,
        )
    except Exception:
        LOGGER.exception("Unexpected product evidence collection failure")
        return _safe_internal_error()

    request_payload = {
        "user_request": validated["question"],
        "feature": CHUFENG_FEATURE,
        "evidence": [evidence],
    }
    return _execute(
        lambda client: client.create_workflow(request_payload),
        success_status=201,
    )


def list_workflows() -> tuple[dict[str, Any], int]:
    return _execute(lambda client: client.list_workflows())


def latest_workflow() -> tuple[dict[str, Any], int]:
    return _execute(lambda client: client.latest_workflow())


def get_workflow(workflow_id: str) -> tuple[dict[str, Any], int]:
    return _execute(lambda client: client.get_workflow(workflow_id))


def _validated_review(
    data: Any,
    authenticated_user: Any,
) -> tuple[dict[str, str] | None, Any | None]:
    if not isinstance(data, dict):
        return None, _error(
            "INVALID_ARGUMENT", "A JSON request body is required.", 400
        )
    if set(data) - {"decision", "reason"}:
        return None, _error(
            "INVALID_ARGUMENT",
            "Only decision and reason fields are accepted.",
            400,
        )
    decision = data.get("decision")
    if decision not in REVIEW_DECISIONS:
        return None, _error(
            "INVALID_ARGUMENT",
            "decision must be accept, partially_accept, or reject.",
            400,
        )
    reason = data.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return None, _error(
            "INVALID_ARGUMENT", "reason must be a non-empty string.", 400
        )
    reason = reason.strip()
    if len(reason) > MAX_REASON_LENGTH:
        return None, _error(
            "INVALID_ARGUMENT",
            f"reason must not exceed {MAX_REASON_LENGTH} characters.",
            400,
        )
    if not isinstance(authenticated_user, dict):
        return None, _error(
            "AUTHENTICATION_REQUIRED", "An authenticated reviewer is required.", 401
        )
    email = authenticated_user.get("email")
    user_id = authenticated_user.get("id")
    if isinstance(email, str) and 0 < len(email.strip()) <= 128:
        reviewed_by = email.strip()
    elif isinstance(user_id, int) and not isinstance(user_id, bool):
        reviewed_by = f"user:{user_id}"
    else:
        return None, _error(
            "AUTHENTICATION_REQUIRED", "An authenticated reviewer is required.", 401
        )
    return {
        "decision": decision,
        "reason": reason,
        "reviewed_by": reviewed_by,
    }, None


def submit_human_review(
    workflow_id: str,
    data: Any,
    authenticated_user: Any,
) -> tuple[dict[str, Any], int]:
    review, failure = _validated_review(data, authenticated_user)
    if failure is not None:
        return failure
    assert review is not None
    return _execute(
        lambda client: client.submit_human_review(workflow_id, review)
    )
