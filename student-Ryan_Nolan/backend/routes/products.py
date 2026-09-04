import sys
from pathlib import Path
from contextlib import closing

from flask import Blueprint, g, request, jsonify, abort
import sqlite3

sys.path.append(str(Path(__file__).resolve().parents[2] / "database"))
from ryan_init_db import get_connection 

products_blueprint = Blueprint("products_blueprint", __name__, url_prefix="/api/inventory/products")

def _require_admin():
    if g.authenticated_user.get("role") != "admin":
        return jsonify({"error": "Administrator access required."}), 403

    return None

def _derive_status(stock_quantity: int) -> str:
    """status is derived from stock_quantity rather than user-set,
    per the schema's CHECK (status IN ('active', 'out_of_stock'))."""
    return "out_of_stock" if stock_quantity <= 0 else "active"


def _row_to_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "category": row["category"],
        "description": row["description"],
        "price": row["price"],
        "unit_cost": row["unit_cost"],
        "stock_quantity": row["stock_quantity"],
        "status": row["status"],
        "supplier_id": row["supplier_id"],
        "reorder_threshold": row["reorder_threshold"],
        "reorder_quantity": row["reorder_quantity"],
        "last_restocked_at": row["last_restocked_at"],
    }


def _validate_payload(payload, partial=False):
    if not partial or "name" in payload:
        if not (payload.get("name") or "").strip():
            abort(400, description="Product name is required")

    if not partial or "category" in payload:
        if not (payload.get("category") or "").strip():
            abort(400, description="Category is required")

    if not partial or "price" in payload:
        price = payload.get("price")
        if not isinstance(price, (int, float)) or price < 0:
            abort(400, description="Price must be a non-negative number")

    if "unit_cost" in payload and payload["unit_cost"] is not None:
        unit_cost = payload["unit_cost"]
        if not isinstance(unit_cost, (int, float)) or unit_cost < 0:
            abort(400, description="Unit cost must be a non-negative number")

    if not partial or "stock_quantity" in payload:
        stock = payload.get("stock_quantity")
        if not isinstance(stock, int) or stock < 0:
            abort(400, description="Stock quantity must be a non-negative integer")

    if "reorder_threshold" in payload and payload["reorder_threshold"] is not None:
        if not isinstance(payload["reorder_threshold"], int) or payload["reorder_threshold"] < 0:
            abort(400, description="Reorder threshold must be a non-negative integer")

    if "reorder_quantity" in payload and payload["reorder_quantity"] is not None:
        if not isinstance(payload["reorder_quantity"], int) or payload["reorder_quantity"] < 0:
            abort(400, description="Reorder quantity must be a non-negative integer")


@products_blueprint.get("")
def list_products():
    """GET /api/inventory/products?search=<name>&filter=low_stock|out_of_stock"""
    if (err := _require_admin()) is not None:
        return err

    search = request.args.get("search", "").strip()
    stock_filter = request.args.get("filter", "all")

    conditions = []
    params = []

    if search:
        conditions.append("LOWER(p.name) LIKE LOWER(?)")
        params.append(f"%{search}%")

    if stock_filter == "in_stock":
        conditions.append("p.stock_quantity > p.reorder_threshold")
    elif stock_filter == "low_stock":
        conditions.append("p.stock_quantity > 0 AND p.stock_quantity <= p.reorder_threshold")
    elif stock_filter == "out_of_stock":
        conditions.append("p.stock_quantity <= 0")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with closing(get_connection()) as db:
        rows = db.execute(
            f"""
            SELECT p.id, p.name, p.category, p.description, p.price, p.unit_cost,
                   p.stock_quantity, p.status, p.supplier_id, p.reorder_threshold,
                   p.reorder_quantity, p.last_restocked_at
            FROM products p
            {where_clause}
            ORDER BY p.name ASC
            """,
            params,
        ).fetchall()

    return jsonify([_row_to_dict(r) for r in rows])


@products_blueprint.get("/<int:product_id>")
def get_product(product_id):
    """GET /api/inventory/products/<id>"""
    if (err := _require_admin()) is not None:
        return err

    with closing(get_connection()) as db:
        row = db.execute(
            """
            SELECT id, name, category, description, price, unit_cost, stock_quantity,
                   status, supplier_id, reorder_threshold, reorder_quantity, last_restocked_at
            FROM products WHERE id = ?
            """,
            (product_id,),
        ).fetchone()

    if row is None:
        abort(404, description="Product not found")

    return jsonify(_row_to_dict(row))


@products_blueprint.post("")
def create_product():
    """POST /api/inventory/products
    Body: { name, category, description?, price, unit_cost?, stock_quantity,
            supplier_id?, reorder_threshold?, reorder_quantity? }
    status is derived server-side from stock_quantity.
    last_restocked_at is left NULL on creation.
    """
    if (err := _require_admin()) is not None:
        return err

    payload = request.get_json(silent=True) or {}
    _validate_payload(payload)

    status = _derive_status(payload["stock_quantity"])

    with closing(get_connection()) as db:
        try:
            cursor = db.execute(
                """
                INSERT INTO products (
                    name, category, description, price, unit_cost, stock_quantity, status,
                    supplier_id, reorder_threshold, reorder_quantity, last_restocked_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    payload["name"].strip(),
                    payload["category"].strip(),
                    payload.get("description"),
                    payload["price"],
                    payload.get("unit_cost", 0),
                    payload["stock_quantity"],
                    status,
                    payload.get("supplier_id"),
                    payload.get("reorder_threshold", 10),
                    payload.get("reorder_quantity", 50),
                ),
            )
            db.commit()
        except sqlite3.IntegrityError as exc:
            db.rollback()
            abort(400, description=f"Could not create product: {exc}")

        row = db.execute(
            """
            SELECT id, name, category, description, price, unit_cost, stock_quantity,
                   status, supplier_id, reorder_threshold, reorder_quantity, last_restocked_at
            FROM products WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return jsonify(_row_to_dict(row)), 201


@products_blueprint.put("/<int:product_id>")
def update_product(product_id):
    """PUT /api/inventory/products/<id>
    Re-derives status from stock_quantity. Stamps last_restocked_at to now()
    only if stock_quantity increased relative to the stored value — if your
    team prefers an explicit action instead, replace this with a dedicated
    POST /<id>/restock endpoint.
    """
    if (err := _require_admin()) is not None:
        return err

    payload = request.get_json(silent=True) or {}
    _validate_payload(payload)

    with closing(get_connection()) as db:
        existing = db.execute(
            "SELECT stock_quantity FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if existing is None:
            abort(404, description="Product not found")

        status = _derive_status(payload["stock_quantity"])
        restocked = payload["stock_quantity"] > existing["stock_quantity"]

        try:
            if restocked:
                db.execute(
                    """
                    UPDATE products
                    SET name = ?, category = ?, description = ?, price = ?, unit_cost = ?,
                        stock_quantity = ?, status = ?, supplier_id = ?,
                        reorder_threshold = ?, reorder_quantity = ?,
                        last_restocked_at = datetime('now')
                    WHERE id = ?
                    """,
                    (
                        payload["name"].strip(),
                        payload["category"].strip(),
                        payload.get("description"),
                        payload["price"],
                        payload.get("unit_cost", 0),
                        payload["stock_quantity"],
                        status,
                        payload.get("supplier_id"),
                        payload.get("reorder_threshold", 10),
                        payload.get("reorder_quantity", 50),
                        product_id,
                    ),
                )
            else:
                db.execute(
                    """
                    UPDATE products
                    SET name = ?, category = ?, description = ?, price = ?, unit_cost = ?,
                        stock_quantity = ?, status = ?, supplier_id = ?,
                        reorder_threshold = ?, reorder_quantity = ?
                    WHERE id = ?
                    """,
                    (
                        payload["name"].strip(),
                        payload["category"].strip(),
                        payload.get("description"),
                        payload["price"],
                        payload.get("unit_cost", 0),
                        payload["stock_quantity"],
                        status,
                        payload.get("supplier_id"),
                        payload.get("reorder_threshold", 10),
                        payload.get("reorder_quantity", 50),
                        product_id,
                    ),
                )
            db.commit()
        except sqlite3.IntegrityError as exc:
            db.rollback()
            abort(400, description=f"Could not update product: {exc}")

        row = db.execute(
            """
            SELECT id, name, category, description, price, unit_cost, stock_quantity,
                   status, supplier_id, reorder_threshold, reorder_quantity, last_restocked_at
            FROM products WHERE id = ?
            """,
            (product_id,),
        ).fetchone()

    return jsonify(_row_to_dict(row))


@products_blueprint.delete("/<int:product_id>")
def delete_product(product_id):
    """DELETE /api/inventory/products/<id>"""
    if (err := _require_admin()) is not None:
        return err

    with closing(get_connection()) as db:
        existing = db.execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone()
        if existing is None:
            abort(404, description="Product not found")

        db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        db.commit()

    return "", 204