import logging
import sqlite3

from ..models import product_model


LOGGER = logging.getLogger(__name__)


def get_products(search_term=""):
    try:
        products = product_model.get_products(search_term.strip())
    except sqlite3.Error:
        LOGGER.exception("Unable to retrieve products")
        return {"error": "Unable to retrieve products."}, 500

    return {"count": len(products), "products": products}, 200
