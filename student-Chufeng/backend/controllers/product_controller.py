import logging
import sqlite3

from ..models import product_model


LOGGER = logging.getLogger(__name__)


def validate_product_data(data):
    if not isinstance(data, dict):
        return None, "A JSON request body is required."

    name = data.get("name")
    category = data.get("category")
    description = data.get("description", "")
    price = data.get("price")
    stock_quantity = data.get("stock_quantity")

    if not isinstance(name, str) or not name.strip():
        return None, "Product name is required."

    if not isinstance(category, str) or not category.strip():
        return None, "Category is required."

    if not isinstance(description, str):
        return None, "Description must be text."

    if isinstance(price, bool) or not isinstance(price, (int, float)) or price < 0:
        return None, "Price must be zero or greater."

    if (
        isinstance(stock_quantity, bool)
        or not isinstance(stock_quantity, int)
        or stock_quantity < 0
    ):
        return None, "Stock quantity must be a whole number of zero or greater."

    return {
        "name": name.strip(),
        "category": category.strip(),
        "description": description.strip(),
        "price": price,
        "stock_quantity": stock_quantity,
        "status": "active" if stock_quantity > 0 else "out_of_stock",
    }, None


def get_products(search_term=""):
    try:
        products = product_model.get_products(search_term.strip())
    except sqlite3.Error:
        LOGGER.exception("Unable to retrieve products")
        return {"error": "Unable to retrieve products."}, 500

    return {"count": len(products), "products": products}, 200


def create_product(data):
    product_data, validation_error = validate_product_data(data)

    if validation_error:
        return {"error": validation_error}, 400

    try:
        if product_model.product_name_exists(product_data["name"]):
            return {"error": "A product with this name already exists."}, 409

        product = product_model.create_product(product_data)
    except sqlite3.IntegrityError:
        return {"error": "A product with this name already exists."}, 409
    except sqlite3.Error:
        LOGGER.exception("Unable to create product")
        return {"error": "Unable to create product."}, 500

    return {"product": product}, 201


def update_product(product_id, data):
    product_data, validation_error = validate_product_data(data)

    if validation_error:
        return {"error": validation_error}, 400

    try:
        if product_model.get_product(product_id) is None:
            return {"error": "Product not found."}, 404

        if product_model.product_name_exists(
            product_data["name"], exclude_id=product_id
        ):
            return {"error": "A product with this name already exists."}, 409

        product = product_model.update_product(product_id, product_data)
    except sqlite3.IntegrityError:
        return {"error": "A product with this name already exists."}, 409
    except sqlite3.Error:
        LOGGER.exception("Unable to update product")
        return {"error": "Unable to update product."}, 500

    if product is None:
        return {"error": "Product not found."}, 404

    return {"product": product}, 200


def delete_product(product_id):
    try:
        product = product_model.delete_product(product_id)
    except sqlite3.Error:
        LOGGER.exception("Unable to delete product")
        return {"error": "Unable to delete product."}, 500

    if product is None:
        return {"error": "Product not found."}, 404

    return {
        "message": "Product deleted successfully.",
        "product": product,
    }, 200
