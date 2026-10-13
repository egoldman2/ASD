"""Shared pytest fixtures for Ryan Nolan's Inventory Management tests."""

import os
import sys
from importlib import import_module
from pathlib import Path
from threading import Thread

import pytest
from werkzeug.serving import make_server

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "database"))

TEST_DB_PATH = Path(__file__).resolve().parent / "test_products.db"


@pytest.fixture
def database_api(monkeypatch):
    """Start the database API on a free port against a fresh test database."""
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    database_app = import_module("student-Chufeng.database.api").create_app(TEST_DB_PATH)
    server = make_server("127.0.0.1", 0, database_app)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv(
        "PRODUCT_DATABASE_API_URL",
        f"http://127.0.0.1:{server.server_port}/api/database",
    )
    yield TEST_DB_PATH
    server.shutdown()
    thread.join(timeout=5)

    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture
def client(database_api):
    """Flask test client for the Inventory backend."""
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as c:
        yield c