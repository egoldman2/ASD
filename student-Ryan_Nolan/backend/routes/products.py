from flask import Blueprint, abort, g, jsonify, request

from database_client import DatabaseServiceError, database_request


products_blueprint = Blueprint(
    "products_blueprint", __name__, url_prefix="/api/inventory/products"
)


def _require_admin():
    if g.authenticated_user.get("role") != "admin":
        return jsonify({"error": "Administrator access required."}), 403
    return None


def _validate_payload(payload):
    if not (payload.get("name") or "").strip():
        abort(400, description="Product name is required")
    if not (payload.get("category") or "").strip():
        abort(400, description="Category is required")
    if not isinstance(payload.get("price"), (int, float)) or payload["price"] < 0:
        abort(400, description="Price must be a non-negative number")
    if not isinstance(payload.get("stock_quantity"), int) or payload["stock_quantity"] < 0:
        abort(400, description="Stock quantity must be a non-negative integer")


def _database_error(error):
    return jsonify(error.payload), error.status_code


@products_blueprint.get("")
def list_products():
    if (error := _require_admin()) is not None:
        return error
    try:
        products = database_request(
            "GET",
            "products",
            params={
                "search": request.args.get("search", ""),
                "filter": request.args.get("filter", "all"),
            },
        )
    except DatabaseServiceError as error:
        return _database_error(error)
    return jsonify(products)


@products_blueprint.get("/<int:product_id>")
def get_product(product_id):
    if (error := _require_admin()) is not None:
        return error
    try:
        product = database_request("GET", f"products/{product_id}")
    except DatabaseServiceError as error:
        return _database_error(error)
    return jsonify(product)


@products_blueprint.post("")
def create_product():
    if (error := _require_admin()) is not None:
        return error
    payload = request.get_json(silent=True) or {}
    _validate_payload(payload)
    try:
        product = database_request("POST", "products", json=payload)
    except DatabaseServiceError as error:
        return _database_error(error)
    return jsonify(product), 201


@products_blueprint.put("/<int:product_id>")
def update_product(product_id):
    if (error := _require_admin()) is not None:
        return error
    payload = request.get_json(silent=True) or {}
    _validate_payload(payload)
    try:
        product = database_request("PUT", f"products/{product_id}", json=payload)
    except DatabaseServiceError as error:
        return _database_error(error)
    return jsonify(product)


@products_blueprint.delete("/<int:product_id>")
def delete_product(product_id):
    if (error := _require_admin()) is not None:
        return error
    try:
        database_request("DELETE", f"products/{product_id}")
    except DatabaseServiceError as error:
        return _database_error(error)
    return "", 204
