"""JSON read endpoints for Customer Support tickets."""

from flask import Blueprint, jsonify

from ..controllers import ticket_controller


support_ticket_blueprint = Blueprint(
    "support_tickets", __name__, url_prefix="/api/support-tickets"
)


@support_ticket_blueprint.get("")
def list_tickets():
    payload, status_code = ticket_controller.get_tickets()
    return jsonify(payload), status_code


@support_ticket_blueprint.get("/<int:ticket_id>")
def get_ticket(ticket_id):
    payload, status_code = ticket_controller.get_ticket(ticket_id)
    return jsonify(payload), status_code
