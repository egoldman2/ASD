import os
import sys
from importlib import import_module
from threading import Thread
import pytest
from pathlib import Path
from werkzeug.serving import make_server

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "database"))

TEST_DB_PATH = Path(__file__).resolve().parent / "test_products.db"


@pytest.fixture
def database_api(monkeypatch):
    # Discard leftover copy's, then create a fresh one
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    database_app = import_module("student-Chufeng.database.api").create_app(TEST_DB_PATH)
    server = make_server("127.0.0.1", 0, database_app)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv(
        "PRODUCT_DATABASE_API_URL",
        f"http://127.0.0.1:{server.server_port}/api/database",
    )
    yield TEST_DB_PATH
    server.shutdown()
    thread.join(timeout=5)

    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture
def client(database_api):

    from app import create_app
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as c:
        yield c

# ---------- Database ----------
def test_database_has_minimum_records(database_api):
    """Spec requires at least 10 records per table."""
    import requests

    products = requests.get(
        os.environ["PRODUCT_DATABASE_API_URL"] + "/products", timeout=5
    ).json()
    suppliers = requests.get(
        os.environ["PRODUCT_DATABASE_API_URL"] + "/suppliers", timeout=5
    ).json()
    assert len(products) >= 10
    assert len(suppliers) >= 5


# ---------- Read: Products ----------
def test_list_products(client):
    resp = client.get("/api/inventory/products")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) >= 10


def test_get_single_product(client):
    resp = client.get("/api/inventory/products/1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == 1
    assert "stock_quantity" in data


def test_get_missing_product_returns_404(client):
    resp = client.get("/api/inventory/products/99999")
    assert resp.status_code == 404


def test_search_products_by_name(client):
    resp = client.get("/api/inventory/products?search=a")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_filter_products_low_stock(client):
    resp = client.get("/api/inventory/products?filter=low_stock")
    assert resp.status_code == 200
    for product in resp.get_json():
        assert product["stock_quantity"] <= product["reorder_threshold"]


def test_filter_products_out_of_stock(client):
    resp = client.get("/api/inventory/products?filter=out_of_stock")
    assert resp.status_code == 200
    for product in resp.get_json():
        assert product["stock_quantity"] <= 0


# ---------- Read: Suppliers ----------
def test_list_suppliers(client):
    resp = client.get("/api/inventory/suppliers")
    assert resp.status_code == 200
    assert len(resp.get_json()) >= 5


def test_get_single_supplier(client):
    resp = client.get("/api/inventory/suppliers/1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == 1


def test_get_missing_supplier_returns_404(client):
    resp = client.get("/api/inventory/suppliers/99999")
    assert resp.status_code == 404


# ---------- Create ----------
def test_create_product(client):
    resp = client.post("/api/inventory/products", json={
        "name": "Test Widget",
        "category": "Widgets",
        "price": 9.99,
        "unit_cost": 4.50,
        "stock_quantity": 25,
        "reorder_threshold": 5,
        "reorder_quantity": 50,
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert "id" in data
    assert data["status"] == "active"


def test_create_product_missing_name_returns_400(client):
    resp = client.post("/api/inventory/products", json={
        "category": "Widgets",
        "price": 9.99,
        "stock_quantity": 10,
    })
    assert resp.status_code == 400


def test_create_product_negative_price_returns_400(client):
    resp = client.post("/api/inventory/products", json={
        "name": "Bad Widget",
        "category": "Widgets",
        "price": -5,
        "stock_quantity": 10,
    })
    assert resp.status_code == 400


def test_create_supplier(client):
    resp = client.post("/api/inventory/suppliers", json={
        "name": "Test Supplier Co",
        "contact_name": "Jane Doe",
        "email": "jane@testsupplier.com",
    })
    assert resp.status_code == 201
    assert "id" in resp.get_json()


def test_create_supplier_missing_name_returns_400(client):
    resp = client.post("/api/inventory/suppliers", json={"contact_name": "No Name"})
    assert resp.status_code == 400


# ---------- Update ----------
def test_update_product(client):
    resp = client.put("/api/inventory/products/1", json={
        "name": "Updated Widget",
        "category": "Widgets",
        "price": 12.50,
        "unit_cost": 5.00,
        "stock_quantity": 40,
        "reorder_threshold": 10,
        "reorder_quantity": 50,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["name"] == "Updated Widget"
    assert data["stock_quantity"] == 40


def test_update_product_sets_status_out_of_stock(client):
    resp = client.put("/api/inventory/products/1", json={
        "name": "Updated Widget",
        "category": "Widgets",
        "price": 12.50,
        "stock_quantity": 0,
        "reorder_threshold": 10,
        "reorder_quantity": 50,
    })
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "out_of_stock"


def test_update_missing_product_returns_404(client):
    resp = client.put("/api/inventory/products/99999", json={
        "name": "Ghost",
        "category": "None",
        "price": 1,
        "stock_quantity": 1,
    })
    assert resp.status_code == 404


def test_update_supplier(client):
    resp = client.put("/api/inventory/suppliers/1", json={
        "name": "Updated Supplier Co",
        "contact_name": "John Smith",
    })
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "Updated Supplier Co"


def test_update_missing_supplier_returns_404(client):
    resp = client.put("/api/inventory/suppliers/99999", json={"name": "Ghost Co"})
    assert resp.status_code == 404


# ---------- Delete ----------
def test_delete_product(client):
    create_resp = client.post("/api/inventory/products", json={
        "name": "Disposable Widget",
        "category": "Widgets",
        "price": 1.00,
        "stock_quantity": 1,
    })
    product_id = create_resp.get_json()["id"]

    delete_resp = client.delete(f"/api/inventory/products/{product_id}")
    assert delete_resp.status_code == 204

    get_resp = client.get(f"/api/inventory/products/{product_id}")
    assert get_resp.status_code == 404


def test_delete_missing_product_returns_404(client):
    resp = client.delete("/api/inventory/products/99999")
    assert resp.status_code == 404


def test_delete_supplier_nulls_product_supplier_id(client):
    supplier_resp = client.post("/api/inventory/suppliers", json={"name": "Temp Supplier"})
    supplier_id = supplier_resp.get_json()["id"]

    product_resp = client.post("/api/inventory/products", json={
        "name": "Linked Widget",
        "category": "Widgets",
        "price": 5.00,
        "stock_quantity": 10,
        "supplier_id": supplier_id,
    })
    product_id = product_resp.get_json()["id"]

    delete_resp = client.delete(f"/api/inventory/suppliers/{supplier_id}")
    assert delete_resp.status_code == 204

    updated_product = client.get(f"/api/inventory/products/{product_id}").get_json()
    assert updated_product["supplier_id"] is None


def test_delete_missing_supplier_returns_404(client):
    resp = client.delete("/api/inventory/suppliers/99999")
    assert resp.status_code == 404
