"""Server-rendered HTMX fragments for Customer Support."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlencode

from flask import Blueprint, Response, current_app, g, make_response, redirect, render_template, request
from shared.mcp_client import MCPClientError

try:
    from . import ai, validation
    from . import mcp_client, mcp_routes, mcp_assistant
    from . import rag_client, rag_routes
except ImportError:  # Direct Docker script execution.
    import ai  # type: ignore
    import validation  # type: ignore
    import mcp_client
    import mcp_routes
    import mcp_assistant
    import rag_client
    import rag_routes


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
        if "/mcp/" in path or "/rag/" in path:
            return None  # These forms swap inside an existing result region.
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
                if request.headers.get("HX-Request") != "true":
                    return redirect(login_url)
                response = make_response("", 200)
                response.headers["HX-Redirect"] = login_url
                return response
            return error_fragment(failure)
        response = make_response("", 200)
        destination = (
            "/staff.html" if (user.role or "").casefold() == "admin" else "/customer.html"
        )
        if request.headers.get("HX-Request") == "true":
            response.headers["HX-Redirect"] = destination
            return response
        return redirect(destination)

    @blueprint.get("/api/support/ui/access/customer")
    def customer_access():
        _user, failure = principal("customer")
        return failure or ("", 204)

    @blueprint.get("/api/support/ui/access/admin")
    def admin_access():
        _user, failure = principal("admin")
        return failure or ("", 204)

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

    def tool_arguments(form, allowed_fields):
        if set(form) - set(allowed_fields) or any(len(form.getlist(key)) != 1 for key in form):
            raise validation.ValidationError("Provide supported fields once each.")
        arguments = {key: value for key, value in form.items() if value != ""}
        for field in mcp_client.INTEGER_BOUNDS:
            if field in arguments:
                value = arguments[field]
                if not value.isascii() or not value.isdecimal() or len(value) > 19:
                    raise validation.ValidationError(f"{field} must be an integer.")
                arguments[field] = int(value)
        return arguments

    @blueprint.post("/api/support/ui/admin/mcp/tools/<action>")
    def admin_mcp_tool(action):
        _user, failure = principal("admin")
        if failure:
            return error_fragment(failure)
        names = {"search": mcp_client.SEARCH_TICKETS, "context": mcp_client.GET_TICKET_CONTEXT,
                 "summary": mcp_client.GET_QUEUE_SUMMARY, "attention": mcp_client.GET_TICKETS_NEEDING_ATTENTION}
        name = names.get(action)
        result, error, status = None, None, 200
        try:
            if len(request.get_data()) > 4096:
                return render_template("support_ui/admin/mcp_result.html", error="Tool request is too large."), 413
            arguments = mcp_client.validate_tool_arguments(name, tool_arguments(
                request.form, mcp_client.TOOL_FIELDS.get(name, set()),
            ))
            envelope = mcp_client.validate_tool_response(name, mcp_routes.support_mcp_client().call_tool(
                name, arguments, request_headers=mcp_routes.session_headers(),
            ))
            if envelope["success"]:
                result = envelope["result"]
            else:
                error = "The support tool could not complete the request."
                status = mcp_routes.TOOL_ERROR_STATUSES.get(envelope["error"]["code"], 502)
        except validation.ValidationError as exc:
            error, status = str(exc), 400
        except MCPClientError as exc:
            error, status = str(exc), exc.status_code
        return render_template("support_ui/admin/mcp_result.html", action=action, result=result, error=error), status

    @blueprint.post("/api/support/ui/admin/mcp/assistant")
    def admin_mcp_assistant():
        _user, failure = principal("admin")
        if failure:
            return error_fragment(failure)
        try:
            if len(request.get_data()) > 4096:
                return render_template("support_ui/admin/mcp_answer.html", error="Assistant request is too large."), 413
            arguments = tool_arguments(request.form, {"question", "ticket_id"})
            question, ticket_id = mcp_assistant.validate_question(arguments)
            result, status = mcp_assistant.answer_question(
                question, ticket_id, mcp_routes.support_mcp_client(), mcp_routes.session_headers(),
                model=current_app.extensions.get("support_mcp_model"),
            )
            return render_template("support_ui/admin/mcp_answer.html", result=result), status
        except validation.ValidationError as exc:
            return render_template("support_ui/admin/mcp_answer.html", error=str(exc)), 400
        except MCPClientError as exc:
            return render_template("support_ui/admin/mcp_answer.html", error=str(exc)), exc.status_code

    @blueprint.post("/api/support/ui/admin/rag/answer")
    def admin_knowledge_answer():
        _user, failure = principal("admin")
        if failure:
            return error_fragment(failure)
        try:
            if len(request.get_data()) > 4096:
                return render_template("support_ui/admin/rag_answer.html", error="Knowledge question is too large."), 413
            arguments = tool_arguments(request.form, {"question"})
            question, top_k = rag_client.validate_question(arguments)
            result = rag_routes.support_rag_client().answer_question(question, top_k)
            result = rag_client.validate_answer(result, question)
            return render_template("support_ui/admin/rag_answer.html", result=result)
        except validation.ValidationError as exc:
            return render_template("support_ui/admin/rag_answer.html", error=str(exc), invalid=True), 400
        except rag_client.RAGClientError as exc:
            return render_template("support_ui/admin/rag_answer.html", error=str(exc)), exc.status_code

    @blueprint.get("/api/support/ui/admin/rag/sources/<filename>")
    def admin_knowledge_source(filename):
        _user, failure = principal("admin")
        if failure:
            return error_fragment(failure)
        path = rag_client.knowledge_file(filename)
        text = None
        if path is not None:
            try:
                with path.open("rb") as stream:
                    raw = stream.read(65537)
                if len(raw) <= 65536:
                    text = raw.decode("utf-8")
            except (OSError, UnicodeError):
                pass
        if text is None:
            return render_template("support_ui/error.html", message="Knowledge source not found or unavailable.",
                                   status=404, login_url=None, target_id=None, retry_path=None), 404
        response = make_response(render_template("support_ui/admin/rag_source.html", filename=filename, text=text))
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

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
