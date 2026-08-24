import os
import sqlite3
import sys
import pytest

# Make the backend importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import app as flask_app  # noqa: E402


@pytest.fixture
def client():
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        yield c


# ---------- Database ----------
def test_database_has_minimum_records():
    """Spec requires at least 10 records per table."""
    db = os.path.join(os.path.dirname(__file__), "..", "database", "orders.db")
    conn = sqlite3.connect(db)
    for table in ("orders", "order_items", "returns"):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert count >= 10, f"{table} has only {count} records"
    conn.close()


# ---------- Read ----------
def test_list_orders(client):
    resp = client.get("/orders")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) >= 10


def test_get_single_order_with_items(client):
    resp = client.get("/orders/1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["order_id"] == 1
    assert "items" in data


def test_get_missing_order_returns_404(client):
    resp = client.get("/orders/99999")
    assert resp.status_code == 404


def test_list_returns(client):
    resp = client.get("/returns")
    assert resp.status_code == 200
    assert len(resp.get_json()) >= 10


# ---------- Create ----------
def test_create_order(client):
    resp = client.post("/orders", json={
        "customer_id": 500,
        "order_date": "2026-08-24",
        "total": 42.0
    })
    assert resp.status_code == 201
    assert "order_id" in resp.get_json()


def test_create_return(client):
    resp = client.post("/returns", json={
        "order_id": 1,
        "reason": "test reason",
        "created_at": "2026-08-24"
    })
    assert resp.status_code == 201
    assert "return_id" in resp.get_json()


# ---------- Status change (separate from CRUD) ----------
def test_update_order_status(client):
    resp = client.patch("/orders/1/status", json={"status": "shipped"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "shipped"


def test_update_return_status(client):
    resp = client.patch("/returns/13/status", json={"status": "approved"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "approved"