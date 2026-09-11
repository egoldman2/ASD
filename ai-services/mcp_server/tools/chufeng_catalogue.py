"""Read-only MCP tool logic for Chufeng's product catalogue feature.

The functions in this module deliberately use the Product Database HTTP API
instead of opening the SQLite database.  ``server.py`` registers these
functions as MCP tools; keeping the transport adapter separate makes the
business rules straightforward to test.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

import requests

from mcp_server.config import get_settings
from mcp_server.response import ToolErrorCode, error_response, success_response


SEARCH_PRODUCTS = "chufeng_search_products"
GET_PRODUCT_DETAILS = "chufeng_get_product_details"
CHECK_PRODUCT_STOCK = "chufeng_check_product_stock"
CALCULATE_CART_SUMMARY = "chufeng_calculate_cart_summary"

MAX_QUERY_LENGTH = 100
MAX_CATEGORY_LENGTH = 100
MAX_RESULTS = 100
MAX_CART_LINES = 20
MAX_ITEM_QUANTITY = 99


class CatalogueToolError(Exception):
    """Expected, user-safe failure raised while executing a catalogue tool."""

    def __init__(
        self,
        code: ToolErrorCode,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def _invalid(message: str, **details: Any) -> CatalogueToolError:
    return CatalogueToolError(
        ToolErrorCode.INVALID_ARGUMENT,
        message,
        details=details or None,
    )


def _positive_integer(value: Any, field: str, *, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _invalid(f"{field} must be a positive integer.", field=field)
    if maximum is not None and value > maximum:
        raise _invalid(
            f"{field} must not exceed {maximum}.",
            field=field,
            maximum=maximum,
        )
    return value


def _optional_text(value: Any, field: str, maximum: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _invalid(f"{field} must be text.", field=field)
    cleaned = value.strip()
    if len(cleaned) > maximum:
        raise _invalid(
            f"{field} must not exceed {maximum} characters.",
            field=field,
            maximum=maximum,
        )
    return cleaned or None


def _money(value: Any, field: str = "price") -> Decimal:
    if isinstance(value, bool):
        raise _invalid(f"{field} must be a non-negative number.", field=field)
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise _invalid(f"{field} must be a non-negative number.", field=field) from exc
    if not amount.is_finite() or amount < 0:
        raise _invalid(f"{field} must be a non-negative number.", field=field)
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _error_payload(tool: str, error: CatalogueToolError) -> dict[str, Any]:
    return error_response(
        tool,
        error.code,
        error.message,
        details=error.details,
    )


def _unexpected_error(tool: str) -> dict[str, Any]:
    return error_response(
        tool,
        ToolErrorCode.INTERNAL_ERROR,
        "The catalogue tool could not complete the request.",
    )


def _request_json(path: str, *, params: dict[str, Any] | None = None) -> Any:
    settings = get_settings()
    url = f"{settings.product_database_api_url}/{path.lstrip('/')}"
    try:
        response = requests.get(
            url,
            params=params,
            timeout=settings.request_timeout_seconds,
        )
    except (requests.ConnectionError, requests.Timeout) as exc:
        raise CatalogueToolError(
            ToolErrorCode.UPSTREAM_UNAVAILABLE,
            "The product service is currently unavailable.",
        ) from exc
    except requests.RequestException as exc:
        raise CatalogueToolError(
            ToolErrorCode.UPSTREAM_ERROR,
            "The product service request failed.",
        ) from exc

    if response.status_code == 404:
        raise CatalogueToolError(
            ToolErrorCode.RECORD_NOT_FOUND,
            "The requested product was not found.",
        )
    if not 200 <= response.status_code < 300:
        raise CatalogueToolError(
            ToolErrorCode.UPSTREAM_ERROR,
            "The product service returned an error.",
            details={"status_code": response.status_code},
        )
    try:
        return response.json()
    except ValueError as exc:
        raise CatalogueToolError(
            ToolErrorCode.UPSTREAM_ERROR,
            "The product service returned invalid JSON.",
        ) from exc


def _public_product(product: Any) -> dict[str, Any]:
    if not isinstance(product, dict):
        raise CatalogueToolError(
            ToolErrorCode.UPSTREAM_ERROR,
            "The product service returned an invalid product record.",
        )

    product_id = product.get("id")
    stock_quantity = product.get("stock_quantity")
    if isinstance(product_id, bool) or not isinstance(product_id, int):
        raise CatalogueToolError(
            ToolErrorCode.UPSTREAM_ERROR,
            "The product service returned an invalid product ID.",
        )
    if isinstance(stock_quantity, bool) or not isinstance(stock_quantity, int):
        raise CatalogueToolError(
            ToolErrorCode.UPSTREAM_ERROR,
            "The product service returned an invalid stock quantity.",
        )

    try:
        price = _money(product.get("price"))
    except CatalogueToolError as exc:
        raise CatalogueToolError(
            ToolErrorCode.UPSTREAM_ERROR,
            "The product service returned an invalid product price.",
        ) from exc

    return {
        "id": product_id,
        "name": str(product.get("name") or ""),
        "category": str(product.get("category") or ""),
        "description": str(product.get("description") or ""),
        "price": float(price),
        "stock_quantity": stock_quantity,
        "status": str(product.get("status") or "unknown"),
        "supplier_name": product.get("supplier_name"),
    }


def _get_product(product_id: int) -> dict[str, Any]:
    return _public_product(_request_json(f"products/{product_id}"))


def search_products(
    query: str = "",
    category: str | None = None,
    max_price: float | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Search the catalogue without exposing private inventory fields."""

    try:
        cleaned_query = _optional_text(query, "query", MAX_QUERY_LENGTH) or ""
        cleaned_category = _optional_text(category, "category", MAX_CATEGORY_LENGTH)
        validated_limit = _positive_integer(limit, "limit", maximum=MAX_RESULTS)
        price_ceiling = None if max_price is None else _money(max_price, "max_price")

        payload = _request_json(
            "products",
            params={"search": cleaned_query} if cleaned_query else None,
        )
        if not isinstance(payload, list):
            raise CatalogueToolError(
                ToolErrorCode.UPSTREAM_ERROR,
                "The product service returned an invalid product list.",
            )

        products = [_public_product(product) for product in payload]
        if cleaned_category:
            expected = cleaned_category.casefold()
            products = [
                product
                for product in products
                if product["category"].casefold() == expected
            ]
        if price_ceiling is not None:
            products = [
                product
                for product in products
                if Decimal(str(product["price"])) <= price_ceiling
            ]

        matched_count = len(products)
        products = products[:validated_limit]
        return success_response(
            SEARCH_PRODUCTS,
            {"products": products, "count": len(products)},
            metadata={
                "matched_count": matched_count,
                "limit": validated_limit,
                "read_only": True,
            },
        )
    except CatalogueToolError as exc:
        return _error_payload(SEARCH_PRODUCTS, exc)
    except Exception:
        return _unexpected_error(SEARCH_PRODUCTS)


def get_product_details(product_id: int) -> dict[str, Any]:
    """Return customer-safe details for one product."""

    try:
        validated_id = _positive_integer(product_id, "product_id")
        product = _get_product(validated_id)
        return success_response(
            GET_PRODUCT_DETAILS,
            {"product": product},
            metadata={"read_only": True},
        )
    except CatalogueToolError as exc:
        return _error_payload(GET_PRODUCT_DETAILS, exc)
    except Exception:
        return _unexpected_error(GET_PRODUCT_DETAILS)


def check_product_stock(product_id: int, quantity: int = 1) -> dict[str, Any]:
    """Check whether a requested quantity is currently available."""

    try:
        validated_id = _positive_integer(product_id, "product_id")
        validated_quantity = _positive_integer(
            quantity,
            "quantity",
            maximum=MAX_ITEM_QUANTITY,
        )
        product = _get_product(validated_id)
        available_quantity = max(product["stock_quantity"], 0)
        available = (
            product["status"] == "active"
            and available_quantity >= validated_quantity
        )
        return success_response(
            CHECK_PRODUCT_STOCK,
            {
                "product_id": product["id"],
                "product_name": product["name"],
                "requested_quantity": validated_quantity,
                "available_quantity": available_quantity,
                "available": available,
                "shortfall": max(validated_quantity - available_quantity, 0),
            },
            metadata={"read_only": True},
        )
    except CatalogueToolError as exc:
        return _error_payload(CHECK_PRODUCT_STOCK, exc)
    except Exception:
        return _unexpected_error(CHECK_PRODUCT_STOCK)


def calculate_cart_summary(items: list[dict[str, int]]) -> dict[str, Any]:
    """Price and validate a proposed cart without changing persisted cart data."""

    try:
        if not isinstance(items, list) or not items:
            raise _invalid("items must be a non-empty list.", field="items")
        if len(items) > MAX_CART_LINES:
            raise _invalid(
                f"items must not contain more than {MAX_CART_LINES} lines.",
                field="items",
                maximum=MAX_CART_LINES,
            )

        quantities: dict[int, int] = {}
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise _invalid(
                    "Each cart item must be an object.",
                    field=f"items[{index}]",
                )
            product_id = _positive_integer(
                item.get("product_id"),
                f"items[{index}].product_id",
            )
            quantity = _positive_integer(
                item.get("quantity"),
                f"items[{index}].quantity",
                maximum=MAX_ITEM_QUANTITY,
            )
            combined = quantities.get(product_id, 0) + quantity
            if combined > MAX_ITEM_QUANTITY:
                raise _invalid(
                    f"Combined quantity for product {product_id} must not exceed "
                    f"{MAX_ITEM_QUANTITY}.",
                    field="items",
                    product_id=product_id,
                    maximum=MAX_ITEM_QUANTITY,
                )
            quantities[product_id] = combined

        lines = []
        total = Decimal("0.00")
        all_available = True
        for product_id, quantity in quantities.items():
            product = _get_product(product_id)
            unit_price = Decimal(str(product["price"]))
            subtotal = (unit_price * quantity).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
            available = (
                product["status"] == "active"
                and product["stock_quantity"] >= quantity
            )
            all_available = all_available and available
            total += subtotal
            lines.append(
                {
                    "product_id": product_id,
                    "product_name": product["name"],
                    "quantity": quantity,
                    "unit_price": float(unit_price),
                    "subtotal": float(subtotal),
                    "available": available,
                    "available_quantity": max(product["stock_quantity"], 0),
                }
            )

        total = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return success_response(
            CALCULATE_CART_SUMMARY,
            {
                "items": lines,
                "line_count": len(lines),
                "total_quantity": sum(quantities.values()),
                "total": float(total),
                "currency": "AUD",
                "all_items_available": all_available,
            },
            metadata={"read_only": True},
        )
    except CatalogueToolError as exc:
        return _error_payload(CALCULATE_CART_SUMMARY, exc)
    except Exception:
        return _unexpected_error(CALCULATE_CART_SUMMARY)
