"""Validated request contracts for the shared multi-agent workflow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import math
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import urlsplit


MAX_USER_REQUEST_CHARS = 4_000
MAX_EVIDENCE_ITEMS = 20
MAX_EVIDENCE_ID_CHARS = 128
MAX_SERVICE_CHARS = 128
MAX_ENDPOINT_CHARS = 2_048
MAX_JSON_DEPTH = 10
MAX_JSON_NODES = 10_000
MAX_JSON_STRING_CHARS = 10_000
MAX_REVIEW_REASON_CHARS = 2_000
MAX_REVIEWER_CHARS = 128


class Feature(str, Enum):
    """Release 2 feature identifiers supported by the shared server."""

    PRODUCT_CATALOGUE = "product_catalogue"
    INVENTORY = "inventory"
    CUSTOMER_LOYALTY = "customer_loyalty"
    ORDER_RETURNS = "order_returns"
    CUSTOMER_SUPPORT = "customer_support"


class HumanReviewDecision(str, Enum):
    """Decisions a human reviewer can submit for a completed workflow."""

    ACCEPT = "accept"
    PARTIALLY_ACCEPT = "partially_accept"
    REJECT = "reject"


class ContractValidationError(ValueError):
    """A client-safe validation error with a stable machine-readable code."""

    def __init__(self, code: str, field: str, message: str) -> None:
        self.code = code
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")

    def to_dict(self) -> dict[str, dict[str, str]]:
        """Return the consistent API error envelope used by the Flask layer."""

        return {
            "error": {
                "code": self.code,
                "field": self.field,
                "message": self.message,
            }
        }


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractValidationError(
            "invalid_type", field, "must be a JSON object."
        )
    return value


def _required_text(
    value: Any,
    field: str,
    *,
    max_chars: int,
) -> str:
    if not isinstance(value, str):
        raise ContractValidationError(
            "invalid_type", field, "must be a string."
        )
    cleaned = value.strip()
    if not cleaned:
        raise ContractValidationError(
            "required_field", field, "must not be empty."
        )
    if len(cleaned) > max_chars:
        raise ContractValidationError(
            "value_too_long",
            field,
            f"must not exceed {max_chars} characters.",
        )
    return cleaned


def _enum_value(value: Any, field: str, enum_type: type[Enum]) -> Enum:
    if not isinstance(value, str):
        raise ContractValidationError(
            "invalid_type", field, "must be a string."
        )
    try:
        return enum_type(value.strip())
    except ValueError as exc:
        allowed = ", ".join(member.value for member in enum_type)
        raise ContractValidationError(
            "invalid_choice",
            field,
            f"must be one of: {allowed}.",
        ) from exc


def _iso_timestamp(value: Any, field: str) -> str:
    text = _required_text(value, field, max_chars=64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractValidationError(
            "invalid_timestamp",
            field,
            "must be an ISO 8601 timestamp with a timezone.",
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractValidationError(
            "invalid_timestamp",
            field,
            "must be an ISO 8601 timestamp with a timezone.",
        )
    return text


def _source_endpoint(value: Any, field: str) -> str:
    endpoint = _required_text(value, field, max_chars=MAX_ENDPOINT_CHARS)
    if endpoint.startswith("/") and not endpoint.startswith("//"):
        return endpoint

    try:
        parsed = urlsplit(endpoint)
        parsed_port = parsed.port
    except ValueError as exc:
        raise ContractValidationError(
            "invalid_endpoint",
            field,
            "must be a relative API path or an HTTP(S) URL.",
        ) from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or (parsed_port is not None and not 1 <= parsed_port <= 65_535)
        or parsed.fragment
    ):
        raise ContractValidationError(
            "invalid_endpoint",
            field,
            "must be a relative API path or an HTTP(S) URL without "
            "credentials or a fragment.",
        )
    return endpoint


def _freeze_json(value: Any, field: str) -> Any:
    """Validate JSON-compatible evidence and return an immutable copy."""

    node_count = 0

    def freeze(node: Any, path: str, depth: int) -> Any:
        nonlocal node_count
        node_count += 1
        if node_count > MAX_JSON_NODES:
            raise ContractValidationError(
                "json_too_large",
                field,
                f"must not contain more than {MAX_JSON_NODES} values.",
            )
        if depth > MAX_JSON_DEPTH:
            raise ContractValidationError(
                "json_too_deep",
                path,
                f"must not exceed {MAX_JSON_DEPTH} nested levels.",
            )

        if node is None or isinstance(node, bool):
            return node
        if isinstance(node, str):
            if len(node) > MAX_JSON_STRING_CHARS:
                raise ContractValidationError(
                    "value_too_long",
                    path,
                    f"must not exceed {MAX_JSON_STRING_CHARS} characters.",
                )
            return node
        if isinstance(node, int):
            return node
        if isinstance(node, float):
            if not math.isfinite(node):
                raise ContractValidationError(
                    "invalid_json_number", path, "must be a finite number."
                )
            return node
        if isinstance(node, Mapping):
            frozen: dict[str, Any] = {}
            for key, child in node.items():
                if not isinstance(key, str):
                    raise ContractValidationError(
                        "invalid_json_key", path, "must use string object keys."
                    )
                child_path = f"{path}.{key}" if key else path
                frozen[key] = freeze(child, child_path, depth + 1)
            return MappingProxyType(frozen)
        if isinstance(node, (list, tuple)):
            return tuple(
                freeze(child, f"{path}[{index}]", depth + 1)
                for index, child in enumerate(node)
            )
        raise ContractValidationError(
            "invalid_json_type",
            path,
            "must contain only JSON-compatible values.",
        )

    return freeze(value, field, 0)


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(child) for child in value]
    return value


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    """Provenance describing which backend supplied an evidence item."""

    service: str
    endpoint: str
    retrieved_at: str

    @classmethod
    def from_dict(cls, payload: Any, field: str = "source") -> "EvidenceSource":
        data = _mapping(payload, field)
        return cls(
            service=_required_text(
                data.get("service"),
                f"{field}.service",
                max_chars=MAX_SERVICE_CHARS,
            ),
            endpoint=_source_endpoint(
                data.get("endpoint"), f"{field}.endpoint"
            ),
            retrieved_at=_iso_timestamp(
                data.get("retrieved_at"), f"{field}.retrieved_at"
            ),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "service": self.service,
            "endpoint": self.endpoint,
            "retrieved_at": self.retrieved_at,
        }


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """One immutable, feature-neutral unit of backend-supplied evidence."""

    evidence_id: str
    source: EvidenceSource
    data: Mapping[str, Any]

    @classmethod
    def from_dict(cls, payload: Any, field: str = "evidence") -> "EvidenceItem":
        item = _mapping(payload, field)
        raw_data = _mapping(item.get("data"), f"{field}.data")
        if not raw_data:
            raise ContractValidationError(
                "required_field", f"{field}.data", "must not be empty."
            )
        return cls(
            evidence_id=_required_text(
                item.get("evidence_id"),
                f"{field}.evidence_id",
                max_chars=MAX_EVIDENCE_ID_CHARS,
            ),
            source=EvidenceSource.from_dict(
                item.get("source"), f"{field}.source"
            ),
            data=_freeze_json(raw_data, f"{field}.data"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source": self.source.to_dict(),
            "data": _thaw_json(self.data),
        }


@dataclass(frozen=True, slots=True)
class WorkflowRequest:
    """Validated input used to start a shared multi-agent workflow."""

    user_request: str
    feature: Feature
    evidence: tuple[EvidenceItem, ...]

    @classmethod
    def from_dict(cls, payload: Any) -> "WorkflowRequest":
        data = _mapping(payload, "request")
        raw_evidence = data.get("evidence")
        if not isinstance(raw_evidence, list):
            raise ContractValidationError(
                "invalid_type", "evidence", "must be a JSON array."
            )
        if not raw_evidence:
            raise ContractValidationError(
                "required_field", "evidence", "must not be empty."
            )
        if len(raw_evidence) > MAX_EVIDENCE_ITEMS:
            raise ContractValidationError(
                "too_many_items",
                "evidence",
                f"must not contain more than {MAX_EVIDENCE_ITEMS} items.",
            )

        evidence = tuple(
            EvidenceItem.from_dict(item, f"evidence[{index}]")
            for index, item in enumerate(raw_evidence)
        )
        evidence_ids = [item.evidence_id for item in evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ContractValidationError(
                "duplicate_evidence_id",
                "evidence",
                "must use a unique evidence_id for every item.",
            )

        return cls(
            user_request=_required_text(
                data.get("user_request"),
                "user_request",
                max_chars=MAX_USER_REQUEST_CHARS,
            ),
            feature=_enum_value(data.get("feature"), "feature", Feature),
            evidence=evidence,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_request": self.user_request,
            "feature": self.feature.value,
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True, slots=True)
class HumanReviewRequest:
    """Validated human decision submitted for an existing workflow."""

    decision: HumanReviewDecision
    reason: str
    reviewed_by: str

    @classmethod
    def from_dict(cls, payload: Any) -> "HumanReviewRequest":
        data = _mapping(payload, "human_review")
        return cls(
            decision=_enum_value(
                data.get("decision"), "decision", HumanReviewDecision
            ),
            reason=_required_text(
                data.get("reason"),
                "reason",
                max_chars=MAX_REVIEW_REASON_CHARS,
            ),
            reviewed_by=_required_text(
                data.get("reviewed_by"),
                "reviewed_by",
                max_chars=MAX_REVIEWER_CHARS,
            ),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "decision": self.decision.value,
            "reason": self.reason,
            "reviewed_by": self.reviewed_by,
        }
