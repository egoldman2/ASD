from flask import Blueprint, g, jsonify, request

from database_client import DatabaseServiceError, database_request


suppliers_blueprint = Blueprint(
    "suppliers_blueprint", __name__, url_prefix="/api/inventory/suppliers"
)


def _require_admin():
    if g.authenticated_user.get("role") != "admin":
        return jsonify({"error": "Administrator access required."}), 403
    return None


def _database_error(error):
    return jsonify(error.payload), error.status_code


@suppliers_blueprint.get("")
def list_suppliers():
    if (error := _require_admin()) is not None:
        return error
    try:
        suppliers = database_request(
            "GET", "suppliers", params={"search": request.args.get("search", "")}
        )
    except DatabaseServiceError as error:
        return _database_error(error)
    return jsonify(suppliers)


@suppliers_blueprint.get("/<int:supplier_id>")
def get_supplier(supplier_id):
    if (error := _require_admin()) is not None:
        return error
    try:
        supplier = database_request("GET", f"suppliers/{supplier_id}")
    except DatabaseServiceError as error:
        return _database_error(error)
    return jsonify(supplier)


@suppliers_blueprint.post("")
def create_supplier():
    if (error := _require_admin()) is not None:
        return error
    try:
        supplier = database_request(
            "POST", "suppliers", json=request.get_json(silent=True) or {}
        )
    except DatabaseServiceError as error:
        return _database_error(error)
    return jsonify(supplier), 201


@suppliers_blueprint.put("/<int:supplier_id>")
def update_supplier(supplier_id):
    if (error := _require_admin()) is not None:
        return error
    try:
        supplier = database_request(
            "PUT", f"suppliers/{supplier_id}", json=request.get_json(silent=True) or {}
        )
    except DatabaseServiceError as error:
        return _database_error(error)
    return jsonify(supplier)


@suppliers_blueprint.delete("/<int:supplier_id>")
def delete_supplier(supplier_id):
    if (error := _require_admin()) is not None:
        return error
    try:
        database_request("DELETE", f"suppliers/{supplier_id}")
    except DatabaseServiceError as error:
        return _database_error(error)
    return "", 204
