"""Inventory access follows the authenticated role, regardless of email."""

import importlib
import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize("role,email,status", [
    ("customer", None, 403),
    ("customer", "customer@example.test", 403),
    ("customer", "admin@asd.com", 403),
    ("customer", " ADMIN@ASD.COM ", 403),
    ("admin", "admin@asd.com", 200),
    ("admin", "another-admin@example.test", 200),
])
def test_inventory_access_uses_authenticated_role(monkeypatch, role, email, status):
    backend = Path(__file__).resolve().parents[1] / "backend"
    monkeypatch.syspath_prepend(str(backend))
    spec = importlib.util.spec_from_file_location("inventory_auth_regression", backend / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class SessionResponse:
        status_code = 200

        def json(self):
            return {"authenticated": True, "user": {"id": 2, "role": role, "email": email}}

    database_calls = []

    def database_request(*args, **kwargs):
        database_calls.append((args, kwargs))
        return []

    monkeypatch.setattr(importlib.import_module("routes.products"), "database_request", database_request)
    monkeypatch.setattr(module.requests, "get", lambda *args, **kwargs: SessionResponse())
    client = module.create_app().test_client()
    client.set_cookie("ethan_session", "valid-customer-session", domain="localhost")
    response = client.get("/api/inventory/products")
    assert response.status_code == status
    if status == 403:
        assert response.json == {"error": "Administrator access required."}
        assert database_calls == []
    else:
        assert response.json == []
        assert len(database_calls) == 1
