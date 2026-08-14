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
    app.register_blueprint(product_routes.product_blueprint)

    @app.after_request
    def allow_frontend_requests(response):
        origin = request.headers.get("Origin")

        if origin in ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin

        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, DELETE, OPTIONS"
        )
        return response

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
