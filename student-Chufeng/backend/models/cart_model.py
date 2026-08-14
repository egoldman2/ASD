from contextlib import closing

from .database import get_database_connection


CART_ITEM_COLUMNS = """
    ci.id,
    ci.product_id,
    ci.quantity,
    p.name,
    p.category,
    p.description,
    p.price,
    p.stock_quantity,
    p.status,
    ROUND(p.price * ci.quantity, 2) AS subtotal
"""


def get_cart_items():
    with closing(get_database_connection()) as connection:
        rows = connection.execute(
            f"""
            SELECT {CART_ITEM_COLUMNS}
            FROM cart_items AS ci
            JOIN products AS p ON p.id = ci.product_id
            ORDER BY ci.id
            """
        ).fetchall()

    return [dict(row) for row in rows]


def get_cart_item(cart_item_id):
    with closing(get_database_connection()) as connection:
        row = connection.execute(
            f"""
            SELECT {CART_ITEM_COLUMNS}
            FROM cart_items AS ci
            JOIN products AS p ON p.id = ci.product_id
            WHERE ci.id = ?
            """,
            (cart_item_id,),
        ).fetchone()

    return dict(row) if row is not None else None


def get_cart_item_by_product(product_id):
    with closing(get_database_connection()) as connection:
        row = connection.execute(
            f"""
            SELECT {CART_ITEM_COLUMNS}
            FROM cart_items AS ci
            JOIN products AS p ON p.id = ci.product_id
            WHERE ci.product_id = ?
            """,
            (product_id,),
        ).fetchone()

    return dict(row) if row is not None else None


def create_cart_item(product_id, quantity):
    with closing(get_database_connection()) as connection:
        cursor = connection.execute(
            "INSERT INTO cart_items (product_id, quantity) VALUES (?, ?)",
            (product_id, quantity),
        )
        cart_item_id = cursor.lastrowid
        connection.commit()

    return get_cart_item(cart_item_id)


def update_cart_item(cart_item_id, quantity):
    with closing(get_database_connection()) as connection:
        cursor = connection.execute(
            "UPDATE cart_items SET quantity = ? WHERE id = ?",
            (quantity, cart_item_id),
        )

        if cursor.rowcount == 0:
            return None

        connection.commit()

    return get_cart_item(cart_item_id)


def delete_cart_item(cart_item_id):
    with closing(get_database_connection()) as connection:
        cursor = connection.execute(
            "DELETE FROM cart_items WHERE id = ?",
            (cart_item_id,),
        )

        if cursor.rowcount == 0:
            return False

        connection.commit()

    return True
