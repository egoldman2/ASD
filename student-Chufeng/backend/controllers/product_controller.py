import logging
from ..models import product_model
from ..models.database import DatabaseAPIError


LOGGER = logging.getLogger(__name__)


def get_products(search_term=""):
    try:
        products = product_model.get_products(search_term.strip())
    except DatabaseAPIError:
        LOGGER.exception("Unable to retrieve products")
        return {"error": "Unable to retrieve products."}, 500

    return {"count": len(products), "products": products}, 200
