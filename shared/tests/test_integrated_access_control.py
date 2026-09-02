import importlib
import sqlite3


def create_orders_database(path):
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            status TEXT NOT NULL,
            total REAL NOT NULL
        );
        CREATE TABLE order_items (
            item_id INTEGER PRIMARY KEY,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL
        );
        CREATE TABLE returns (
            return_id INTEGER PRIMARY KEY,
            order_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        INSERT INTO orders VALUES
            (1, 2, '2026-09-01', 'pending', 25.0),
            (2, 99, '2026-09-01', 'shipped', 50.0);
        INSERT INTO returns VALUES
            (1, 1, 'Damaged', 'requested', '2026-09-01'),
            (2, 2, 'Wrong item', 'approved', '2026-09-01');
        """
    )
    connection.commit()
    connection.close()


def build_client(monkeypatch, tmp_path, user=None):
    application_module = importlib.import_module("app")
    order_routes = importlib.import_module(
        "student-Howard.backend.routes.order_routes"
    )
    database_path = tmp_path / "orders.db"
    create_orders_database(database_path)
    monkeypatch.setattr(order_routes, "DB", str(database_path))

    if user is not None:
        monkeypatch.setattr(
            application_module,
            "_authenticated_user",
            lambda: (user, None),
        )

    application = application_module.create_app()
    return application.test_client()


def add_session_cookie(client):
    client.set_cookie("localhost", "ethan_session", "verified-session")


def test_private_data_requires_login(monkeypatch, tmp_path):
    client = build_client(monkeypatch, tmp_path)

    assert client.get("/api/cart-items").status_code == 401
    assert client.get("/api/order-returns/orders").status_code == 401
    assert client.get("/api/order-returns/returns").status_code == 401


def test_customer_only_receives_owned_orders_and_returns(monkeypatch, tmp_path):
    client = build_client(
        monkeypatch,
        tmp_path,
        user={"id": 2, "role": "customer"},
    )
    add_session_cookie(client)

    orders = client.get("/api/order-returns/orders")
    returns = client.get("/api/order-returns/returns")

    assert orders.status_code == 200
    assert [order["order_id"] for order in orders.get_json()] == [1]
    assert returns.status_code == 200
    assert [item["return_id"] for item in returns.get_json()] == [1]
    assert client.get("/api/order-returns/orders/2").status_code == 404


def test_customer_cannot_change_order_status(monkeypatch, tmp_path):
    client = build_client(
        monkeypatch,
        tmp_path,
        user={"id": 2, "role": "customer"},
    )
    add_session_cookie(client)

    response = client.patch(
        "/api/order-returns/orders/1/status",
        json={"status": "shipped"},
        headers={"Origin": "http://localhost:8004"},
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "Administrator access required."


def test_admin_receives_all_orders_and_returns(monkeypatch, tmp_path):
    client = build_client(
        monkeypatch,
        tmp_path,
        user={"id": 1, "role": "admin"},
    )
    add_session_cookie(client)

    orders = client.get("/api/order-returns/orders")
    returns = client.get("/api/order-returns/returns")

    assert [order["order_id"] for order in orders.get_json()] == [1, 2]
    assert [item["return_id"] for item in returns.get_json()] == [1, 2]


def test_each_customer_has_an_independent_cart(monkeypatch, tmp_path):
    application_module = importlib.import_module("app")
    customer_cart = importlib.import_module("shared.customer_cart")
    monkeypatch.setattr(
        customer_cart,
        "CART_DATABASE_PATH",
        tmp_path / "customer_carts.db",
    )
    active_user = {"id": 2, "role": "customer"}
    monkeypatch.setattr(
        application_module,
        "_authenticated_user",
        lambda: (active_user, None),
    )
    client = application_module.create_app().test_client()
    add_session_cookie(client)

    added = client.post(
        "/api/cart-items",
        json={"product_id": 1, "quantity": 2},
        headers={"Origin": "http://localhost:8001"},
    )
    assert added.status_code == 201
    assert client.get("/api/cart-items").get_json()["count"] == 1

    active_user["id"] = 3
    other_customer_cart = client.get("/api/cart-items").get_json()
    assert other_customer_cart == {
        "count": 0,
        "items": [],
        "total": 0,
        "total_quantity": 0,
    }

    active_user["id"] = 2
    assert client.get("/api/cart-items").get_json()["items"][0]["quantity"] == 2
