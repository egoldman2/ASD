"""HTMX fragments for the staff-only Customer Support workspace."""

from flask import Blueprint, render_template, request

from ..controllers import ticket_controller


support_ticket_ui_blueprint = Blueprint(
    "support_ticket_ui",
    __name__,
    template_folder="../templates",
    url_prefix="/support-ui/staff/tickets",
)


@support_ticket_ui_blueprint.get("")
def list_tickets():
    payload, status_code = ticket_controller.get_tickets(request.args)
    if status_code != 200:
        return render_template("customer_support/notice.html", **payload), status_code

    return render_template("customer_support/ticket_list.html", **payload)


@support_ticket_ui_blueprint.get("/<int:ticket_id>")
def get_ticket(ticket_id):
    payload, status_code = ticket_controller.get_ticket(ticket_id)
    if status_code != 200:
        return render_template("customer_support/notice.html", **payload), status_code

    return render_template("customer_support/ticket_detail.html", **payload)
