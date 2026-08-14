from contextlib import closing
from pathlib import Path
import sqlite3

from flask import Flask, jsonify, request


app = Flask(__name__)
DATABASE_PATH = Path(__file__).resolve().parent.parent / "database" / "products.db"


def get_database_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


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


@app.after_request
def allow_frontend_requests(response):
    response.headers["Access-Control-Allow-Origin"] = "http://localhost:8001"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


@app.get("/api/products")
def get_products():
    search_term = request.args.get("search", "").strip()

    try:
        with closing(get_database_connection()) as connection:
            if search_term:
                rows = connection.execute(
                    """
                    SELECT id, name, category, description, price, stock_quantity, status
                    FROM products
                    WHERE name LIKE ? COLLATE NOCASE
                    ORDER BY id
                    """,
                    (f"%{search_term}%",),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT id, name, category, description, price, stock_quantity, status
                    FROM products
                    ORDER BY id
                    """
                ).fetchall()
    except sqlite3.Error:
        app.logger.exception("Unable to retrieve products")
        return jsonify({"error": "Unable to retrieve products."}), 500

    products = [dict(row) for row in rows]
    return jsonify({"count": len(products), "products": products})


@app.post("/api/products")
def create_product():
    data = request.get_json(silent=True)
    product_data, validation_error = validate_product_data(data)

    if validation_error:
        return jsonify({"error": validation_error}), 400

    try:
        with closing(get_database_connection()) as connection:
            existing_product = connection.execute(
                """
                SELECT id
                FROM products
                WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))
                """,
                (product_data["name"],),
            ).fetchone()

            if existing_product is not None:
                return jsonify(
                    {"error": "A product with this name already exists."}
                ), 409

            cursor = connection.execute(
                """
                INSERT INTO products
                    (name, category, description, price, stock_quantity, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    product_data["name"],
                    product_data["category"],
                    product_data["description"],
                    product_data["price"],
                    product_data["stock_quantity"],
                    product_data["status"],
                ),
            )
            product = connection.execute(
                """
                SELECT id, name, category, description, price, stock_quantity, status
                FROM products
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
            connection.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "A product with this name already exists."}), 409
    except sqlite3.Error:
        app.logger.exception("Unable to create product")
        return jsonify({"error": "Unable to create product."}), 500

    return jsonify({"product": dict(product)}), 201


@app.put("/api/products/<int:product_id>")
def update_product(product_id):
    data = request.get_json(silent=True)
    product_data, validation_error = validate_product_data(data)

    if validation_error:
        return jsonify({"error": validation_error}), 400

    try:
        with closing(get_database_connection()) as connection:
            existing_product = connection.execute(
                "SELECT id FROM products WHERE id = ?",
                (product_id,),
            ).fetchone()

            if existing_product is None:
                return jsonify({"error": "Product not found."}), 404

            name_conflict = connection.execute(
                """
                SELECT id
                FROM products
                WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))
                  AND id != ?
                """,
                (product_data["name"], product_id),
            ).fetchone()

            if name_conflict is not None:
                return jsonify(
                    {"error": "A product with this name already exists."}
                ), 409

            connection.execute(
                """
                UPDATE products
                SET name = ?,
                    category = ?,
                    description = ?,
                    price = ?,
                    stock_quantity = ?,
                    status = ?
                WHERE id = ?
                """,
                (
                    product_data["name"],
                    product_data["category"],
                    product_data["description"],
                    product_data["price"],
                    product_data["stock_quantity"],
                    product_data["status"],
                    product_id,
                ),
            )
            product = connection.execute(
                """
                SELECT id, name, category, description, price, stock_quantity, status
                FROM products
                WHERE id = ?
                """,
                (product_id,),
            ).fetchone()
            connection.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "A product with this name already exists."}), 409
    except sqlite3.Error:
        app.logger.exception("Unable to update product")
        return jsonify({"error": "Unable to update product."}), 500

    return jsonify({"product": dict(product)})


@app.delete("/api/products/<int:product_id>")
def delete_product(product_id):
    try:
        with closing(get_database_connection()) as connection:
            product = connection.execute(
                "SELECT id, name FROM products WHERE id = ?",
                (product_id,),
            ).fetchone()

            if product is None:
                return jsonify({"error": "Product not found."}), 404

            connection.execute("DELETE FROM products WHERE id = ?", (product_id,))
            connection.commit()
    except sqlite3.Error:
        app.logger.exception("Unable to delete product")
        return jsonify({"error": "Unable to delete product."}), 500

    return jsonify(
        {
            "message": "Product deleted successfully.",
            "product": dict(product),
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True, use_reloader=False)
