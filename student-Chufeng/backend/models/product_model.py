from contextlib import closing

from .database import get_database_connection


PRODUCT_COLUMNS = (
    "id, name, category, description, price, stock_quantity, status"
)


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
