"""Focused tests for Chufeng's read-only catalogue tool logic."""

import requests

from mcp_server.tools import chufeng_catalogue as catalogue


PRODUCTS = [
    {
        "id": 1,
        "name": "Mechanical Keyboard",
        "category": "Peripherals",
        "description": "Compact keyboard",
        "price": 129.95,
        "unit_cost": 60.0,
        "stock_quantity": 8,
        "status": "active",
        "supplier_name": "Key Supply",
        "reorder_threshold": 3,
    },
    {
        "id": 2,
        "name": "Office Mouse",
        "category": "Peripherals",
        "description": "Wireless mouse",
        "price": 39.5,
        "unit_cost": 15.0,
        "stock_quantity": 1,
        "status": "active",
        "supplier_name": "Mouse Supply",
        "reorder_threshold": 4,
    },
]


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def _fake_product_api(monkeypatch):
    calls = []

    def fake_get(url, *, params=None, timeout=None):
        calls.append({"url": url, "params": params, "timeout": timeout})
        if url.endswith("/products"):
            return FakeResponse(PRODUCTS)
        product_id = int(url.rsplit("/", 1)[-1])
        product = next((item for item in PRODUCTS if item["id"] == product_id), None)
        return FakeResponse(product or {"error": "not found"}, 200 if product else 404)

    monkeypatch.setattr(catalogue.requests, "get", fake_get)
    return calls


def test_search_products_filters_results_and_private_fields(monkeypatch):
    calls = _fake_product_api(monkeypatch)

    response = catalogue.search_products(
        query="keyboard",
        category="peripherals",
        max_price=130,
        limit=1,
    )

    assert response["success"] is True
    assert response["result"]["count"] == 1
    assert response["result"]["products"][0]["id"] == 1
    assert "unit_cost" not in response["result"]["products"][0]
    assert "reorder_threshold" not in response["result"]["products"][0]
    assert calls[0]["params"] == {"search": "keyboard"}
    assert calls[0]["timeout"] == 10.0
    assert response["metadata"]["read_only"] is True


def test_search_products_rejects_invalid_limit_without_calling_api(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("The product API must not be called for invalid input")

    monkeypatch.setattr(catalogue.requests, "get", fail_if_called)

    response = catalogue.search_products(limit=0)

    assert response["success"] is False
    assert response["error"]["code"] == "INVALID_ARGUMENT"
    assert response["error"]["details"]["field"] == "limit"


def test_get_product_details_maps_not_found(monkeypatch):
    _fake_product_api(monkeypatch)

    response = catalogue.get_product_details(999)

    assert response["success"] is False
    assert response["error"]["code"] == "RECORD_NOT_FOUND"


def test_check_product_stock_reports_shortfall(monkeypatch):
    _fake_product_api(monkeypatch)

    response = catalogue.check_product_stock(2, quantity=3)

    assert response["success"] is True
    assert response["result"]["available"] is False
    assert response["result"]["available_quantity"] == 1
    assert response["result"]["shortfall"] == 2


def test_calculate_cart_summary_combines_duplicate_lines(monkeypatch):
    calls = _fake_product_api(monkeypatch)

    response = catalogue.calculate_cart_summary(
        [
            {"product_id": 1, "quantity": 1},
            {"product_id": 1, "quantity": 2},
            {"product_id": 2, "quantity": 1},
        ]
    )

    assert response["success"] is True
    assert response["result"]["line_count"] == 2
    assert response["result"]["total_quantity"] == 4
    assert response["result"]["total"] == 429.35
    assert response["result"]["all_items_available"] is True
    assert len(calls) == 2


def test_product_service_timeout_is_safe(monkeypatch):
    def timeout(*args, **kwargs):
        raise requests.Timeout("private network detail")

    monkeypatch.setattr(catalogue.requests, "get", timeout)

    response = catalogue.get_product_details(1)

    assert response["success"] is False
    assert response["error"]["code"] == "UPSTREAM_UNAVAILABLE"
    assert "private network detail" not in str(response)
