import os
from importlib import import_module
from flask import Flask, request

ALLOWED_ORIGINS = {
    "http://localhost:8000",
    "http://localhost:8001",
    "http://localhost:8002",
    "http://localhost:8003",
    "http://localhost:8004",
    "http://localhost:8005",
}


def create_app():
    app = Flask(__name__)
    product_routes = import_module(
        "student-Chufeng.backend.routes.product_routes"
    )
    cart_routes = import_module(
        "student-Chufeng.backend.routes.cart_routes"
    )
    ai_routes = import_module(
        "student-Chufeng.backend.routes.ai_routes"
    )
    order_routes = import_module(
        "student-Howard.backend.routes.order_routes"
    )


    inventory_routes = import_module(
        "student-Ryan_Nolan.backend.routes.products"
    )
    supplier_routes = import_module(
        "student-Ryan_Nolan.backend.routes.suppliers"
    )
    assistant_routes = import_module(
        "student-Ryan_Nolan.backend.routes.assistant"
    )

    app.register_blueprint(inventory_routes.products_blueprint)
    app.register_blueprint(supplier_routes.suppliers_blueprint)
    app.register_blueprint(assistant_routes.assistant_blueprint)


    app.register_blueprint(product_routes.product_blueprint)
    app.register_blueprint(cart_routes.cart_blueprint)
    app.register_blueprint(ai_routes.ai_blueprint)
    app.register_blueprint(order_routes.order_blueprint)



    @app.after_request
    def allow_frontend_requests(response):
        origin = request.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, HX-Request, HX-Target, HX-Current-URL, "
            "HX-Trigger, HX-Trigger-Name, HX-Boosted"
        )
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, DELETE, OPTIONS"
        )
        return response

    return app


app = create_app()
if __name__ == "__main__":
    app.run(
        host=os.getenv("APP_HOST", "127.0.0.1"),
        port=int(os.getenv("APP_PORT", "5000")),
        debug=os.getenv("APP_DEBUG", "true").lower() == "true",
        use_reloader=False,
    )
