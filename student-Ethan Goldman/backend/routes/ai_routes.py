"""JSON and HTMX routes for read-only support ticket analysis."""

from flask import Blueprint, jsonify, render_template, request

from ..controllers import ai_controller


support_ai_blueprint = Blueprint(
    "support_ai", __name__, url_prefix="/api/ai/support-assistant"
)

support_ai_ui_blueprint = Blueprint(
    "support_ai_ui",
    __name__,
    template_folder="../templates",
    url_prefix="/support-ui/staff/tickets",
)


@support_ai_blueprint.post("")
def analyse_ticket():
    payload, status_code = ai_controller.analyse_ticket_request(
        request.get_json(silent=True)
    )
    return jsonify(payload), status_code


@support_ai_ui_blueprint.post("/<int:ticket_id>/ai-analysis")
def analyse_ticket_fragment(ticket_id):
    payload, status_code = ai_controller.analyse_ticket(ticket_id)
    if status_code != 200:
        return render_template("customer_support/notice.html", **payload), status_code
    return render_template("customer_support/ai_result.html", **payload)
