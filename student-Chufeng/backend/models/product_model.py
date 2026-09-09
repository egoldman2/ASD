from .database import DatabaseAPIError, database_request


def get_products(search_term=""):
    parameters = {"search": search_term} if search_term else None
    return database_request("GET", "products", params=parameters)


def get_product(product_id):
    try:
        return database_request("GET", f"products/{product_id}")
    except DatabaseAPIError as exc:
        if exc.status_code == 404:
            return None
        raise
