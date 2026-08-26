"""Read-only orchestration for Customer Support tickets."""

import logging
import sqlite3

from ..models import ticket_model


LOGGER = logging.getLogger(__name__)


def get_tickets():
    try:
        tickets = ticket_model.get_tickets()
    except sqlite3.Error:
        LOGGER.exception("Unable to retrieve support tickets")
        return {"error": "Unable to retrieve support tickets."}, 500

    status_counts = {"open": 0, "pending": 0, "solved": 0}
    for ticket in tickets:
        status_counts[ticket["status"]] += 1

    return {"count": len(tickets), "tickets": tickets, "status_counts": status_counts}, 200


def get_ticket(ticket_id):
    try:
        ticket = ticket_model.get_ticket(ticket_id)
    except sqlite3.Error:
        LOGGER.exception("Unable to retrieve support ticket %s", ticket_id)
        return {"error": "Unable to retrieve the support ticket."}, 500

    if ticket is None:
        return {"error": "Support ticket not found."}, 404

    return {"ticket": ticket}, 200
