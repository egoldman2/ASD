"""Read-only orchestration for Customer Support tickets."""

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
