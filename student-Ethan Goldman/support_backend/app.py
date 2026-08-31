"""Independent Flask API for Customer Support.

The service delegates authentication, persistence, and AI inference to
separate services. It has no dependency on the repository root application.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Mapping

from flask import Flask, current_app, g, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

try:
    from . import ai, auth, db_client, validation
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ai  # type: ignore
    import auth  # type: ignore
    import db_client  # type: ignore
    import validation  # type: ignore


LOGGER = logging.getLogger(__name__)
FRONTEND_ORIGIN = "http://localhost:8005"
MUTATIONS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
CORRELATION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _error(message: str, status: int, field: str | None = None):
    body: dict[str, Any] = {"error": message if isinstance(message, str) else "Request failed."}
    if field:
        body["field"] = field
    return jsonify(body), status


def _input() -> Mapping[str, Any] | None:
    return request.get_json(silent=True)


def _principal(role: str | None = None):
    try:
        user = auth.authenticate_request()
    except auth.InvalidSession:
        return None, _error("You must sign in.", 401)
    except auth.AuthError:
        return None, _error("Authentication service unavailable.", 503)
    normalized = (user.role or "").casefold()
    if role == "admin" and normalized != "admin":
        return None, _error("You do not have permission for this resource.", 403)
    if role == "customer" and normalized != "customer":
        return None, _error("You do not have permission for this resource.", 403)
    return user, None


def _database():
    client = current_app.extensions.get("support_database_client")
    if client is None:
        client = db_client.SupportDatabaseClient(
            base_url=current_app.config["SUPPORT_DATABASE_API_URL"],
            timeout=current_app.config["SUPPORT_DATABASE_TIMEOUT"],
        )
        current_app.extensions["support_database_client"] = client
    return client


def _db_error(exc: Exception):
    if isinstance(exc, db_client.SupportDatabaseError):
        return _error(exc.public_message, exc.status_code)
    LOGGER.error("support_database_call_failed correlation_id=%s", g.correlation_id)
    return _error("The support database could not complete the request.", 503)


def create_app(config: Mapping[str, Any] | None = None, *, database: Any = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        AUTH_SERVICE_URL=os.getenv("AUTH_SERVICE_URL", "http://ethan-backend:6002"),
        AUTH_TIMEOUT_SECONDS=_float_env("AUTH_TIMEOUT_SECONDS", 5),
        SUPPORT_DATABASE_API_URL=os.getenv(
            "SUPPORT_DATABASE_API_URL", "http://customer-support-database:6006"
        ),
        SUPPORT_DATABASE_TIMEOUT=_float_env("SUPPORT_DATABASE_TIMEOUT", 5),
        SUPPORT_FRONTEND_ORIGIN=os.getenv("SUPPORT_FRONTEND_ORIGIN", FRONTEND_ORIGIN),
        MAX_CONTENT_LENGTH=256 * 1024,
    )
    if config:
        app.config.update(dict(config))
    if database is not None:
        app.extensions["support_database_client"] = database

    @app.before_request
    def before():
        supplied = request.headers.get("X-Correlation-ID", "").strip()
        g.correlation_id = supplied if CORRELATION_RE.fullmatch(supplied) else uuid.uuid4().hex
        origin = request.headers.get("Origin")
        allowed = current_app.config["SUPPORT_FRONTEND_ORIGIN"]
        if request.method == "OPTIONS":
            if origin and origin != allowed:
                return _error("Origin is not allowed.", 403)
            return "", 204
        if (
            request.method in MUTATIONS
            and request.path.startswith("/api/support/")
            and origin != allowed
        ):
            return _error("A trusted request origin is required.", 403)
        return None

    @app.after_request
    def after(response):
        origin = request.headers.get("Origin")
        allowed = current_app.config["SUPPORT_FRONTEND_ORIGIN"]
        vary = response.headers.get("Vary", "")
        if "Origin" not in {part.strip() for part in vary.split(",") if part.strip()}:
            response.headers["Vary"] = f"{vary}, Origin".strip(", ")
        if origin == allowed:
            response.headers["Access-Control-Allow-Origin"] = allowed
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, Accept, X-Requested-With, X-Correlation-ID"
            )
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            )
        response.headers["X-Correlation-ID"] = g.get("correlation_id", uuid.uuid4().hex)
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_exc):
        return _error("Request is too large.", 413)

    @app.errorhandler(404)
    def missing(_exc):
        return _error("The requested support resource was not found.", 404)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "customer-support-backend"})

    @app.get("/api/support/customer/session")
    def session():
        user, failure = _principal()
        if failure:
            return failure
        return jsonify({"authenticated": True, "user": user.to_dict()})

    @app.get("/api/support/customer/tickets")
    def customer_list():
        user, failure = _principal("customer")
        if failure:
            return failure
        if request.args:
            return _error("Customer ticket listing does not accept search or filters.", 400)
        try:
            result = _database().list_tickets(customer_user_id=user.id)
        except Exception as exc:
            return _db_error(exc)
        return jsonify(result)

    @app.post("/api/support/customer/tickets")
    def customer_create():
        user, failure = _principal("customer")
        if failure:
            return failure
        if not user.name or not user.email:
            return _error("Your authenticated profile is incomplete.", 403)
        try:
            values = validation.validate_customer_create(_input())
        except validation.ValidationError as exc:
            return _error(exc.message, 400, exc.field)
        try:
            result = _database().create_ticket(
                customer_user_id=user.id,
                customer_name_snapshot=user.name,
                customer_email_snapshot=user.email,
                subject=values["subject"],
                message=values["message"],
            )
        except Exception as exc:
            return _db_error(exc)
        return jsonify({"ticket": result, "message": "Support ticket created."}), 201

    @app.get("/api/support/customer/tickets/<int:ticket_id>")
    def customer_detail(ticket_id: int):
        user, failure = _principal("customer")
        if failure:
            return failure
        try:
            ticket = _database().get_ticket(ticket_id, customer_user_id=user.id)
        except Exception as exc:
            return _db_error(exc)
        if not isinstance(ticket, Mapping):
            return _error("The requested support ticket was not found.", 404)
        return jsonify({"ticket": ticket})

    @app.post("/api/support/customer/tickets/<int:ticket_id>/messages")
    def customer_message(ticket_id: int):
        user, failure = _principal("customer")
        if failure:
            return failure
        try:
            values = validation.validate_message(_input())
            result = _database().create_message(
                ticket_id,
                message=values["message"],
                sender_role="customer",
                author_name=user.name or "Customer",
                customer_user_id=user.id,
            )
            ticket = _database().get_ticket(ticket_id, customer_user_id=user.id)
        except validation.ValidationError as exc:
            return _error(exc.message, 400, exc.field)
        except Exception as exc:
            return _db_error(exc)
        if not isinstance(ticket, Mapping):
            return _error("The requested support ticket was not found.", 404)
        return jsonify({"ticket": ticket, "message": result, "ticket_id": ticket_id}), 201

    @app.get("/api/support/admin/tickets")
    def admin_list():
        _user, failure = _principal("admin")
        if failure:
            return failure
        try:
            filters = validation.validate_admin_filters(request.args.to_dict())
            result = _database().list_tickets(filters=filters)
        except validation.ValidationError as exc:
            return _error(exc.message, 400, exc.field)
        except Exception as exc:
            return _db_error(exc)
        return jsonify(result)

    @app.get("/api/support/admin/tickets/<int:ticket_id>")
    def admin_detail(ticket_id: int):
        _user, failure = _principal("admin")
        if failure:
            return failure
        try:
            ticket = _database().get_ticket(ticket_id)
            if not isinstance(ticket, Mapping):
                return _error("The requested support ticket was not found.", 404)
        except Exception as exc:
            return _db_error(exc)
        return jsonify({"ticket": ticket})

    @app.put("/api/support/admin/tickets/<int:ticket_id>")
    def admin_update(ticket_id: int):
        user, failure = _principal("admin")
        if failure:
            return failure
        try:
            values = validation.validate_admin_update(_input())
        except validation.ValidationError as exc:
            return _error(exc.message, 400, exc.field)
        update = {key: value for key, value in values.items() if key in {"category", "priority", "status", "assigned_to"}}
        if values.get("apply_triage"):
            update.update(
                category=values["triage_category"],
                priority=values["triage_priority"],
                triage_applied_by=str(user.id),
            )
        try:
            result = _database().update_ticket(ticket_id, update)
        except Exception as exc:
            return _db_error(exc)
        return jsonify({"ticket": result, "message": "Ticket updated."})

    @app.delete("/api/support/admin/tickets/<int:ticket_id>")
    def admin_delete(ticket_id: int):
        _user, failure = _principal("admin")
        if failure:
            return failure
        try:
            _database().delete_ticket(ticket_id)
        except Exception as exc:
            return _db_error(exc)
        return jsonify({"message": "Support ticket deleted.", "ticket_id": ticket_id})

    @app.post("/api/support/admin/tickets/<int:ticket_id>/messages")
    def admin_message(ticket_id: int):
        user, failure = _principal("admin")
        if failure:
            return failure
        try:
            values = validation.validate_message(_input())
            result = _database().create_message(
                ticket_id,
                message=values["message"],
                sender_role="staff",
                author_name=user.name or "Support staff",
            )
            ticket = _database().get_ticket(ticket_id)
        except validation.ValidationError as exc:
            return _error(exc.message, 400, exc.field)
        except Exception as exc:
            return _db_error(exc)
        if not isinstance(ticket, Mapping):
            return _error("The requested support ticket was not found.", 404)
        return jsonify({"ticket": ticket, "message": result, "ticket_id": ticket_id}), 201

    @app.post("/api/support/admin/tickets/<int:ticket_id>/ai-analysis")
    def admin_ai(ticket_id: int):
        _user, failure = _principal("admin")
        if failure:
            return failure
        try:
            result = ai.analyze_ticket(
                _database().get_ticket(ticket_id),
                correlation_id=g.correlation_id,
            )
        except db_client.SupportDatabaseError as exc:
            return _db_error(exc)
        except ai.OllamaError as exc:
            return _error(exc.safe_message, exc.status_code)
        except Exception:
            LOGGER.error("support_ai_failed correlation_id=%s", g.correlation_id)
            return _error("The AI assistant is currently unavailable.", 503)
        return jsonify(result)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "6005")),
        debug=False,
        use_reloader=False,
    )
