from importlib import import_module

# python -m pytest student-Chufeng/tests -q

def test_initialize_database(tmp_path):
    database_path = tmp_path / "catalogue.db"
    init_db = import_module("student-Chufeng.database.init_db")

    result = init_db.initialize_database(database_path)

    assert result == {
        "initialized": True,
        "products": 12,
        "cart_items": 10,
    }


def test_get_and_search_products(client):
    all_products = client.get("/api/products")
    search_result = client.get("/api/products?search=reader")

    assert all_products.status_code == 200
    assert all_products.json["count"] == 12
    assert search_result.status_code == 200
    assert search_result.json["count"] == 1
    assert search_result.json["products"][0]["name"] == "E-Reader"


def test_get_cart_and_total(client):
    response = client.get("/api/cart-items")

    assert response.status_code == 200
    assert response.json["count"] == 10
    assert response.json["total_quantity"] == 21
    assert response.json["total"] == 1928.94
    assert response.json["items"][0]["subtotal"] == 258.0


def test_add_cart_item(client):
    products = client.get("/api/products").json["products"]
    e_reader = next(product for product in products if product["name"] == "E-Reader")

    created = client.post(
        "/api/cart-items",
        json={"product_id": e_reader["id"], "quantity": 2},
    )
    added_again = client.post(
        "/api/cart-items",
        json={"product_id": e_reader["id"], "quantity": 1},
    )

    assert created.status_code == 201
    assert created.json["item"]["quantity"] == 2
    assert added_again.status_code == 200
    assert added_again.json["item"]["quantity"] == 3
    assert client.get("/api/cart-items").json["count"] == 11


def test_update_cart_quantity(client):
    item = client.get("/api/cart-items").json["items"][0]

    updated = client.put(
        f"/api/cart-items/{item['id']}",
        json={"quantity": 5},
    )
    over_stock = client.put(
        f"/api/cart-items/{item['id']}",
        json={"quantity": item["stock_quantity"] + 1},
    )

    assert updated.status_code == 200
    assert updated.json["item"]["quantity"] == 5
    assert over_stock.status_code == 409
    assert over_stock.json["error"] == "The requested quantity exceeds available stock."


def test_delete_cart_item(client):
    item = client.get("/api/cart-items").json["items"][0]

    deleted = client.delete(f"/api/cart-items/{item['id']}")
    deleted_again = client.delete(f"/api/cart-items/{item['id']}")

    assert deleted.status_code == 200
    assert deleted.json["item"]["name"] == item["name"]
    assert deleted_again.status_code == 404
    assert client.get("/api/cart-items").json["count"] == 9
