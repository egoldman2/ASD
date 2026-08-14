from flask import Blueprint, jsonify, request

from ..controllers import product_controller


product_blueprint = Blueprint("products", __name__, url_prefix="/api/products")


@product_blueprint.get("")
def get_products():
    payload, status_code = product_controller.get_products(
        request.args.get("search", "")
    )
    return jsonify(payload), status_code
