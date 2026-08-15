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


def test_ai_product_assistant_is_read_only(client, monkeypatch):
    ai_controller = import_module(
        "student-Chufeng.backend.controllers.ai_controller"
    )
    prompts = []

    def fake_ollama(prompt):
        prompts.append(prompt)
        return (
            "This balanced selection supports everyday listening, entertainment, "
            "and productive work."
        )

    monkeypatch.setattr(ai_controller, "_call_ollama", fake_ollama)
    products_before = client.get("/api/products").json["count"]
    cart_before = client.get("/api/cart-items").json

    response = client.post(
        "/api/ai/product-assistant",
        json={
            "message": (
                "I have a $500 budget. Can you recommend a combination "
                "of electronic products?"
            )
        },
    )

    assert response.status_code == 200
    assert response.json["model"] == "qwen2.5:0.5b"
    assert "$471.50" in response.json["answer"]
    assert set(response.json["workflow"]) == {"plan", "act", "observe", "adapt"}
    assert "Wireless Earbuds" in prompts[0]
    assert "Mechanical Keyboard" in prompts[0]
    assert "Fitness Watch" not in prompts[0]
    assert "backend selected the supplied product combination" in prompts[0]
    assert client.get("/api/products").json["count"] == products_before
    assert client.get("/api/cart-items").json == cart_before


def test_ai_product_assistant_requires_question(client):
    response = client.post(
        "/api/ai/product-assistant",
        json={"message": "   "},
    )

    assert response.status_code == 400
    assert response.json["error"] == "A product question is required."


def test_ai_product_assistant_handles_unavailable_model(client, monkeypatch):
    ai_controller = import_module(
        "student-Chufeng.backend.controllers.ai_controller"
    )

    def unavailable_ollama(_prompt):
        raise ai_controller.OllamaUnavailableError

    monkeypatch.setattr(ai_controller, "_call_ollama", unavailable_ollama)

    response = client.post(
        "/api/ai/product-assistant",
        json={"message": "Recommend an electronic product combination."},
    )

    assert response.status_code == 503
    assert response.json["error"] == "The AI assistant is currently unavailable."
