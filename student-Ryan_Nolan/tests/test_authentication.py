"""A valid customer session is forbidden, rather than an auth-service outage."""

import importlib.util
from pathlib import Path


def test_customer_session_returns_403_without_accessing_inventory(monkeypatch):
    backend = Path(__file__).resolve().parents[1] / "backend"
    monkeypatch.syspath_prepend(str(backend))
    spec = importlib.util.spec_from_file_location("inventory_auth_regression", backend / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class SessionResponse:
        status_code = 200

        def json(self):
            return {"authenticated": True, "user": {"id": 2, "role": "customer"}}

    monkeypatch.setattr(module.requests, "get", lambda *args, **kwargs: SessionResponse())
    client = module.create_app().test_client()
    client.set_cookie("localhost", "ethan_session", "valid-customer-session")
    response = client.get("/api/inventory/products")
    assert response.status_code == 403
    assert response.json == {"error": "Administrator access required."}
