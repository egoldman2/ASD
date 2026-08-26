"""HTMX fragments for the staff-only Customer Support workspace."""

from flask import Blueprint, render_template, request

from ..controllers import ticket_controller


support_ticket_ui_blueprint = Blueprint(
    "support_ticket_ui",
    __name__,
    template_folder="../templates",
    url_prefix="/support-ui/staff/tickets",
)

support_customer_ui_blueprint = Blueprint(
    "support_customer_ui",
    __name__,
    template_folder="../templates",
    url_prefix="/support-ui/customer/tickets",
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


@support_ticket_ui_blueprint.post("/<int:ticket_id>/messages")
def add_staff_message(ticket_id):
    payload, status_code = ticket_controller.add_ticket_message(
        ticket_id, request.form, fixed_sender_role="staff"
    )
    if status_code not in (201, 400):
        return render_template("customer_support/notice.html", **payload), status_code

    ticket_payload, ticket_status = ticket_controller.get_ticket(ticket_id)
    if ticket_status != 200:
        return (
            render_template("customer_support/notice.html", **ticket_payload),
            ticket_status,
        )

    template_values = {
        **ticket_payload,
        "message_notice": "Reply added to the conversation."
        if status_code == 201
        else None,
        "message_error": payload.get("error") if status_code == 400 else None,
    }
    return render_template(
        "customer_support/ticket_detail.html", **template_values
    ), status_code


@support_customer_ui_blueprint.get("")
def get_customer_ticket():
    ticket_id = request.args.get("ticket_id", "").strip()
    if not ticket_id.isdigit():
        return render_template(
            "customer_support/notice.html",
            error="Enter a valid numeric ticket ID.",
        )

    payload, status_code = ticket_controller.get_customer_ticket(
        int(ticket_id), request.args.get("customer_email")
    )
    if status_code != 200:
        return render_template("customer_support/notice.html", **payload)

    return render_template("customer_support/customer_conversation.html", **payload)


@support_customer_ui_blueprint.post("/<int:ticket_id>/messages")
def add_customer_message(ticket_id):
    payload, status_code = ticket_controller.add_customer_ticket_message(
        ticket_id, request.form
    )
    customer_email = request.form.get("customer_email", "")
    if status_code not in (201, 400):
        return render_template("customer_support/notice.html", **payload), status_code

    ticket_payload, ticket_status = ticket_controller.get_customer_ticket(
        ticket_id, customer_email
    )
    if ticket_status != 200:
        return render_template("customer_support/notice.html", **ticket_payload)

    template_values = {
        **ticket_payload,
        "message_notice": "Your reply was added to the conversation."
        if status_code == 201
        else None,
        "message_error": payload.get("error") if status_code == 400 else None,
    }
    return render_template(
        "customer_support/customer_conversation.html", **template_values
    ), status_code
