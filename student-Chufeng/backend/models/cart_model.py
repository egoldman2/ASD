from .database import DatabaseAPIError, database_request


def _optional_get(path):
    try:
        return database_request("GET", path)
    except DatabaseAPIError as exc:
        if exc.status_code == 404:
            return None
        raise


def get_cart_items():
    return database_request("GET", "cart-items")


def get_cart_item(cart_item_id):
    return _optional_get(f"cart-items/{cart_item_id}")


def get_cart_item_by_product(product_id):
    return _optional_get(f"cart-items/by-product/{product_id}")


def create_cart_item(product_id, quantity):
    return database_request(
        "POST", "cart-items", json={"product_id": product_id, "quantity": quantity}
    )


def update_cart_item(cart_item_id, quantity):
    try:
        return database_request(
            "PUT", f"cart-items/{cart_item_id}", json={"quantity": quantity}
        )
    except DatabaseAPIError as exc:
        if exc.status_code == 404:
            return None
        raise


def delete_cart_item(cart_item_id):
    try:
        database_request("DELETE", f"cart-items/{cart_item_id}")
        return True
    except DatabaseAPIError as exc:
        if exc.status_code == 404:
            return False
        raise
