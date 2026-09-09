import os
import sqlite3
from contextlib import closing
from pathlib import Path

from flask import Flask, jsonify, request

try:
    from .init_db import DATABASE_PATH as DEFAULT_DATABASE_PATH
    from .init_db import initialize_database
except ImportError:
    from init_db import DATABASE_PATH as DEFAULT_DATABASE_PATH
    from init_db import initialize_database


PRODUCT_COLUMNS = """
    p.id, p.name, p.category, p.description, p.price, p.unit_cost,
    p.stock_quantity, p.status, p.supplier_id, p.reorder_threshold,
    p.reorder_quantity, p.last_restocked_at, s.name AS supplier_name
"""
CART_COLUMNS = """
    ci.id, ci.product_id, ci.quantity, p.name, p.category, p.description,
    p.price, p.stock_quantity, p.status,
    ROUND(p.price * ci.quantity, 2) AS subtotal
"""
CUSTOMER_CART_COLUMNS = """
    ci.id, ci.user_id, ci.product_id, ci.quantity, p.name, p.category,
    p.description, p.price, p.stock_quantity, p.status,
    ROUND(p.price * ci.quantity, 2) AS subtotal
"""


def create_app(database_path=None):
    app = Flask(__name__)
    app.config["DATABASE_PATH"] = str(
        database_path or os.environ.get("DATABASE_PATH", DEFAULT_DATABASE_PATH)
    )
    initialize_database(app.config["DATABASE_PATH"])

    def connect():
        connection = sqlite3.connect(app.config["DATABASE_PATH"])
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def one_product(connection, product_id):
        return connection.execute(
            f"""SELECT {PRODUCT_COLUMNS}
                FROM products p LEFT JOIN suppliers s ON s.id = p.supplier_id
                WHERE p.id = ?""",
            (product_id,),
        ).fetchone()

    def one_cart_item(connection, item_id):
        return connection.execute(
            f"""SELECT {CART_COLUMNS}
                FROM cart_items ci JOIN products p ON p.id = ci.product_id
                WHERE ci.id = ?""",
            (item_id,),
        ).fetchone()

    @app.get("/health")
    def health():
        with closing(connect()) as connection:
            connection.execute("SELECT 1").fetchone()
        return jsonify({"status": "healthy", "service": "product-database-api"})

    @app.get("/api/database/products")
    def list_products():
        search = request.args.get("search", "").strip()
        stock_filter = request.args.get("filter", "all")
        conditions = []
        parameters = []
        if search:
            conditions.append("LOWER(p.name) LIKE LOWER(?)")
            parameters.append(f"%{search}%")
        if stock_filter == "in_stock":
            conditions.append("p.stock_quantity > p.reorder_threshold")
        elif stock_filter == "low_stock":
            conditions.append("p.stock_quantity > 0 AND p.stock_quantity <= p.reorder_threshold")
        elif stock_filter == "out_of_stock":
            conditions.append("p.stock_quantity <= 0")
        elif stock_filter == "needs_reorder":
            conditions.append("p.stock_quantity <= p.reorder_threshold")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        order = "p.name ASC" if stock_filter != "all" else "p.id ASC"
        with closing(connect()) as connection:
            rows = connection.execute(
                f"""SELECT {PRODUCT_COLUMNS}
                    FROM products p LEFT JOIN suppliers s ON s.id = p.supplier_id
                    {where} ORDER BY {order}""",
                parameters,
            ).fetchall()
        return jsonify([dict(row) for row in rows])

    @app.get("/api/database/products/<int:product_id>")
    def get_product(product_id):
        with closing(connect()) as connection:
            row = one_product(connection, product_id)
        if row is None:
            return jsonify({"error": "Product not found"}), 404
        return jsonify(dict(row))

    def validate_product(payload):
        if not (payload.get("name") or "").strip():
            return "Product name is required"
        if not (payload.get("category") or "").strip():
            return "Category is required"
        if not isinstance(payload.get("price"), (int, float)) or payload["price"] < 0:
            return "Price must be a non-negative number"
        if not isinstance(payload.get("stock_quantity"), int) or payload["stock_quantity"] < 0:
            return "Stock quantity must be a non-negative integer"
        for field, label in (("unit_cost", "Unit cost"), ("reorder_threshold", "Reorder threshold"), ("reorder_quantity", "Reorder quantity")):
            value = payload.get(field, 0)
            if not isinstance(value, (int, float)) or value < 0:
                return f"{label} must be a non-negative number"
        return None

    @app.post("/api/database/products")
    def create_product():
        payload = request.get_json(silent=True) or {}
        if error := validate_product(payload):
            return jsonify({"error": error}), 400
        status = "out_of_stock" if payload["stock_quantity"] == 0 else "active"
        try:
            with closing(connect()) as connection:
                cursor = connection.execute(
                    """INSERT INTO products
                       (name, category, description, price, unit_cost, stock_quantity,
                        status, supplier_id, reorder_threshold, reorder_quantity)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (payload["name"].strip(), payload["category"].strip(), payload.get("description"),
                     payload["price"], payload.get("unit_cost", 0), payload["stock_quantity"],
                     status, payload.get("supplier_id"), payload.get("reorder_threshold", 10),
                     payload.get("reorder_quantity", 50)),
                )
                connection.commit()
                row = one_product(connection, cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            return jsonify({"error": f"Could not create product: {exc}"}), 400
        return jsonify(dict(row)), 201

    @app.put("/api/database/products/<int:product_id>")
    def update_product(product_id):
        payload = request.get_json(silent=True) or {}
        if error := validate_product(payload):
            return jsonify({"error": error}), 400
        status = "out_of_stock" if payload["stock_quantity"] == 0 else "active"
        try:
            with closing(connect()) as connection:
                existing = connection.execute(
                    "SELECT stock_quantity FROM products WHERE id = ?", (product_id,)
                ).fetchone()
                if existing is None:
                    return jsonify({"error": "Product not found"}), 404
                restocked = payload["stock_quantity"] > existing["stock_quantity"]
                connection.execute(
                    """UPDATE products SET name=?, category=?, description=?, price=?, unit_cost=?,
                       stock_quantity=?, status=?, supplier_id=?, reorder_threshold=?, reorder_quantity=?,
                       last_restocked_at=CASE WHEN ? THEN datetime('now') ELSE last_restocked_at END
                       WHERE id=?""",
                    (payload["name"].strip(), payload["category"].strip(), payload.get("description"),
                     payload["price"], payload.get("unit_cost", 0), payload["stock_quantity"], status,
                     payload.get("supplier_id"), payload.get("reorder_threshold", 10),
                     payload.get("reorder_quantity", 50), restocked, product_id),
                )
                connection.commit()
                row = one_product(connection, product_id)
        except sqlite3.IntegrityError as exc:
            return jsonify({"error": f"Could not update product: {exc}"}), 400
        return jsonify(dict(row))

    @app.delete("/api/database/products/<int:product_id>")
    def delete_product(product_id):
        with closing(connect()) as connection:
            cursor = connection.execute("DELETE FROM products WHERE id = ?", (product_id,))
            if cursor.rowcount == 0:
                return jsonify({"error": "Product not found"}), 404
            connection.commit()
        return "", 204

    @app.get("/api/database/suppliers")
    def list_suppliers():
        search = request.args.get("search", "").strip()
        where = "WHERE LOWER(name) LIKE LOWER(?)" if search else ""
        parameters = (f"%{search}%",) if search else ()
        with closing(connect()) as connection:
            rows = connection.execute(
                f"SELECT id, name, contact_name, email, phone, address, created_at FROM suppliers {where} ORDER BY name",
                parameters,
            ).fetchall()
        return jsonify([dict(row) for row in rows])

    @app.get("/api/database/suppliers/<int:supplier_id>")
    def get_supplier(supplier_id):
        with closing(connect()) as connection:
            row = connection.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
        return (jsonify(dict(row)), 200) if row else (jsonify({"error": "Supplier not found"}), 404)

    @app.post("/api/database/suppliers")
    def create_supplier():
        payload = request.get_json(silent=True) or {}
        name = (payload.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Supplier name is required"}), 400
        with closing(connect()) as connection:
            cursor = connection.execute(
                "INSERT INTO suppliers (name, contact_name, email, phone, address) VALUES (?, ?, ?, ?, ?)",
                (name, payload.get("contact_name"), payload.get("email"), payload.get("phone"), payload.get("address")),
            )
            connection.commit()
            row = connection.execute("SELECT * FROM suppliers WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201

    @app.put("/api/database/suppliers/<int:supplier_id>")
    def update_supplier(supplier_id):
        payload = request.get_json(silent=True) or {}
        name = (payload.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Supplier name is required"}), 400
        with closing(connect()) as connection:
            cursor = connection.execute(
                "UPDATE suppliers SET name=?, contact_name=?, email=?, phone=?, address=? WHERE id=?",
                (name, payload.get("contact_name"), payload.get("email"), payload.get("phone"), payload.get("address"), supplier_id),
            )
            if cursor.rowcount == 0:
                return jsonify({"error": "Supplier not found"}), 404
            connection.commit()
            row = connection.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
        return jsonify(dict(row))

    @app.delete("/api/database/suppliers/<int:supplier_id>")
    def delete_supplier(supplier_id):
        with closing(connect()) as connection:
            cursor = connection.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
            if cursor.rowcount == 0:
                return jsonify({"error": "Supplier not found"}), 404
            connection.commit()
        return "", 204

    @app.get("/api/database/cart-items")
    def list_cart_items():
        with closing(connect()) as connection:
            rows = connection.execute(
                f"SELECT {CART_COLUMNS} FROM cart_items ci JOIN products p ON p.id=ci.product_id ORDER BY ci.id"
            ).fetchall()
        return jsonify([dict(row) for row in rows])

    @app.get("/api/database/cart-items/<int:item_id>")
    def get_cart_item(item_id):
        with closing(connect()) as connection:
            row = one_cart_item(connection, item_id)
        return (jsonify(dict(row)), 200) if row else (jsonify({"error": "Cart item not found"}), 404)

    @app.get("/api/database/cart-items/by-product/<int:product_id>")
    def get_cart_item_by_product(product_id):
        with closing(connect()) as connection:
            row = connection.execute(
                f"SELECT {CART_COLUMNS} FROM cart_items ci JOIN products p ON p.id=ci.product_id WHERE ci.product_id=?",
                (product_id,),
            ).fetchone()
        return (jsonify(dict(row)), 200) if row else (jsonify({"error": "Cart item not found"}), 404)

    @app.post("/api/database/cart-items")
    def create_cart_item():
        payload = request.get_json(silent=True) or {}
        try:
            with closing(connect()) as connection:
                cursor = connection.execute(
                    "INSERT INTO cart_items (product_id, quantity) VALUES (?, ?)",
                    (payload.get("product_id"), payload.get("quantity")),
                )
                connection.commit()
                row = one_cart_item(connection, cursor.lastrowid)
        except (sqlite3.IntegrityError, sqlite3.OperationalError) as exc:
            return jsonify({"error": f"Could not create cart item: {exc}"}), 400
        return jsonify(dict(row)), 201

    @app.put("/api/database/cart-items/<int:item_id>")
    def update_cart_item(item_id):
        payload = request.get_json(silent=True) or {}
        try:
            with closing(connect()) as connection:
                cursor = connection.execute("UPDATE cart_items SET quantity=? WHERE id=?", (payload.get("quantity"), item_id))
                if cursor.rowcount == 0:
                    return jsonify({"error": "Cart item not found"}), 404
                connection.commit()
                row = one_cart_item(connection, item_id)
        except sqlite3.IntegrityError as exc:
            return jsonify({"error": f"Could not update cart item: {exc}"}), 400
        return jsonify(dict(row))

    @app.delete("/api/database/cart-items/<int:item_id>")
    def delete_cart_item(item_id):
        with closing(connect()) as connection:
            cursor = connection.execute("DELETE FROM cart_items WHERE id=?", (item_id,))
            if cursor.rowcount == 0:
                return jsonify({"error": "Cart item not found"}), 404
            connection.commit()
        return "", 204

    def customer_cart_item(connection, item_id, user_id):
        return connection.execute(
            f"""SELECT {CUSTOMER_CART_COLUMNS}
                FROM customer_cart_items ci JOIN products p ON p.id=ci.product_id
                WHERE ci.id=? AND ci.user_id=?""",
            (item_id, user_id),
        ).fetchone()

    @app.get("/api/database/customer-cart-items")
    def list_customer_cart_items():
        user_id = request.args.get("user_id", type=int)
        if user_id is None:
            return jsonify({"error": "A valid user ID is required"}), 400
        with closing(connect()) as connection:
            rows = connection.execute(
                f"""SELECT {CUSTOMER_CART_COLUMNS}
                    FROM customer_cart_items ci JOIN products p ON p.id=ci.product_id
                    WHERE ci.user_id=? ORDER BY ci.id""",
                (user_id,),
            ).fetchall()
        return jsonify([dict(row) for row in rows])

    @app.get("/api/database/customer-cart-items/by-product/<int:product_id>")
    def get_customer_cart_item_by_product(product_id):
        user_id = request.args.get("user_id", type=int)
        with closing(connect()) as connection:
            row = connection.execute(
                f"""SELECT {CUSTOMER_CART_COLUMNS}
                    FROM customer_cart_items ci JOIN products p ON p.id=ci.product_id
                    WHERE ci.user_id=? AND ci.product_id=?""",
                (user_id, product_id),
            ).fetchone()
        return (jsonify(dict(row)), 200) if row else (jsonify({"error": "Cart item not found"}), 404)

    @app.post("/api/database/customer-cart-items")
    def create_customer_cart_item():
        payload = request.get_json(silent=True) or {}
        try:
            with closing(connect()) as connection:
                cursor = connection.execute(
                    "INSERT INTO customer_cart_items (user_id, product_id, quantity) VALUES (?, ?, ?)",
                    (payload.get("user_id"), payload.get("product_id"), payload.get("quantity")),
                )
                connection.commit()
                row = customer_cart_item(connection, cursor.lastrowid, payload.get("user_id"))
        except sqlite3.IntegrityError as exc:
            return jsonify({"error": f"Could not create cart item: {exc}"}), 400
        return jsonify(dict(row)), 201

    @app.put("/api/database/customer-cart-items/<int:item_id>")
    def update_customer_cart_item(item_id):
        payload = request.get_json(silent=True) or {}
        user_id = payload.get("user_id")
        try:
            with closing(connect()) as connection:
                cursor = connection.execute(
                    "UPDATE customer_cart_items SET quantity=? WHERE id=? AND user_id=?",
                    (payload.get("quantity"), item_id, user_id),
                )
                if cursor.rowcount == 0:
                    return jsonify({"error": "Cart item not found"}), 404
                connection.commit()
                row = customer_cart_item(connection, item_id, user_id)
        except sqlite3.IntegrityError as exc:
            return jsonify({"error": f"Could not update cart item: {exc}"}), 400
        return jsonify(dict(row))

    @app.delete("/api/database/customer-cart-items/<int:item_id>")
    def delete_customer_cart_item(item_id):
        user_id = request.args.get("user_id", type=int)
        with closing(connect()) as connection:
            row = customer_cart_item(connection, item_id, user_id)
            if row is None:
                return jsonify({"error": "Cart item not found"}), 404
            connection.execute(
                "DELETE FROM customer_cart_items WHERE id=? AND user_id=?", (item_id, user_id)
            )
            connection.commit()
        return jsonify(dict(row))

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(
        host=os.environ.get("APP_HOST", "0.0.0.0"),
        port=int(os.environ.get("APP_PORT", "6001")),
    )
