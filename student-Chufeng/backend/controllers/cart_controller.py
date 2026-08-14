import logging
import sqlite3

from ..models import cart_model, product_model


LOGGER = logging.getLogger(__name__)


def _validate_quantity(data):
    if not isinstance(data, dict):
        return None, "A JSON request body is required."

    quantity = data.get("quantity")
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        return None, "Quantity must be a whole number of one or greater."

    return quantity, None


def _cart_response(items):
    return {
        "count": len(items),
        "total_quantity": sum(item["quantity"] for item in items),
        "total": round(sum(item["subtotal"] for item in items), 2),
        "items": items,
    }


def get_cart_items():
    try:
        return _cart_response(cart_model.get_cart_items()), 200
    except sqlite3.Error:
        LOGGER.exception("Unable to retrieve cart items")
        return {"error": "Unable to retrieve cart items."}, 500


def create_cart_item(data):
    quantity, validation_error = _validate_quantity(data)
    if validation_error:
        return {"error": validation_error}, 400

    product_id = data.get("product_id")
    if isinstance(product_id, bool) or not isinstance(product_id, int):
        return {"error": "A valid product ID is required."}, 400

    try:
        product = product_model.get_product(product_id)
        if product is None:
            return {"error": "Product not found."}, 404

        if product["status"] != "active" or product["stock_quantity"] < 1:
            return {"error": "This product is out of stock."}, 409

        existing_item = cart_model.get_cart_item_by_product(product_id)
        new_quantity = quantity
        if existing_item is not None:
            new_quantity += existing_item["quantity"]

        if new_quantity > product["stock_quantity"]:
            return {"error": "The requested quantity exceeds available stock."}, 409

        if existing_item is not None:
            item = cart_model.update_cart_item(existing_item["id"], new_quantity)
            return {
                "message": "Cart quantity updated successfully.",
                "item": item,
            }, 200

        item = cart_model.create_cart_item(product_id, quantity)
    except sqlite3.Error:
        LOGGER.exception("Unable to add product to cart")
        return {"error": "Unable to add product to cart."}, 500

    return {"message": "Product added to cart successfully.", "item": item}, 201


def update_cart_item(cart_item_id, data):
    quantity, validation_error = _validate_quantity(data)
    if validation_error:
        return {"error": validation_error}, 400

    try:
        existing_item = cart_model.get_cart_item(cart_item_id)
        if existing_item is None:
            return {"error": "Cart item not found."}, 404

        if quantity > existing_item["stock_quantity"]:
            return {"error": "The requested quantity exceeds available stock."}, 409

        item = cart_model.update_cart_item(cart_item_id, quantity)
    except sqlite3.Error:
        LOGGER.exception("Unable to update cart item")
        return {"error": "Unable to update cart item."}, 500

    return {"message": "Cart quantity updated successfully.", "item": item}, 200


def delete_cart_item(cart_item_id):
    try:
        item = cart_model.get_cart_item(cart_item_id)
        if item is None:
            return {"error": "Cart item not found."}, 404

        cart_model.delete_cart_item(cart_item_id)
    except sqlite3.Error:
        LOGGER.exception("Unable to remove cart item")
        return {"error": "Unable to remove cart item."}, 500

    return {"message": "Product removed from cart successfully.", "item": item}, 200
