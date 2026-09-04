import os
from importlib import import_module

import requests
from flask import Flask, g, jsonify, request

ALLOWED_ORIGINS = {
    "http://localhost:8000",
    "http://localhost:8001",
    "http://localhost:8002",
    "http://localhost:8003",
    "http://localhost:8004",
    "http://localhost:8005",
}

AUTH_SERVICE_URL = os.environ.get(
    "AUTH_SERVICE_URL",
    "http://localhost:6002",
).rstrip("/")
AUTH_TIMEOUT_SECONDS = float(os.environ.get("AUTH_TIMEOUT_SECONDS", "5"))
AUTH_COOKIE_NAME = "ethan_session"
PROTECTED_API_PREFIXES = (
    "/api/cart-items",
    "/api/order-returns",
    "/api/inventory",
)
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _authentication_error(message, status_code):
    return jsonify({"error": message}), status_code


def _authenticated_user():
    session_cookie = request.cookies.get(AUTH_COOKIE_NAME)
    if not session_cookie:
        return None, _authentication_error("You must sign in.", 401)

    try:
        response = requests.get(
            f"{AUTH_SERVICE_URL}/api/session",
            cookies={AUTH_COOKIE_NAME: session_cookie},
            timeout=AUTH_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
    except requests.RequestException:
        return None, _authentication_error(
            "The authentication service is unavailable.",
            503,
        )

    if response.status_code == 401:
        return None, _authentication_error("You must sign in.", 401)
    if response.status_code != 200:
        return None, _authentication_error(
            "The authentication service is unavailable.",
            503,
        )

    try:
        payload = response.json()
    except ValueError:
        payload = None

    user = payload.get("user") if isinstance(payload, dict) else None
    role = user.get("role") if isinstance(user, dict) else None
    user_id = user.get("id") if isinstance(user, dict) else None
    authenticated = (
        payload.get("authenticated")
        if isinstance(payload, dict)
        else False
    )
    if (
        authenticated is not True
        or role not in {"admin", "customer"}
        or isinstance(user_id, bool)
        or not isinstance(user_id, int)
    ):
        return None, _authentication_error(
            "The authentication service returned an invalid session.",
            503,
        )

    return user, None


def create_app():
    app = Flask(__name__)
    product_routes = import_module(
        "student-Chufeng.backend.routes.product_routes"
    )
    customer_cart = import_module(
        "shared.customer_cart"
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
    app.register_blueprint(customer_cart.cart_blueprint)
    app.register_blueprint(ai_routes.ai_blueprint)
    app.register_blueprint(order_routes.order_blueprint)



    @app.before_request
    def protect_private_apis():
        if request.method == "OPTIONS":
            return "", 204

        if not request.path.startswith(PROTECTED_API_PREFIXES):
            return None

        # The original feature tests exercise their blueprints without the
        # integrated authentication service. Live and production requests do
        # not use this testing-only principal.
        if app.config.get("TESTING"):
            g.authenticated_user = {
                "id": 1,
                "email": "test-admin@asd.local",
                "full_name": "Test Administrator",
                "role": "admin",
            }
            return None

        if (
            request.method in MUTATING_METHODS
            and request.headers.get("Origin") not in ALLOWED_ORIGINS
        ):
            return _authentication_error(
                "A trusted website origin is required.",
                403,
            )

        user, failure = _authenticated_user()
        if failure is not None:
            return failure

        g.authenticated_user = user
        return None

    @app.after_request
    def allow_frontend_requests(response):
        origin = request.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers.add("Vary", "Origin")
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, HX-Request, HX-Target, HX-Current-URL, "
            "HX-Trigger, HX-Trigger-Name, HX-Boosted"
        )
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, PATCH, DELETE, OPTIONS"
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
