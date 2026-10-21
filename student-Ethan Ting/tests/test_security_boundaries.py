"""Regression checks supporting narrowly reviewed security-scan findings."""

import ast
import importlib.util
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import Request

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def backend():
    spec = importlib.util.spec_from_file_location("ethan_security_app", ROOT / "backend/app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("base", ["file:///etc/passwd", "ftp://localhost", "data:text/plain,test",
    "http://", "http://user:password@localhost", "http://localhost:0", "http://localhost:65536",  # pragma: allowlist secret - Dummy credentials test that URL userinfo is rejected.
    "http://localhost/api", "http://localhost?key=value", "http://localhost#fragment",
    "http://localhost\n", "http://[invalid", None])
def test_service_origins_fail_closed(backend, monkeypatch, base):
    monkeypatch.setattr(backend, "urlopen", lambda *a, **k: pytest.fail("Network request made"))
    monkeypatch.setattr(backend, "DATABASE_API_URL", base)
    with pytest.raises(ValueError):
        backend.database_request("/health")


@pytest.mark.parametrize("path", ["//external.test/path", "https://external.test", "health",
    "/health#fragment", "/health\r\nHeader: value", None])
def test_only_application_paths_are_accepted(backend, path):
    with pytest.raises(ValueError):
        backend.service_http_url("http://localhost:6003", path)


@pytest.mark.parametrize("origin", ["http://127.0.0.1:6003", "https://api.example.test",
    "http://ethan-database:6003/", "http://host.docker.internal:5003", "http://[::1]:6003"])
def test_supported_service_origins(backend, origin):
    assert backend.service_http_url(origin, "/internal/users?email=test%40example.test") == origin.rstrip("/") + "/internal/users?email=test%40example.test"


@pytest.mark.parametrize("destination", ["http://external.test", "file:///etc/passwd", "ftp://external.test"])
def test_service_redirects_are_rejected(backend, destination):
    with pytest.raises(HTTPError, match="redirects are not allowed"):
        backend.NoServiceRedirect().redirect_request(Request("http://localhost/health"), None, 302,
            "Moved", {}, destination)


@pytest.mark.parametrize("part", ["backend", "database"])
def test_native_loopback_and_explicit_container_binding(part):
    source = (ROOT / part / "app.py").read_text()
    assert 'host=os.environ.get("APP_HOST", "127.0.0.1")' in source
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert f"FROM python-base AS {part}\nENV APP_HOST=0.0.0.0" in dockerfile


def test_dynamic_update_assignments_are_fixed_not_user_identifiers():
    source = ast.parse((ROOT / "database/app.py").read_text())
    update = next(node for node in source.body if isinstance(node, ast.FunctionDef)
        and node.name == "update_user")
    assignments = [node.args[0] for node in ast.walk(update) if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "updates" and node.func.attr == "append"]
    assert assignments
    assert all(isinstance(node, ast.Constant) for node in assignments)
    assert {node.value for node in assignments} == {
        "full_name = ?", "email = ?", "is_active = ?", "password_hash = ?"}


@pytest.fixture
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "security-test.db"))
    monkeypatch.syspath_prepend(str(ROOT / "database"))
    monkeypatch.delitem(sys.modules, "init_db", raising=False)
    spec = importlib.util.spec_from_file_location("ethan_security_database", ROOT / "database/app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sql_looking_values_are_stored_literally(isolated_database):
    module = isolated_database
    name = "Test', role = 'admin'; DROP TABLE users; --"
    with module.app.test_client() as client:
        response = client.put("/internal/users/2", json={"full_name": name, "email": "literal@example.test"})
    assert response.status_code == 200
    with module.get_connection() as connection:
        customer = dict(connection.execute("SELECT * FROM users WHERE id = ?", (2,)).fetchone())
        assert customer["full_name"] == name
        assert customer["email"] == "literal@example.test"
        assert customer["role"] == "customer"
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] >= 10


def test_browser_cannot_supply_update_column_names(isolated_database):
    with isolated_database.app.test_client() as client:
        response = client.put("/internal/users/2", json={"role = 'admin' --": "admin", "role": "admin"})
    assert response.status_code == 400
    with isolated_database.get_connection() as connection:
        assert connection.execute("SELECT role FROM users WHERE id = ?", (2,)).fetchone()[0] == "customer"
