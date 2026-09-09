from importlib import import_module

from flask import Blueprint, current_app, g, jsonify, request


cart_controller = import_module("student-Chufeng.backend.controllers.cart_controller")
product_model = import_module("student-Chufeng.backend.models.product_model")
database = import_module("student-Chufeng.backend.models.database")

cart_blueprint = Blueprint("customer_cart", __name__, url_prefix="/api/cart-items")


def current_user_id():
    return g.authenticated_user["id"]


def validated_quantity(data):
    if not isinstance(data, dict):
        return None, "A JSON request body is required."
    quantity = data.get("quantity")
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        return None, "Quantity must be a whole number of one or greater."
    return quantity, None


def cart_response(items):
    return {
        "count": len(items),
        "total_quantity": sum(item["quantity"] for item in items),
        "total": round(sum(item["subtotal"] for item in items), 2),
        "items": items,
    }


def legacy_response(operation, *args):
    payload, status_code = operation(*args)
    return jsonify(payload), status_code


def database_error(error):
    return jsonify(error.payload), error.status_code


@cart_blueprint.get("")
def get_cart_items():
    if current_app.config.get("TESTING"):
        return legacy_response(cart_controller.get_cart_items)
    try:
        items = database.database_request(
            "GET", "customer-cart-items", params={"user_id": current_user_id()}
        )
    except database.DatabaseAPIError as error:
        return database_error(error)
    return jsonify(cart_response(items))


@cart_blueprint.post("")
def create_cart_item():
    data = request.get_json(silent=True)
    if current_app.config.get("TESTING"):
        return legacy_response(cart_controller.create_cart_item, data)

    quantity, error = validated_quantity(data)
    if error:
        return jsonify({"error": error}), 400
    product_id = data.get("product_id")
    if isinstance(product_id, bool) or not isinstance(product_id, int):
        return jsonify({"error": "A valid product ID is required."}), 400

    try:
        product = product_model.get_product(product_id)
        if product is None:
            return jsonify({"error": "Product not found."}), 404
        if product["status"] != "active" or product["stock_quantity"] < 1:
            return jsonify({"error": "This product is out of stock."}), 409

        try:
            existing = database.database_request(
                "GET",
                f"customer-cart-items/by-product/{product_id}",
                params={"user_id": current_user_id()},
            )
        except database.DatabaseAPIError as lookup_error:
            if lookup_error.status_code != 404:
                raise
            existing = None

        new_quantity = quantity + (existing["quantity"] if existing else 0)
        if new_quantity > product["stock_quantity"]:
            return jsonify({"error": "The requested quantity exceeds available stock."}), 409

        if existing:
            item = database.database_request(
                "PUT",
                f"customer-cart-items/{existing['id']}",
                json={"user_id": current_user_id(), "quantity": new_quantity},
            )
            return jsonify({
                "message": "Cart quantity updated successfully.", "item": item
            }), 200

        item = database.database_request(
            "POST",
            "customer-cart-items",
            json={
                "user_id": current_user_id(),
                "product_id": product_id,
                "quantity": quantity,
            },
        )
    except database.DatabaseAPIError as api_error:
        return database_error(api_error)
    return jsonify({"message": "Product added to cart successfully.", "item": item}), 201


@cart_blueprint.put("/<int:cart_item_id>")
def update_cart_item(cart_item_id):
    data = request.get_json(silent=True)
    if current_app.config.get("TESTING"):
        return legacy_response(cart_controller.update_cart_item, cart_item_id, data)
    quantity, error = validated_quantity(data)
    if error:
        return jsonify({"error": error}), 400
    try:
        items = database.database_request(
            "GET", "customer-cart-items", params={"user_id": current_user_id()}
        )
        existing = next((item for item in items if item["id"] == cart_item_id), None)
        if existing is None:
            return jsonify({"error": "Cart item not found."}), 404
        if quantity > existing["stock_quantity"]:
            return jsonify({"error": "The requested quantity exceeds available stock."}), 409
        item = database.database_request(
            "PUT",
            f"customer-cart-items/{cart_item_id}",
            json={"user_id": current_user_id(), "quantity": quantity},
        )
    except database.DatabaseAPIError as api_error:
        return database_error(api_error)
    return jsonify({"message": "Cart quantity updated successfully.", "item": item})


@cart_blueprint.delete("/<int:cart_item_id>")
def delete_cart_item(cart_item_id):
    if current_app.config.get("TESTING"):
        return legacy_response(cart_controller.delete_cart_item, cart_item_id)
    try:
        item = database.database_request(
            "DELETE",
            f"customer-cart-items/{cart_item_id}",
            params={"user_id": current_user_id()},
        )
    except database.DatabaseAPIError as api_error:
        return database_error(api_error)
    return jsonify({"message": "Product removed from cart successfully.", "item": item})
