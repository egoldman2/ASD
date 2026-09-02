"""Allow-list validators for customer and staff support operations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


CATEGORY_VALUES = frozenset(
    {"order", "return", "payment", "product", "delivery", "account", "other", "unclassified"}
)
PRIORITY_VALUES = frozenset({"low", "medium", "high", "urgent", "unclassified"})
STATUS_VALUES = frozenset({"needs_triage", "open", "pending", "solved"})

MIN_SUBJECT_LENGTH = 5
MAX_SUBJECT_LENGTH = 160
MAX_MESSAGE_LENGTH = 2000
MAX_SEARCH_LENGTH = 160
MAX_ASSIGNED_TO_LENGTH = 100


class ValidationError(ValueError):
    """Safe validation failure that intentionally does not retain input data."""

    def __init__(self, message: str, field: str | None = None):
        self.message = message
        self.field = field
        super().__init__(message)


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError("A JSON object is required.")
    return value


def _text(
    value: Any,
    field: str,
    *,
    minimum: int = 1,
    maximum: int,
) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be text.", field)
    cleaned = value.strip()
    if not minimum <= len(cleaned) <= maximum:
        if minimum == 0:
            message = f"{field} must be {maximum} characters or fewer."
        else:
            message = f"{field} must be between {minimum} and {maximum} characters."
        raise ValidationError(message, field)
    return cleaned


def _enum(value: Any, field: str, choices: frozenset[str]) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field} is not valid.", field)
    cleaned = value.strip().casefold()
    if cleaned not in choices:
        raise ValidationError(f"{field} is not valid.", field)
    return cleaned


def validate_customer_create(data: Mapping[str, Any] | None) -> dict[str, str]:
    values = _mapping(data)
    # Deliberately return only the two customer-controlled fields. Any caller
    # supplied identity, role, management, or triage values are discarded.
    return {
        "subject": _text(
            values.get("subject"),
            "Subject",
            minimum=MIN_SUBJECT_LENGTH,
            maximum=MAX_SUBJECT_LENGTH,
        ),
        "message": _text(
            values.get("message"),
            "Message",
            minimum=1,
            maximum=MAX_MESSAGE_LENGTH,
        ),
    }


def validate_message(data: Mapping[str, Any] | None) -> dict[str, str]:
    values = _mapping(data)
    return {
        "message": _text(
            values.get("message"),
            "Message",
            minimum=1,
            maximum=MAX_MESSAGE_LENGTH,
        )
    }


def validate_admin_update(data: Mapping[str, Any] | None) -> dict[str, Any]:
    values = _mapping(data)
    result: dict[str, Any] = {}
    if "category" in values:
        result["category"] = _enum(values["category"], "Category", CATEGORY_VALUES)
    if "priority" in values:
        result["priority"] = _enum(values["priority"], "Priority", PRIORITY_VALUES)
    if "status" in values:
        result["status"] = _enum(values["status"], "Status", STATUS_VALUES)
    if "assigned_to" in values:
        assigned = values["assigned_to"]
        if assigned is None or assigned == "":
            result["assigned_to"] = None
        else:
            result["assigned_to"] = _text(
                assigned,
                "Assigned staff",
                minimum=2,
                maximum=MAX_ASSIGNED_TO_LENGTH,
            )

    if "apply_ai_suggestions" in values:
        suggestions = _mapping(values["apply_ai_suggestions"])
        result.update(
            apply_triage=True,
            triage_category=_enum(
                suggestions.get("category"), "Triage category", CATEGORY_VALUES
            ),
            triage_priority=_enum(
                suggestions.get("priority"), "Triage priority", PRIORITY_VALUES
            ),
        )
    if not result:
        raise ValidationError("At least one ticket update is required.")
    return result


def validate_admin_filters(data: Mapping[str, Any] | None) -> dict[str, str]:
    values = _mapping(data or {})
    result: dict[str, str] = {}
    search = values.get("search", "")
    if search is None:
        search = ""
    if not isinstance(search, str):
        raise ValidationError("Search must be text.", "search")
    search = search.strip()
    if len(search) > MAX_SEARCH_LENGTH:
        raise ValidationError("Search must be 160 characters or fewer.", "search")
    if search:
        result["search"] = search
    for field, choices in (
        ("category", CATEGORY_VALUES),
        ("priority", PRIORITY_VALUES),
        ("status", STATUS_VALUES),
    ):
        value = values.get(field, "")
        if value in (None, ""):
            continue
        result[field] = _enum(value, field.title(), choices)
    assigned = values.get("assigned_to", "")
    if assigned is None:
        assigned = ""
    if not isinstance(assigned, str):
        raise ValidationError("Assignee filter must be text.", "assigned_to")
    assigned = assigned.strip()
    if len(assigned) > MAX_ASSIGNED_TO_LENGTH:
        raise ValidationError(
            "Assignee filter must be 100 characters or fewer.", "assigned_to"
        )
    if assigned:
        result["assigned_to"] = assigned
    return result
