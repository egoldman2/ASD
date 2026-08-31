from importlib import import_module
from pathlib import Path
import sys

import pytest
from flask import Flask


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def database_path(tmp_path, monkeypatch):
    path = tmp_path / "support_tickets.db"
    init_db = import_module("student-Ethan Goldman.database.init_db")
    database = import_module("student-Ethan Goldman.backend.models.database")

    init_db.initialize_database(path, reset=True)
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    return path


@pytest.fixture
def client(database_path):
    application = Flask(__name__)
    ticket_routes = import_module(
        "student-Ethan Goldman.backend.routes.ticket_routes"
    )
    ticket_ui_routes = import_module(
        "student-Ethan Goldman.backend.routes.ticket_ui_routes"
    )
    ai_routes = import_module("student-Ethan Goldman.backend.routes.ai_routes")
    application.register_blueprint(ticket_routes.support_ticket_blueprint)
    application.register_blueprint(ticket_ui_routes.support_ticket_ui_blueprint)
    application.register_blueprint(ticket_ui_routes.support_customer_ui_blueprint)
    application.register_blueprint(ai_routes.support_ai_blueprint)
    application.register_blueprint(ai_routes.support_ai_ui_blueprint)
    application.config.update(TESTING=True)

    with application.test_client() as test_client:
        yield test_client
