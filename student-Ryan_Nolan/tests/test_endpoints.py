"""Release 2 post-commit CI/CD endpoint tests - Ryan Nolan (Inventory Management).

Endpoint 1: GET  /api/inventory/products   (list products)
Endpoint 2: POST /api/inventory/products   (create product)

Fixtures (client, database_api) come from conftest.py in this folder.
"""

PRODUCTS_URL = "/api/inventory/products"

VALID_PRODUCT = {
    "name": "CI Endpoint Widget",
    "category": "Widgets",
    "price": 9.99,
    "unit_cost": 4.50,
    "stock_quantity": 25,
    "reorder_threshold": 5,
    "reorder_quantity": 50,
}


# ---------- Endpoint 1: GET /api/inventory/products ----------

def test_endpoint1_list_products_returns_seeded_records(client):
    resp = client.get(PRODUCTS_URL)

    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) >= 10


def test_endpoint1_list_products_has_inventory_fields(client):
    resp = client.get(PRODUCTS_URL)

    assert resp.status_code == 200
    first = resp.get_json()[0]
    for field in ("id", "name", "stock_quantity", "reorder_threshold"):
        assert field in first


def test_endpoint1_low_stock_filter_only_returns_low_stock(client):
    resp = client.get(f"{PRODUCTS_URL}?filter=low_stock")

    assert resp.status_code == 200
    for product in resp.get_json():
        assert product["stock_quantity"] <= product["reorder_threshold"]


# ---------- Endpoint 2: POST /api/inventory/products ----------

def test_endpoint2_create_product_returns_201_and_persists(client):
    resp = client.post(PRODUCTS_URL, json=VALID_PRODUCT)

    assert resp.status_code == 201
    created = resp.get_json()
    assert "id" in created
    assert created["status"] == "active"

    fetched = client.get(f"{PRODUCTS_URL}/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.get_json()["name"] == VALID_PRODUCT["name"]


def test_endpoint2_create_product_missing_name_returns_400(client):
    payload = {k: v for k, v in VALID_PRODUCT.items() if k != "name"}
    resp = client.post(PRODUCTS_URL, json=payload)

    assert resp.status_code == 400


def test_endpoint2_create_product_negative_price_returns_400(client):
    resp = client.post(PRODUCTS_URL, json={**VALID_PRODUCT, "price": -5})

    assert resp.status_code == 400