from flask import Blueprint, jsonify, request

from ..controllers import ai_controller


ai_blueprint = Blueprint(
    "product_ai",
    __name__,
    url_prefix="/api/ai/product-assistant",
)


@ai_blueprint.post("")
def ask_product_assistant():
    payload, status_code = ai_controller.ask_product_assistant(
        request.get_json(silent=True)
    )
    return jsonify(payload), status_code
