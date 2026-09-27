"""Protected, bounded read endpoints used by the host MCP tools."""

from flask import Blueprint, jsonify, request

try:
    from .ai import redact_text
    from .validation import ValidationError, validate_admin_filters
except ImportError:  # Direct-script backend startup.
    from ai import redact_text
    from validation import ValidationError, validate_admin_filters


def _query(allowed):
    if set(request.args) - set(allowed) or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise ValidationError("Unsupported or repeated query parameter.")


def _integer(field, default, minimum, maximum):
    value = request.args.get(field, str(default))
    if not value.isascii() or not value.isdecimal() or not minimum <= int(value) <= maximum:
        raise ValidationError(f"{field} must be an integer between {minimum} and {maximum}.", field)
    return int(value)


def _private_values(ticket):
    values = [ticket.get("customer_name_snapshot"), ticket.get("customer_email_snapshot")]
    values.extend(message.get("author_name") for message in ticket.get("messages", [])
                  if message.get("sender_role") == "customer")
    return tuple(value for value in values if isinstance(value, str) and value)


def public_ticket(ticket):
    """Keep operational fields while removing customer identity and prose PII."""
    private = _private_values(ticket)
    result = {field: ticket[field] for field in
              ("id", "status", "category", "priority", "created_at", "updated_at")}
    result["subject"] = redact_text(ticket.get("subject", ""), private)
    assignee = ticket.get("assigned_to")
    result["assigned_to"] = redact_text(assignee) if assignee else None
    if "messages" in ticket:
        result.update(
            messages=[{"id": message["id"], "sender_role": message["sender_role"],
                       "message": redact_text(message["message"], private),
                       "created_at": message["created_at"]} for message in ticket["messages"]],
            message_count=ticket["message_count"], message_limit=ticket["message_limit"],
            messages_truncated=ticket["messages_truncated"],
        )
    return result


def create_tool_reads_blueprint(*, principal, database, db_error):
    blueprint = Blueprint("support_tool_reads", __name__, url_prefix="/api/support/admin/tool-data")

    @blueprint.get("/tickets")
    def search_tickets():
        _, error = principal("admin")
        if error is not None:
            return error
        try:
            _query({"search", "category", "priority", "status", "assigned_to", "limit", "offset"})
            filters = validate_admin_filters(request.args)
            result = database().search_ticket_summaries(
                filters, limit=_integer("limit", 20, 1, 50), offset=_integer("offset", 0, 0, 10000),
            )
            private = tuple(value for ticket in result["tickets"] for value in _private_values(ticket))
            result["tickets"] = [public_ticket(ticket) for ticket in result["tickets"]]
            result["filters"] = {key: redact_text(value, private) for key, value in filters.items()}
            return jsonify(result)
        except ValidationError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return db_error(exc)

    @blueprint.get("/tickets/<int:ticket_id>")
    def get_ticket_context(ticket_id):
        _, error = principal("admin")
        if error is not None:
            return error
        try:
            _query({"message_limit"})
            if ticket_id < 1:
                raise ValidationError("ticket_id must be a positive integer.")
            result = database().get_ticket_context(
                ticket_id, message_limit=_integer("message_limit", 20, 1, 50),
            )
            return jsonify(public_ticket(result))
        except ValidationError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return db_error(exc)

    return blueprint
