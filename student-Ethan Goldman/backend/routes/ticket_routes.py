"""JSON endpoints for Customer Support tickets and their messages."""

from flask import Blueprint, jsonify, request

from ..controllers import ticket_controller


support_ticket_blueprint = Blueprint(
    "support_tickets", __name__, url_prefix="/api/support-tickets"
)


@support_ticket_blueprint.get("")
def list_tickets():
    payload, status_code = ticket_controller.get_tickets(request.args)
    return jsonify(payload), status_code


@support_ticket_blueprint.post("")
def create_ticket():
    payload, status_code = ticket_controller.create_ticket(
        request.get_json(silent=True) or {}
    )
    return jsonify(payload), status_code


@support_ticket_blueprint.get("/<int:ticket_id>")
def get_ticket(ticket_id):
    payload, status_code = ticket_controller.get_ticket(ticket_id)
    return jsonify(payload), status_code


@support_ticket_blueprint.post("/<int:ticket_id>/messages")
def add_ticket_message(ticket_id):
    payload, status_code = ticket_controller.add_ticket_message(
        ticket_id, request.get_json(silent=True) or {}
    )
    return jsonify(payload), status_code
