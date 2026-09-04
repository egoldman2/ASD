import os
import sqlite3
import sys
import pytest
from flask import Flask

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "routes"))
from products import products_blueprint 
from suppliers import suppliers_blueprint 


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(products_blueprint)
    app.register_blueprint(suppliers_blueprint)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------- Database ----------
def test_database_has_minimum_records():
    """Spec requires at least 10 records per table."""
    db = os.path.join(os.path.dirname(__file__), "..", "database", "inventory.db")
    conn = sqlite3.connect(db)
    for table in ("products", "suppliers"):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert count >= 10, f"{table} has only {count} records"
    conn.close()


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
    assert len(resp.get_json()) >= 10


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