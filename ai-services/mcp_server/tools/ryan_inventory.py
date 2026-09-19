"""Read-only MCP tool logic for Ryan's inventory management feature.

Like the catalogue tools, these functions use the Product Database HTTP API
rather than opening SQLite.  ``server.py`` registers them as MCP tools.
Inventory tools are the only tools that expose replenishment fields
(reorder threshold/quantity, supplier link, last restocked, unit cost).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

import requests

from mcp_server.config import get_settings
from mcp_server.response import ToolErrorCode, error_response, success_response


GET_LOW_STOCK_ITEMS = "ryan_get_low_stock_items"
GET_PRODUCT_INVENTORY = "ryan_get_product_inventory"
GET_SUPPLIER_DETAILS = "ryan_get_supplier_details"
CALCULATE_RESTOCK_ORDER = "ryan_calculate_restock_order"

MAX_LOW_STOCK_RESULTS = 50
MAX_SUPPLIER_PRODUCTS = 50


class InventoryToolError(Exception):
    """Expected, user-safe failure raised while executing an inventory tool."""

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


def _invalid(message: str, **details: Any) -> InventoryToolError:
    return InventoryToolError(
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


def _upstream_error(message: str, **details: Any) -> InventoryToolError:
    return InventoryToolError(
        ToolErrorCode.UPSTREAM_ERROR,
        message,
        details=details or None,
    )


def _error_payload(tool: str, error: InventoryToolError) -> dict[str, Any]:
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
        "The inventory tool could not complete the request.",
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
        raise InventoryToolError(
            ToolErrorCode.UPSTREAM_UNAVAILABLE,
            "The inventory data service is currently unavailable.",
        ) from exc
    except requests.RequestException as exc:
        raise _upstream_error("The inventory data service request failed.") from exc

    if response.status_code == 404:
        raise InventoryToolError(
            ToolErrorCode.RECORD_NOT_FOUND,
            "The requested record was not found.",
        )
    if not 200 <= response.status_code < 300:
        raise _upstream_error(
            "The inventory data service returned an error.",
            status_code=response.status_code,
        )
    try:
        return response.json()
    except ValueError as exc:
        raise _upstream_error(
            "The inventory data service returned invalid JSON."
        ) from exc


def _int_field(record: dict[str, Any], field: str) -> int:
    value = record.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _upstream_error(f"The inventory data service returned an invalid {field}.")
    return value


def _money(value: Any) -> float:
    """Convert an upstream money value to a 2-decimal float."""

    if isinstance(value, bool):
        raise _upstream_error("The inventory data service returned an invalid price.")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise _upstream_error(
            "The inventory data service returned an invalid price."
        ) from exc
    if not amount.is_finite() or amount < 0:
        raise _upstream_error("The inventory data service returned an invalid price.")
    return float(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _inventory_product(product: Any) -> dict[str, Any]:
    """Return the inventory view of a product. unit_cost is never included."""

    if not isinstance(product, dict):
        raise _upstream_error("The inventory data service returned an invalid product.")

    stock = _int_field(product, "stock_quantity")
    threshold = _int_field(product, "reorder_threshold")
    reorder_quantity = _int_field(product, "reorder_quantity")
    supplier_id = product.get("supplier_id")
    if supplier_id is not None and (
        isinstance(supplier_id, bool) or not isinstance(supplier_id, int)
    ):
        raise _upstream_error(
            "The inventory data service returned an invalid supplier_id."
        )

    return {
        "id": _int_field(product, "id"),
        "name": str(product.get("name") or ""),
        "category": str(product.get("category") or ""),
        "status": str(product.get("status") or "unknown"),
        "stock_quantity": stock,
        "reorder_threshold": threshold,
        "reorder_quantity": reorder_quantity,
        "needs_reorder": stock <= threshold,
        "supplier_id": supplier_id,
        "supplier_name": product.get("supplier_name"),
        "last_restocked_at": product.get("last_restocked_at"),
    }


def _public_supplier(supplier: Any) -> dict[str, Any]:
    if not isinstance(supplier, dict):
        raise _upstream_error("The inventory data service returned an invalid supplier.")
    return {
        "id": _int_field(supplier, "id"),
        "name": str(supplier.get("name") or ""),
        "contact_name": supplier.get("contact_name"),
        "email": supplier.get("email"),
        "phone": supplier.get("phone"),
        "address": supplier.get("address"),
        "created_at": supplier.get("created_at"),
    }


def _get_product_row(product_id: int) -> dict[str, Any]:
    payload = _request_json(f"products/{product_id}")
    if not isinstance(payload, dict):
        raise _upstream_error("The inventory data service returned an invalid product.")
    return payload


def get_low_stock_items(limit: int = 20) -> dict[str, Any]:
    """List products at or below their reorder threshold."""

    try:
        validated_limit = _positive_integer(
            limit, "limit", maximum=MAX_LOW_STOCK_RESULTS
        )
        payload = _request_json("products", params={"filter": "needs_reorder"})
        if not isinstance(payload, list):
            raise _upstream_error(
                "The inventory data service returned an invalid product list."
            )

        products = [_inventory_product(product) for product in payload]
        products.sort(key=lambda p: p["stock_quantity"] - p["reorder_threshold"])
        matched_count = len(products)
        products = products[:validated_limit]
        return success_response(
            GET_LOW_STOCK_ITEMS,
            {"products": products, "count": len(products)},
            metadata={
                "matched_count": matched_count,
                "limit": validated_limit,
                "read_only": True,
            },
        )
    except InventoryToolError as exc:
        return _error_payload(GET_LOW_STOCK_ITEMS, exc)
    except Exception:
        return _unexpected_error(GET_LOW_STOCK_ITEMS)


def get_product_inventory(product_id: int) -> dict[str, Any]:
    """Return replenishment details for one product."""

    try:
        validated_id = _positive_integer(product_id, "product_id")
        product = _inventory_product(_get_product_row(validated_id))
        return success_response(
            GET_PRODUCT_INVENTORY,
            {"product": product},
            metadata={"read_only": True},
        )
    except InventoryToolError as exc:
        return _error_payload(GET_PRODUCT_INVENTORY, exc)
    except Exception:
        return _unexpected_error(GET_PRODUCT_INVENTORY)


def get_supplier_details(supplier_id: int) -> dict[str, Any]:
    """Return one supplier and the products they supply."""

    try:
        validated_id = _positive_integer(supplier_id, "supplier_id")
        supplier = _public_supplier(_request_json(f"suppliers/{validated_id}"))

        payload = _request_json("products")
        if not isinstance(payload, list):
            raise _upstream_error(
                "The inventory data service returned an invalid product list."
            )
        supplied = [
            _inventory_product(product)
            for product in payload
            if isinstance(product, dict) and product.get("supplier_id") == validated_id
        ]
        matched_count = len(supplied)
        supplied = supplied[:MAX_SUPPLIER_PRODUCTS]
        return success_response(
            GET_SUPPLIER_DETAILS,
            {
                "supplier": supplier,
                "products": supplied,
                "product_count": len(supplied),
            },
            metadata={
                "matched_count": matched_count,
                "limit": MAX_SUPPLIER_PRODUCTS,
                "read_only": True,
            },
        )
    except InventoryToolError as exc:
        return _error_payload(GET_SUPPLIER_DETAILS, exc)
    except Exception:
        return _unexpected_error(GET_SUPPLIER_DETAILS)


def calculate_restock_order(product_id: int) -> dict[str, Any]:
    """Compute a proposed restock order. Nothing is persisted or ordered."""

    try:
        validated_id = _positive_integer(product_id, "product_id")
        row = _get_product_row(validated_id)
        product = _inventory_product(row)

        stock = product["stock_quantity"]
        threshold = product["reorder_threshold"]
        order_quantity = product["reorder_quantity"]
        needs_reorder = product["needs_reorder"]

        suggested = order_quantity if needs_reorder else 0
        shortfall = max(threshold - stock, 0)
        unit_cost = _money(row.get("unit_cost", 0))
        estimated_cost = float(
            (Decimal(str(unit_cost)) * suggested).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )

        return success_response(
            CALCULATE_RESTOCK_ORDER,
            {
                "product_id": product["id"],
                "product_name": product["name"],
                "stock_quantity": stock,
                "reorder_threshold": threshold,
                "needs_reorder": needs_reorder,
                "shortfall_to_threshold": shortfall,
                "suggested_order_quantity": suggested,
                "projected_stock_after_order": stock + suggested,
                "unit_cost": unit_cost,
                "estimated_order_cost": estimated_cost,
                "currency": "AUD",
                "supplier_id": product["supplier_id"],
                "supplier_name": product["supplier_name"],
            },
            metadata={"read_only": True, "persisted": False},
        )
    except InventoryToolError as exc:
        return _error_payload(CALCULATE_RESTOCK_ORDER, exc)
    except Exception:
        return _unexpected_error(CALCULATE_RESTOCK_ORDER)