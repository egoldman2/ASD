from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module, util
import os
from pathlib import Path
import sys
from threading import Thread

import pytest
import requests
from werkzeug.serving import make_server


PROJECT_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

TRUSTED_ORIGIN = "http://localhost:8005"


class LiveServer:
    """Run a real Flask application over HTTP on an available local port."""

    def __init__(self, application):
        self.server = make_server("127.0.0.1", 0, application, threaded=True)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()


def load_file_module(name: str, path: Path):
    specification = util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


@dataclass
class AuthServices:
    database: LiveServer
    backend: LiveServer

    def login(self, email: str, password: str) -> requests.Session:
        session = requests.Session()
        response = session.post(
            f"{self.backend.url}/api/login",
            json={"email": email, "password": password},
            timeout=10,
        )
        response.raise_for_status()
        return session


@pytest.fixture(scope="session")
def auth_services(tmp_path_factory):
    """Start the actual Customer & Loyalty database and auth services."""

    database_directory = PROJECT_ROOT / "student-Ethan Ting" / "database"
    backend_path = PROJECT_ROOT / "student-Ethan Ting" / "backend" / "app.py"
    database_path = tmp_path_factory.mktemp("auth-live") / "users.db"
    previous_path = os.environ.get("DATABASE_PATH")
    previous_init_db = sys.modules.pop("init_db", None)
    os.environ["DATABASE_PATH"] = str(database_path)
    sys.path.insert(0, str(database_directory))

    database_server = None
    auth_server = None
    try:
        database_module = load_file_module(
            "ethan_ting_database_live", database_directory / "app.py"
        )
        database_server = LiveServer(database_module.app)

        auth_module = load_file_module("ethan_ting_auth_live", backend_path)
        auth_module.DATABASE_API_URL = database_server.url
        auth_module.app.config.update(
            SECRET_KEY="customer-support-live-test-secret",
            TESTING=False,
        )
        auth_server = LiveServer(auth_module.app)
        yield AuthServices(database_server, auth_server)
    finally:
        if auth_server:
            auth_server.close()
        if database_server:
            database_server.close()
        sys.path.remove(str(database_directory))
        sys.modules.pop("ethan_ting_database_live", None)
        sys.modules.pop("ethan_ting_auth_live", None)
        sys.modules.pop("init_db", None)
        if previous_init_db is not None:
            sys.modules["init_db"] = previous_init_db
        if previous_path is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = previous_path


@dataclass
class SupportStack:
    auth: AuthServices
    database: LiveServer
    backend: LiveServer
    database_path: Path

    def customer(self, email="customer@asd.local"):
        return self.auth.login(email, "CustomerPass!2026")

    def admin(self):
        return self.auth.login("admin@asd.local", "AdminPass!2026")

    @property
    def origin_headers(self):
        return {"Origin": TRUSTED_ORIGIN}

    @property
    def htmx_headers(self):
        return {"Origin": TRUSTED_ORIGIN, "HX-Request": "true"}


@pytest.fixture
def support_stack(tmp_path, auth_services):
    """Start Ethan's actual database API and support backend over HTTP."""

    init_db = import_module("student-Ethan Goldman.database_service.init_db")
    database_app = import_module("student-Ethan Goldman.database_service.app")
    support_app = import_module("student-Ethan Goldman.support_backend.app")

    database_path = tmp_path / "support.db"
    init_db.initialize_database(database_path)
    database_server = LiveServer(database_app.create_app(database_path))
    backend_server = None
    try:
        application = support_app.create_app(
            {
                "TESTING": False,
                "AUTH_SERVICE_URL": auth_services.backend.url,
                "AUTH_TIMEOUT_SECONDS": 5,
                "SUPPORT_DATABASE_API_URL": database_server.url,
                "SUPPORT_DATABASE_TIMEOUT": 5,
                "SUPPORT_FRONTEND_ORIGIN": TRUSTED_ORIGIN,
            }
        )
        backend_server = LiveServer(application)
        yield SupportStack(
            auth_services,
            database_server,
            backend_server,
            database_path,
        )
    finally:
        if backend_server:
            backend_server.close()
        database_server.close()
