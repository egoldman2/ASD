"""Orchestration and validation for Customer Support tickets."""

from datetime import datetime, timezone
from email.utils import parseaddr
import logging
import sqlite3

from ..models import ticket_model


LOGGER = logging.getLogger(__name__)

FILTER_ENUMS = {
    "status": {"open", "pending", "solved"},
    "priority": {"low", "medium", "high", "urgent"},
    "category": {
        "order", "return", "payment", "product", "delivery", "account", "other"
    },
}
MESSAGE_ROLES = {"customer", "staff"}
MAX_MESSAGE_LENGTH = 2000


def _utc_timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _valid_email(value):
    parsed_name, parsed_address = parseaddr(value)
    return (
        not parsed_name
        and parsed_address == value
        and "@" in parsed_address
        and "." in parsed_address.rsplit("@", 1)[-1]
    )


def validate_ticket(values):
    cleaned = {
        field: str(values.get(field, "")).strip()
        for field in (
            "customer_name", "customer_email", "subject", "message",
            "category", "priority",
        )
    }

    length_rules = {
        "customer_name": (2, 100, "Name must be between 2 and 100 characters."),
        "subject": (5, 160, "Subject must be between 5 and 160 characters."),
        "message": (
            10,
            MAX_MESSAGE_LENGTH,
            "Message must be between 10 and 2000 characters.",
        ),
    }
    for field, (minimum, maximum, error) in length_rules.items():
        if not minimum <= len(cleaned[field]) <= maximum:
            return None, error

    email = cleaned["customer_email"]
    if len(email) > 254 or not _valid_email(email):
        return None, "Enter a valid email address."

    for field in ("category", "priority"):
        cleaned[field] = cleaned[field].casefold()
        if cleaned[field] not in FILTER_ENUMS[field]:
            return None, f"Select a valid {field}."

    return cleaned, None


def create_ticket(values):
    ticket_values, validation_error = validate_ticket(values)
    if validation_error:
        return {"error": validation_error}, 400

    try:
        ticket = ticket_model.create_ticket(ticket_values, _utc_timestamp())
    except sqlite3.Error:
        LOGGER.exception("Unable to create support ticket")
        return {"error": "Unable to create the support ticket."}, 500

    return {"ticket": ticket}, 201


def validate_filters(arguments):
    filters = {}

    search = arguments.get("search", "").strip()
    if len(search) > 160:
        return None, "Search must be 160 characters or fewer."
    if search:
        filters["search"] = search

    for field, allowed_values in FILTER_ENUMS.items():
        value = arguments.get(field, "").strip().casefold()
        if not value:
            continue
        if value not in allowed_values:
            return None, f"Invalid {field} filter."
        filters[field] = value

    assigned_to = arguments.get("assigned_to", "").strip()
    if len(assigned_to) > 100:
        return None, "Assignee filter must be 100 characters or fewer."
    if assigned_to:
        filters["assigned_to"] = assigned_to

    return filters, None


def get_tickets(arguments=None):
    filters, validation_error = validate_filters(arguments or {})
    if validation_error:
        return {"error": validation_error}, 400

    try:
        tickets = ticket_model.get_tickets(filters)
    except sqlite3.Error:
        LOGGER.exception("Unable to retrieve support tickets")
        return {"error": "Unable to retrieve support tickets."}, 500

    status_counts = {"open": 0, "pending": 0, "solved": 0}
    for ticket in tickets:
        status_counts[ticket["status"]] += 1

    return {
        "count": len(tickets),
        "tickets": tickets,
        "status_counts": status_counts,
        "filters": filters,
    }, 200


def get_ticket(ticket_id):
    try:
        ticket = ticket_model.get_ticket(ticket_id)
    except sqlite3.Error:
        LOGGER.exception("Unable to retrieve support ticket %s", ticket_id)
        return {"error": "Unable to retrieve the support ticket."}, 500

    if ticket is None:
        return {"error": "Support ticket not found."}, 404

    return {"ticket": ticket}, 200


def get_customer_ticket(ticket_id, customer_email):
    """Return a customer-safe conversation after matching the ticket email."""
    email = (customer_email or "").strip().casefold()
    if not email:
        return {"error": "Enter the email address used for this ticket."}, 400

    payload, status_code = get_ticket(ticket_id)
    if status_code != 200:
        return payload, status_code

    ticket = payload["ticket"]
    if ticket["customer_email"].casefold() != email:
        return {"error": "Ticket details could not be verified."}, 404

    customer_ticket = {
        key: ticket[key]
        for key in ("id", "subject", "created_at", "updated_at", "messages")
    }
    return {"ticket": customer_ticket, "customer_email": email}, 200


def add_ticket_message(ticket_id, values, fixed_sender_role=None):
    sender_role = fixed_sender_role or str(
        values.get("sender_role", "")
    ).strip().casefold()
    if sender_role not in MESSAGE_ROLES:
        return {"error": "Sender role must be customer or staff."}, 400

    message = str(values.get("message", "")).strip()
    if not message:
        return {"error": "Message is required."}, 400
    if len(message) > MAX_MESSAGE_LENGTH:
        return {"error": "Message must be 2000 characters or fewer."}, 400

    created_at = _utc_timestamp()
    try:
        created_message = ticket_model.create_ticket_message(
            ticket_id, sender_role, message, created_at
        )
    except sqlite3.Error:
        LOGGER.exception("Unable to add a message to support ticket %s", ticket_id)
        return {"error": "Unable to add the ticket message."}, 500

    if created_message is None:
        return {"error": "Support ticket not found."}, 404

    return {"message": created_message}, 201


def add_customer_ticket_message(ticket_id, values):
    customer_payload, status_code = get_customer_ticket(
        ticket_id, values.get("customer_email")
    )
    if status_code != 200:
        return customer_payload, status_code

    return add_ticket_message(ticket_id, values, fixed_sender_role="customer")
