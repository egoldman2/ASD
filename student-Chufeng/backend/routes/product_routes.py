from flask import Blueprint, jsonify, request

from ..controllers import product_controller


product_blueprint = Blueprint("products", __name__, url_prefix="/api/products")


@product_blueprint.get("")
def get_products():
    payload, status_code = product_controller.get_products(
        request.args.get("search", "")
    )
    return jsonify(payload), status_code


@product_blueprint.post("")
def create_product():
    payload, status_code = product_controller.create_product(
        request.get_json(silent=True)
    )
    return jsonify(payload), status_code


@product_blueprint.put("/<int:product_id>")
def update_product(product_id):
    payload, status_code = product_controller.update_product(
        product_id, request.get_json(silent=True)
    )
    return jsonify(payload), status_code


@product_blueprint.delete("/<int:product_id>")
def delete_product(product_id):
    payload, status_code = product_controller.delete_product(product_id)
    return jsonify(payload), status_code
