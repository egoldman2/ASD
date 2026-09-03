import sys
from pathlib import Path
from contextlib import closing

from flask import Blueprint, request, jsonify, abort
import sqlite3

sys.path.append(str(Path(__file__).resolve().parents[2] / "database"))
from ryan_init_db import get_connection 

suppliers_blueprint = Blueprint("suppliers_blueprint", __name__, url_prefix="/api/inventory/suppliers")


def _row_to_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "contact_name": row["contact_name"],
        "email": row["email"],
        "phone": row["phone"],
        "address": row["address"],
        "created_at": row["created_at"],
    }


@suppliers_blueprint.get("")
def list_suppliers():
    """GET /api/inventory/suppliers?search=<name>"""
    search = request.args.get("search", "").strip()

    with closing(get_connection()) as db:
        if search:
            rows = db.execute(
                """
                SELECT id, name, contact_name, email, phone, address, created_at
                FROM suppliers
                WHERE LOWER(name) LIKE LOWER(?)
                ORDER BY name ASC
                """,
                (f"%{search}%",),
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT id, name, contact_name, email, phone, address, created_at
                FROM suppliers
                ORDER BY name ASC
                """
            ).fetchall()

    return jsonify([_row_to_dict(r) for r in rows])


@suppliers_blueprint.get("/<int:supplier_id>")
def get_supplier(supplier_id):
    """GET /api/inventory/suppliers/<id>"""
    with closing(get_connection()) as db:
        row = db.execute(
            """
            SELECT id, name, contact_name, email, phone, address, created_at
            FROM suppliers WHERE id = ?
            """,
            (supplier_id,),
        ).fetchone()

    if row is None:
        abort(404, description="Supplier not found")

    return jsonify(_row_to_dict(row))


@suppliers_blueprint.post("")
def create_supplier():
    """POST /api/inventory/suppliers
    Body: { name, contact_name?, email?, phone?, address? }
    """
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()

    if not name:
        abort(400, description="Supplier name is required")

    with closing(get_connection()) as db:
        try:
            cursor = db.execute(
                """
                INSERT INTO suppliers (name, contact_name, email, phone, address)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    name,
                    payload.get("contact_name"),
                    payload.get("email"),
                    payload.get("phone"),
                    payload.get("address"),
                ),
            )
            db.commit()
        except sqlite3.IntegrityError as exc:
            db.rollback()
            abort(400, description=f"Could not create supplier: {exc}")

        row = db.execute(
            """
            SELECT id, name, contact_name, email, phone, address, created_at
            FROM suppliers WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return jsonify(_row_to_dict(row)), 201


@suppliers_blueprint.put("/<int:supplier_id>")
def update_supplier(supplier_id):
    """PUT /api/inventory/suppliers/<id>
    Body: { name, contact_name?, email?, phone?, address? }
    """
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()

    if not name:
        abort(400, description="Supplier name is required")

    with closing(get_connection()) as db:
        existing = db.execute("SELECT id FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
        if existing is None:
            abort(404, description="Supplier not found")

        try:
            db.execute(
                """
                UPDATE suppliers
                SET name = ?, contact_name = ?, email = ?, phone = ?, address = ?
                WHERE id = ?
                """,
                (
                    name,
                    payload.get("contact_name"),
                    payload.get("email"),
                    payload.get("phone"),
                    payload.get("address"),
                    supplier_id,
                ),
            )
            db.commit()
        except sqlite3.IntegrityError as exc:
            db.rollback()
            abort(400, description=f"Could not update supplier: {exc}")

        row = db.execute(
            """
            SELECT id, name, contact_name, email, phone, address, created_at
            FROM suppliers WHERE id = ?
            """,
            (supplier_id,),
        ).fetchone()

    return jsonify(_row_to_dict(row))


@suppliers_blueprint.delete("/<int:supplier_id>")
def delete_supplier(supplier_id):
    """DELETE /api/inventory/suppliers/<id>
    Products referencing this supplier have supplier_id set to NULL
    automatically via ON DELETE SET NULL in the schema.
    """
    with closing(get_connection()) as db:
        existing = db.execute("SELECT id FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
        if existing is None:
            abort(404, description="Supplier not found")

        db.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
        db.commit()

    return "", 204