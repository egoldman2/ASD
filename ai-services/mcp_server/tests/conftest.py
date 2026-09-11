"""Test path setup for the shared MCP service package."""

from importlib import import_module
from pathlib import Path
import sys
from threading import Thread

import pytest
from werkzeug.serving import make_server


AI_SERVICES_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(AI_SERVICES_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICES_ROOT))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def product_database_path(tmp_path):
    """Create an isolated copy of Chufeng's seeded product database."""

    database_path = tmp_path / "mcp-products.db"
    init_db = import_module("student-Chufeng.database.init_db")
    init_db.initialize_database(database_path, reset=True)
    return database_path


@pytest.fixture
def live_product_database_api(product_database_path):
    """Run the real Product Database API on an available local port."""

    database_api = import_module("student-Chufeng.database.api")
    server = make_server(
        "127.0.0.1",
        0,
        database_api.create_app(product_database_path),
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api/database"
    finally:
        server.shutdown()
        thread.join(timeout=5)
