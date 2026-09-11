from importlib import import_module
from pathlib import Path
import sys
from threading import Thread

import pytest
from werkzeug.serving import make_server


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_SERVICES_ROOT = PROJECT_ROOT / "ai-services"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(AI_SERVICES_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICES_ROOT))


@pytest.fixture
def database_path(tmp_path):
    path = tmp_path / "products.db"
    init_db = import_module("student-Chufeng.database.init_db")
    init_db.initialize_database(path, reset=True)
    return path


@pytest.fixture
def database_api_url(database_path):
    database_api = import_module("student-Chufeng.database.api")
    server = make_server("127.0.0.1", 0, database_api.create_app(database_path))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api/database"
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.fixture
def client(database_api_url, monkeypatch):
    monkeypatch.setenv("PRODUCT_DATABASE_API_URL", database_api_url)

    application = import_module("app").app
    application.config.update(TESTING=True)

    with application.test_client() as test_client:
        yield test_client
