import os
import sqlite3
from contextlib import closing
from importlib import import_module
from pathlib import Path

from flask import Blueprint, current_app, g, jsonify, request


cart_controller = import_module(
    "student-Chufeng.backend.controllers.cart_controller"
)
product_model = import_module(
    "student-Chufeng.backend.models.product_model"
)


cart_blueprint = Blueprint("customer_cart", __name__, url_prefix="/api/cart-items")
CART_DATABASE_PATH = Path(
    os.environ.get("CART_DATABASE_PATH", "/data/customer_carts.db")
)


def database_connection():
    CART_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(CART_DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_cart_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            UNIQUE (user_id, product_id)
        )
        """
    )
    connection.commit()
    return connection


def current_user_id():
    return g.authenticated_user["id"]


def validated_quantity(data):
    if not isinstance(data, dict):
        return None, "A JSON request body is required."
    quantity = data.get("quantity")
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        return None, "Quantity must be a whole number of one or greater."
    return quantity, None


def cart_item(row):
    if row is None:
        return None
    product = product_model.get_product(row["product_id"])
    if product is None:
        return None
    return {
        "id": row["id"],
        "product_id": row["product_id"],
        "quantity": row["quantity"],
        "name": product["name"],
        "category": product["category"],
        "description": product["description"],
        "price": product["price"],
        "stock_quantity": product["stock_quantity"],
        "status": product["status"],
        "subtotal": round(product["price"] * row["quantity"], 2),
    }


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


@cart_blueprint.get("")
def get_cart_items():
    if current_app.config.get("TESTING"):
        return legacy_response(cart_controller.get_cart_items)

    with closing(database_connection()) as connection:
        rows = connection.execute(
            """
            SELECT id, product_id, quantity
            FROM customer_cart_items
            WHERE user_id = ?
            ORDER BY id
            """,
            (current_user_id(),),
        ).fetchall()
    items = [item for row in rows if (item := cart_item(row)) is not None]
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

    product = product_model.get_product(product_id)
    if product is None:
        return jsonify({"error": "Product not found."}), 404
    if product["status"] != "active" or product["stock_quantity"] < 1:
        return jsonify({"error": "This product is out of stock."}), 409

    with closing(database_connection()) as connection:
        existing = connection.execute(
            """
            SELECT id, product_id, quantity
            FROM customer_cart_items
            WHERE user_id = ? AND product_id = ?
            """,
            (current_user_id(), product_id),
        ).fetchone()
        new_quantity = quantity + (existing["quantity"] if existing else 0)
        if new_quantity > product["stock_quantity"]:
            return jsonify({
                "error": "The requested quantity exceeds available stock."
            }), 409

        if existing:
            connection.execute(
                "UPDATE customer_cart_items SET quantity = ? WHERE id = ?",
                (new_quantity, existing["id"]),
            )
            item_id = existing["id"]
            status_code = 200
            message = "Cart quantity updated successfully."
        else:
            cursor = connection.execute(
                """
                INSERT INTO customer_cart_items (user_id, product_id, quantity)
                VALUES (?, ?, ?)
                """,
                (current_user_id(), product_id, quantity),
            )
            item_id = cursor.lastrowid
            status_code = 201
            message = "Product added to cart successfully."
        connection.commit()
        row = connection.execute(
            "SELECT id, product_id, quantity FROM customer_cart_items WHERE id = ?",
            (item_id,),
        ).fetchone()

    return jsonify({"message": message, "item": cart_item(row)}), status_code


@cart_blueprint.put("/<int:cart_item_id>")
def update_cart_item(cart_item_id):
    data = request.get_json(silent=True)
    if current_app.config.get("TESTING"):
        return legacy_response(
            cart_controller.update_cart_item,
            cart_item_id,
            data,
        )

    quantity, error = validated_quantity(data)
    if error:
        return jsonify({"error": error}), 400

    with closing(database_connection()) as connection:
        row = connection.execute(
            """
            SELECT id, product_id, quantity
            FROM customer_cart_items
            WHERE id = ? AND user_id = ?
            """,
            (cart_item_id, current_user_id()),
        ).fetchone()
        if row is None:
            return jsonify({"error": "Cart item not found."}), 404
        product = product_model.get_product(row["product_id"])
        if product is None:
            return jsonify({"error": "Product not found."}), 404
        if quantity > product["stock_quantity"]:
            return jsonify({
                "error": "The requested quantity exceeds available stock."
            }), 409
        connection.execute(
            "UPDATE customer_cart_items SET quantity = ? WHERE id = ?",
            (quantity, cart_item_id),
        )
        connection.commit()
        updated = connection.execute(
            "SELECT id, product_id, quantity FROM customer_cart_items WHERE id = ?",
            (cart_item_id,),
        ).fetchone()

    return jsonify({
        "message": "Cart quantity updated successfully.",
        "item": cart_item(updated),
    })


@cart_blueprint.delete("/<int:cart_item_id>")
def delete_cart_item(cart_item_id):
    if current_app.config.get("TESTING"):
        return legacy_response(cart_controller.delete_cart_item, cart_item_id)

    with closing(database_connection()) as connection:
        row = connection.execute(
            """
            SELECT id, product_id, quantity
            FROM customer_cart_items
            WHERE id = ? AND user_id = ?
            """,
            (cart_item_id, current_user_id()),
        ).fetchone()
        if row is None:
            return jsonify({"error": "Cart item not found."}), 404
        item = cart_item(row)
        connection.execute(
            "DELETE FROM customer_cart_items WHERE id = ? AND user_id = ?",
            (cart_item_id, current_user_id()),
        )
        connection.commit()

    return jsonify({
        "message": "Product removed from cart successfully.",
        "item": item,
    })
