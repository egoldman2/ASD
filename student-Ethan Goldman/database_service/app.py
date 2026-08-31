"""Flask HTTP API for the independent Customer Support database service."""

from contextlib import closing
from datetime import datetime, timezone
import logging
import os
import sqlite3
import sys
from pathlib import Path

from flask import Flask, jsonify, request

try:
    from . import database
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import database

LOGGER = logging.getLogger(__name__)
CATEGORIES = {"order", "return", "payment", "product", "delivery", "account", "other", "unclassified"}
PRIORITIES = {"low", "medium", "high", "urgent", "unclassified"}
STATUSES = {"needs_triage", "open", "pending", "solved"}
SENDER_ROLES = {"customer", "staff"}


class ApiError(Exception):
    def __init__(self, status_code, code, message):
        super().__init__(message); self.status_code = status_code; self.code = code; self.message = message


def _error(status, code, message):
    return jsonify({"error": {"code": code, "message": message}}), status


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _json():
    if not request.is_json or not isinstance((payload := request.get_json(silent=True)), dict):
        raise ApiError(400, "invalid_json", "Request body must be a JSON object.")
    return payload


def _string(payload, field, minimum, maximum):
    value = payload.get(field)
    if not isinstance(value, str):
        raise ApiError(400, "invalid_field", f"{field} must be a string.")
    value = value.strip()
    if not minimum <= len(value) <= maximum:
        raise ApiError(400, "invalid_field", f"{field} must contain between {minimum} and {maximum} characters.")
    return value


def _owner_id(payload):
    value = payload.get("customer_user_id")
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ApiError(400, "invalid_field", "customer_user_id must be a non-empty string or integer.")
    value = str(value).strip()
    if not 1 <= len(value) <= 128:
        raise ApiError(400, "invalid_field", "customer_user_id must contain between 1 and 128 characters.")
    return value


def _email(payload):
    value = _string(payload, "customer_email_snapshot", 3, 254)
    if "@" not in value or value.startswith("@") or value.endswith("@"):
        raise ApiError(400, "invalid_field", "customer_email_snapshot must be a valid email-like value.")
    return value


def _enum(payload, field, allowed, required=False):
    if field not in payload and not required:
        return None
    value = payload.get(field)
    if not isinstance(value, str) or value not in allowed:
        raise ApiError(400, "invalid_field", f"{field} has an unsupported value.")
    return value


def _assigned(payload):
    if payload.get("assigned_to") is None:
        return None
    value = payload["assigned_to"]
    if not isinstance(value, str):
        raise ApiError(400, "invalid_field", "assigned_to must be a string or null.")
    value = value.strip()
    if value.casefold() == "unassigned":
        return None
    if not 2 <= len(value) <= 100:
        raise ApiError(400, "invalid_field", "assigned_to must contain between 2 and 100 characters.")
    return value


def _filters():
    filters = {field: None for field in ("search", "category", "priority", "status", "assigned_to", "owner_user_id")}
    if request.args.get("search") is not None:
        filters["search"] = request.args["search"].strip() or None
        if filters["search"] and len(filters["search"]) > 200:
            raise ApiError(400, "invalid_filter", "search must not exceed 200 characters.")
    for field, allowed in (("category", CATEGORIES), ("priority", PRIORITIES), ("status", STATUSES)):
        value = request.args.get(field)
        if value is not None and value not in allowed:
            raise ApiError(400, "invalid_filter", f"Invalid {field} filter.")
        filters[field] = value
    for field, maximum in (("assigned_to", 100), ("owner_user_id", 128)):
        value = request.args.get(field)
        if value is not None:
            value = value.strip()
            if not value or len(value) > maximum:
                raise ApiError(400, "invalid_filter", f"Invalid {field} filter.")
        filters[field] = value
    return filters


def create_app(database_path=None):
    application = Flask(__name__)
    path = database_path or database.get_database_path()
    application.config["DATABASE_PATH"] = path

    @application.errorhandler(ApiError)
    def api_error(error):
        return _error(error.status_code, error.code, error.message)

    @application.errorhandler(400)
    def bad_request(_error):
        return _error(400, "bad_request", "The request could not be understood.")

    @application.errorhandler(404)
    def not_found(_error):
        return _error(404, "not_found", "The requested resource was not found.")

    @application.errorhandler(sqlite3.IntegrityError)
    def integrity_error(error):
        LOGGER.warning("database integrity conflict: %s", error.__class__.__name__)
        return _error(409, "conflict", "The database rejected the requested change.")

    @application.errorhandler(sqlite3.Error)
    def database_error(error):
        LOGGER.exception("database operation failed: %s", error.__class__.__name__)
        return _error(500, "database_error", "The database operation failed.")

    @application.errorhandler(Exception)
    def unexpected_error(error):
        LOGGER.exception("unexpected database API error: %s", error.__class__.__name__)
        return _error(500, "internal_error", "An internal server error occurred.")

    @application.get("/health")
    def health():
        with closing(database.get_database_connection(path)) as connection:
            connection.execute("SELECT 1").fetchone()
        return jsonify({"status": "ok", "service": "customer-support-database"})

    @application.get("/api/tickets")
    def list_tickets():
        filters = _filters(); tickets, counts = database.get_tickets(filters, path)
        return jsonify({"count": len(tickets), "tickets": tickets, "status_counts": counts, "filters": filters})

    @application.get("/api/tickets/<int:ticket_id>")
    def get_ticket(ticket_id):
        owner_user_id = request.args.get("owner_user_id")
        ticket = database.get_ticket(ticket_id, path, owner_user_id=owner_user_id)
        if ticket is None:
            raise ApiError(404, "not_found", "Ticket not found.")
        return jsonify(ticket)

    @application.post("/api/tickets")
    def create_ticket():
        payload = _json()
        values = {
            "customer_user_id": _owner_id(payload),
            "customer_name_snapshot": _string(payload, "customer_name_snapshot", 2, 100),
            "customer_email_snapshot": _email(payload),
            "subject": _string(payload, "subject", 5, 160),
            "message": _string(payload, "message", 1, 2000),
        }
        return jsonify(database.create_ticket(values, _now(), path)), 201

    @application.post("/api/tickets/<int:ticket_id>/messages")
    def add_message(ticket_id):
        payload = _json(); values = {"sender_role": _enum(payload, "sender_role", SENDER_ROLES) or "customer", "message": _string(payload, "message", 1, 2000)}
        if "author_name" in payload:
            values["author_name"] = _string(payload, "author_name", 2, 100)
        message = database.create_ticket_message(
            ticket_id,
            values,
            _now(),
            path,
            owner_user_id=payload.get("owner_user_id"),
        )
        if message is None:
            raise ApiError(404, "not_found", "Ticket not found.")
        return jsonify(message), 201

    @application.put("/api/tickets/<int:ticket_id>")
    def update_ticket(ticket_id):
        payload = _json(); values = {}
        for field, allowed in (("category", CATEGORIES), ("priority", PRIORITIES), ("status", STATUSES)):
            if field in payload:
                values[field] = _enum(payload, field, allowed, required=True)
        if "assigned_to" in payload:
            values["assigned_to"] = _assigned(payload)
        if "triage_applied_by" in payload:
            values["triage_applied_by"] = None if payload["triage_applied_by"] is None else _string(payload, "triage_applied_by", 2, 100)
        if not values:
            raise ApiError(400, "invalid_update", "At least one ticket field must be supplied.")
        ticket = database.update_ticket(ticket_id, values, _now(), path)
        if ticket is None:
            raise ApiError(404, "not_found", "Ticket not found.")
        return jsonify(ticket)

    @application.delete("/api/tickets/<int:ticket_id>")
    def delete_ticket(ticket_id):
        if not database.delete_ticket(ticket_id, path):
            raise ApiError(404, "not_found", "Ticket not found.")
        return jsonify({"deleted": True, "id": ticket_id})

    return application


app = create_app()

if __name__ == "__main__":
    try:
        from .init_db import initialize_database
    except ImportError:  # pragma: no cover
        from database_service.init_db import initialize_database
    initialize_database(app.config["DATABASE_PATH"])
    app.run(
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "6006")),
        debug=False,
        use_reloader=False,
    )
