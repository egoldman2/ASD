from flask import Blueprint, jsonify, request

from ..controllers import cart_controller


cart_blueprint = Blueprint("cart", __name__, url_prefix="/api/cart-items")


@cart_blueprint.get("")
def get_cart_items():
    payload, status_code = cart_controller.get_cart_items()
    return jsonify(payload), status_code


@cart_blueprint.post("")
def create_cart_item():
    payload, status_code = cart_controller.create_cart_item(
        request.get_json(silent=True)
    )
    return jsonify(payload), status_code


@cart_blueprint.put("/<int:cart_item_id>")
def update_cart_item(cart_item_id):
    payload, status_code = cart_controller.update_cart_item(
        cart_item_id, request.get_json(silent=True)
    )
    return jsonify(payload), status_code


@cart_blueprint.delete("/<int:cart_item_id>")
def delete_cart_item(cart_item_id):
    payload, status_code = cart_controller.delete_cart_item(cart_item_id)
    return jsonify(payload), status_code
