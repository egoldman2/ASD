from contextlib import closing
from pathlib import Path
import sqlite3


DATABASE_PATH = Path(__file__).resolve().parents[2] / "database" / "products.db"
PRODUCT_COLUMNS = (
    "id, name, category, description, price, stock_quantity, status"
)


def get_database_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def get_products(search_term=""):
    with closing(get_database_connection()) as connection:
        if search_term:
            rows = connection.execute(
                f"""
                SELECT {PRODUCT_COLUMNS}
                FROM products
                WHERE name LIKE ? COLLATE NOCASE
                ORDER BY id
                """,
                (f"%{search_term}%",),
            ).fetchall()
        else:
            rows = connection.execute(
                f"""
                SELECT {PRODUCT_COLUMNS}
                FROM products
                ORDER BY id
                """
            ).fetchall()

    return [dict(row) for row in rows]


def get_product(product_id):
    with closing(get_database_connection()) as connection:
        row = connection.execute(
            f"SELECT {PRODUCT_COLUMNS} FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()

    return dict(row) if row is not None else None


def product_name_exists(name, exclude_id=None):
    query = "SELECT id FROM products WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))"
    parameters = [name]

    if exclude_id is not None:
        query += " AND id != ?"
        parameters.append(exclude_id)

    with closing(get_database_connection()) as connection:
        row = connection.execute(query, parameters).fetchone()

    return row is not None


def create_product(product_data):
    with closing(get_database_connection()) as connection:
        cursor = connection.execute(
            """
            INSERT INTO products
                (name, category, description, price, stock_quantity, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            _product_values(product_data),
        )
        product_id = cursor.lastrowid
        connection.commit()
        row = connection.execute(
            f"SELECT {PRODUCT_COLUMNS} FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()

    return dict(row)


def update_product(product_id, product_data):
    with closing(get_database_connection()) as connection:
        cursor = connection.execute(
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
            (*_product_values(product_data), product_id),
        )

        if cursor.rowcount == 0:
            return None

        connection.commit()
        row = connection.execute(
            f"SELECT {PRODUCT_COLUMNS} FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()

    return dict(row)


def delete_product(product_id):
    with closing(get_database_connection()) as connection:
        row = connection.execute(
            "SELECT id, name FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()

        if row is None:
            return None

        connection.execute("DELETE FROM products WHERE id = ?", (product_id,))
        connection.commit()

    return dict(row)


def _product_values(product_data):
    return (
        product_data["name"],
        product_data["category"],
        product_data["description"],
        product_data["price"],
        product_data["stock_quantity"],
        product_data["status"],
    )
