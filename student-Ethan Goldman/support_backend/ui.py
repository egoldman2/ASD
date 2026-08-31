"""Server-rendered HTMX fragments for Customer Support."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlencode

from flask import Blueprint, Response, g, make_response, render_template, request

try:
    from . import ai, validation
except ImportError:  # Direct Docker script execution.
    import ai  # type: ignore
    import validation  # type: ignore


def create_ui_blueprint(
    *,
    principal: Callable[[str | None], tuple[Any, Any]],
    database: Callable[[], Any],
    db_error: Callable[[Exception], Any],
) -> Blueprint:
    """Build the UI blueprint around the API's existing security helpers."""

    blueprint = Blueprint("support_ui", __name__, template_folder="templates")

    def error_target() -> str | None:
        path = request.path
        if path.endswith("/ai-analysis"):
            return "ai-panel"
        if "/ui/customer/tickets/" in path:
            return "ticket-detail-region"
        if path.endswith("/ui/customer/tickets"):
            return "new-ticket-panel" if request.method == "POST" else "ticket-list-region"
        if "/ui/admin/tickets/" in path:
            return "ticket-detail-shell"
        return None

    def error_fragment(failure: Any):
        response, status = failure if isinstance(failure, tuple) else (failure, 500)
        payload = response.get_json(silent=True) if isinstance(response, Response) else None
        message = (
            payload.get("error")
            if isinstance(payload, Mapping) and isinstance(payload.get("error"), str)
            else "The support request could not be completed."
        )
        page = "staff.html" if "/admin/" in request.path else "customer.html"
        login_url = "http://localhost:8003/index.html?" + urlencode(
            {"return_url": f"http://localhost:8005/{page}"}
        )
        return render_template(
            "support_ui/error.html",
            message=message,
            status=status,
            login_url=login_url,
            target_id=error_target(),
            retry_path=request.full_path.rstrip("?") if request.method == "GET" else None,
        ), status

    def database_failure(exc: Exception):
        return error_fragment(db_error(exc))

    def validation_message(exc: validation.ValidationError) -> str:
        message = request.form.get("message")
        if exc.field == "Message" and isinstance(message, str) and not message.strip():
            return "Message is required."
        return exc.message

    def not_found():
        return render_template(
            "support_ui/error.html",
            message="The requested support ticket was not found.",
            status=404,
            login_url=None,
            target_id=error_target(),
            retry_path=None,
        ), 404

    def customer_ticket(user: Any, ticket_id: int):
        try:
            ticket = database().get_ticket(ticket_id, customer_user_id=user.id)
        except Exception as exc:
            return None, database_failure(exc)
        return (ticket, None) if isinstance(ticket, Mapping) else (None, not_found())

    def admin_ticket(ticket_id: int):
        try:
            ticket = database().get_ticket(ticket_id)
        except Exception as exc:
            return None, database_failure(exc)
        return (ticket, None) if isinstance(ticket, Mapping) else (None, not_found())

    @blueprint.get("/api/support/ui/entry")
    def support_entry():
        user, failure = principal(None)
        if failure:
            _body, status = failure if isinstance(failure, tuple) else (failure, 500)
            if status == 401:
                login_url = "http://localhost:8003/index.html?" + urlencode(
                    {"return_url": "http://localhost:8005/"}
                )
                response = make_response("", 200)
                response.headers["HX-Redirect"] = login_url
                return response
            return error_fragment(failure)
        response = make_response("", 200)
        response.headers["HX-Redirect"] = (
            "/staff.html" if (user.role or "").casefold() == "admin" else "/customer.html"
        )
        return response

    @blueprint.get("/api/support/ui/customer/dashboard")
    def customer_dashboard():
        user, failure = principal("customer")
        if failure:
            return error_fragment(failure)
        return render_template("support_ui/customer/dashboard.html", user=user)

    @blueprint.get("/api/support/ui/customer/tickets")
    def customer_tickets():
        user, failure = principal("customer")
        if failure:
            return error_fragment(failure)
        try:
            result = database().list_tickets(customer_user_id=user.id)
        except Exception as exc:
            return database_failure(exc)
        tickets = result.get("tickets", []) if isinstance(result, Mapping) else []
        return render_template(
            "support_ui/customer/ticket_list.html",
            tickets=tickets if isinstance(tickets, list) else [],
        )

    @blueprint.post("/api/support/ui/customer/tickets")
    def customer_create():
        user, failure = principal("customer")
        if failure:
            return error_fragment(failure)
        if not user.name or not user.email:
            return render_template(
                "support_ui/customer/create_panel.html",
                error="Your authenticated profile is incomplete.",
                values=request.form,
            ), 403
        try:
            values = validation.validate_customer_create(request.form)
        except validation.ValidationError as exc:
            return render_template(
                "support_ui/customer/create_panel.html",
                error=validation_message(exc),
                values=request.form,
            ), 400
        try:
            database().create_ticket(
                customer_user_id=user.id,
                customer_name_snapshot=user.name,
                customer_email_snapshot=user.email,
                subject=values["subject"],
                message=values["message"],
            )
        except Exception as exc:
            return database_failure(exc)
        response = make_response(
            render_template(
                "support_ui/customer/create_panel.html",
                notice="Support ticket created.",
                values={},
            ),
            201,
        )
        response.headers["HX-Trigger"] = "supportTicketsChanged"
        return response

    @blueprint.get("/api/support/ui/customer/tickets/<int:ticket_id>")
    def customer_detail(ticket_id: int):
        user, failure = principal("customer")
        if failure:
            return error_fragment(failure)
        ticket, failure = customer_ticket(user, ticket_id)
        if failure:
            return failure
        return render_template("support_ui/customer/ticket_detail.html", ticket=ticket)

    @blueprint.get("/api/support/ui/customer/ticket-detail")
    def customer_detail_empty():
        _user, failure = principal("customer")
        if failure:
            return error_fragment(failure)
        return render_template("support_ui/customer/ticket_detail_empty.html")

    @blueprint.post("/api/support/ui/customer/tickets/<int:ticket_id>/messages")
    def customer_reply(ticket_id: int):
        user, failure = principal("customer")
        if failure:
            return error_fragment(failure)
        ticket, failure = customer_ticket(user, ticket_id)
        if failure:
            return failure
        try:
            values = validation.validate_message(request.form)
        except validation.ValidationError as exc:
            return render_template(
                "support_ui/customer/ticket_detail.html",
                ticket=ticket,
                error=validation_message(exc),
            ), 400
        try:
            database().create_message(
                ticket_id,
                message=values["message"],
                sender_role="customer",
                author_name=user.name or "Customer",
                customer_user_id=user.id,
            )
            ticket = database().get_ticket(ticket_id, customer_user_id=user.id)
        except Exception as exc:
            return database_failure(exc)
        if not isinstance(ticket, Mapping):
            return not_found()
        response = make_response(
            render_template(
                "support_ui/customer/ticket_detail.html",
                ticket=ticket,
                notice="Your reply was added.",
            ),
            201,
        )
        response.headers["HX-Trigger"] = "supportTicketsChanged"
        return response

    @blueprint.get("/api/support/ui/admin/tickets")
    def admin_queue():
        user, failure = principal("admin")
        if failure:
            return error_fragment(failure)
        try:
            filters = validation.validate_admin_filters(request.args.to_dict())
            result = database().list_tickets(filters=filters)
        except validation.ValidationError as exc:
            return render_template(
                "support_ui/error.html",
                message=exc.message,
                status=400,
                login_url=None,
            ), 400
        except Exception as exc:
            return database_failure(exc)
        tickets = result.get("tickets", []) if isinstance(result, Mapping) else []
        counts = result.get("status_counts", {}) if isinstance(result, Mapping) else {}
        return render_template(
            "support_ui/admin/queue.html",
            user=user,
            tickets=tickets if isinstance(tickets, list) else [],
            counts=counts if isinstance(counts, Mapping) else {},
            filters=filters,
        )

    @blueprint.get("/api/support/ui/admin/tickets/<int:ticket_id>")
    def admin_detail(ticket_id: int):
        _user, failure = principal("admin")
        if failure:
            return error_fragment(failure)
        ticket, failure = admin_ticket(ticket_id)
        if failure:
            return failure
        return render_template("support_ui/admin/ticket_detail.html", ticket=ticket)

    @blueprint.put("/api/support/ui/admin/tickets/<int:ticket_id>")
    def admin_update(ticket_id: int):
        user, failure = principal("admin")
        if failure:
            return error_fragment(failure)
        ticket, failure = admin_ticket(ticket_id)
        if failure:
            return failure
        submitted = request.form.to_dict()
        if submitted.pop("apply_ai_suggestions", None):
            submitted = {
                "apply_ai_suggestions": {
                    "category": submitted.get("category"),
                    "priority": submitted.get("priority"),
                }
            }
        try:
            values = validation.validate_admin_update(submitted)
        except validation.ValidationError as exc:
            return render_template(
                "support_ui/admin/ticket_detail.html",
                ticket=ticket,
                error=validation_message(exc),
            ), 400
        update = {
            key: value
            for key, value in values.items()
            if key in {"category", "priority", "status", "assigned_to"}
        }
        if values.get("apply_triage"):
            update.update(
                category=values["triage_category"],
                priority=values["triage_priority"],
                triage_applied_by=str(user.id),
            )
        try:
            result = database().update_ticket(ticket_id, update)
        except Exception as exc:
            return database_failure(exc)
        if not isinstance(result, Mapping):
            result, failure = admin_ticket(ticket_id)
            if failure:
                return failure
        return render_template(
            "support_ui/admin/ticket_detail.html",
            ticket=result,
            notice="Ticket updated.",
        )

    @blueprint.post("/api/support/ui/admin/tickets/<int:ticket_id>/messages")
    def admin_reply(ticket_id: int):
        user, failure = principal("admin")
        if failure:
            return error_fragment(failure)
        ticket, failure = admin_ticket(ticket_id)
        if failure:
            return failure
        try:
            values = validation.validate_message(request.form)
        except validation.ValidationError as exc:
            return render_template(
                "support_ui/admin/ticket_detail.html",
                ticket=ticket,
                error=validation_message(exc),
            ), 400
        try:
            database().create_message(
                ticket_id,
                message=values["message"],
                sender_role="staff",
                author_name=user.name or "Support staff",
            )
            ticket = database().get_ticket(ticket_id)
        except Exception as exc:
            return database_failure(exc)
        if not isinstance(ticket, Mapping):
            return not_found()
        return render_template(
            "support_ui/admin/ticket_detail.html",
            ticket=ticket,
            notice="Reply added.",
        ), 201

    @blueprint.post("/api/support/ui/admin/tickets/<int:ticket_id>/ai-analysis")
    def admin_ai(ticket_id: int):
        _user, failure = principal("admin")
        if failure:
            return error_fragment(failure)
        ticket, failure = admin_ticket(ticket_id)
        if failure:
            return failure
        try:
            result = ai.analyze_ticket(ticket, correlation_id=g.correlation_id)
        except ai.OllamaError as exc:
            return render_template(
                "support_ui/admin/ai_panel.html",
                ticket_id=ticket_id,
                error=exc.safe_message,
            ), exc.status_code
        except Exception:
            return render_template(
                "support_ui/admin/ai_panel.html",
                ticket_id=ticket_id,
                error="The AI assistant is currently unavailable.",
            ), 503
        return render_template(
            "support_ui/admin/ai_panel.html",
            ticket_id=ticket_id,
            result=result,
        )

    @blueprint.delete("/api/support/ui/admin/tickets/<int:ticket_id>")
    def admin_delete(ticket_id: int):
        _user, failure = principal("admin")
        if failure:
            return error_fragment(failure)
        try:
            database().delete_ticket(ticket_id)
        except Exception as exc:
            return database_failure(exc)
        response = make_response("", 204)
        response.headers["HX-Redirect"] = "/staff.html"
        return response

    return blueprint
