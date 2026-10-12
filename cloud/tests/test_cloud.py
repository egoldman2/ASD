"""Check cloud routing, bundle boundaries, origin validation and seed persistence."""

from importlib import import_module
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from werkzeug.security import check_password_hash

from cloud.prepare import prepare
from shared.runtime_config import allowed_origins

ROOT = Path(__file__).resolve().parents[2]


def test_cloud_bundle_routes_all_features_and_excludes_private_local_files(tmp_path):
    bundle = prepare(tmp_path / "bundle")
    assert not list(bundle.rglob("*.db"))
    assert not list(bundle.rglob(".env*"))
    assert not (bundle / ".git").exists()
    assert not (bundle / "docs").exists()
    assert (bundle / "cloud/install.sh").is_file()
    assert (bundle / "cloud/gateway.conf.template").is_file()
    assert (bundle / "cloud/Dockerfile.backend").is_file()
    assert (bundle / "cloud/Dockerfile.home").is_file()
    for feature, route in (
        ("student-Chufeng", "/catalogue/"), ("student-Ryan_Nolan", "/inventory/"),
        ("student-Ethan Ting", "/account/"), ("student-Howard", "/orders/"),
        ("student-Ethan Goldman", "/support/"),
    ):
        for page in (bundle / feature / "frontend").glob("*.html"):
            assert f'<base href="{route}">' in page.read_text()
            assert "http://localhost" not in page.read_text()
    account_script = (bundle / "student-Ethan Ting/frontend/js/login.js").read_text()
    assert 'const AUTH_API_URL = "/account-api"' in account_script
    assert "/account/index.html?return_url=%2Fcatalogue%2Fcart.html" in (bundle / "shared/nginx/product-catalogue.conf").read_text()


def test_bundle_cannot_replace_an_existing_directory(tmp_path):
    sentinel = tmp_path / "keep.txt"
    sentinel.write_text("Keep me")
    with pytest.raises(ValueError):
        prepare(tmp_path)
    assert sentinel.read_text() == "Keep me"


@pytest.mark.parametrize("origin", ["https://market.example", "http://127.0.0.1:8080"])
def test_public_origin_replaces_local_origin_allowlist(monkeypatch, origin):
    monkeypatch.setenv("PUBLIC_ORIGIN", origin)
    assert allowed_origins() == {origin}


@pytest.mark.parametrize("origin", ["https://example.test/path", "https://user:pass@example.test", "https://example.test?token=x", "javascript:alert(1)"])
def test_invalid_origin_is_rejected(monkeypatch, origin):
    monkeypatch.setenv("PUBLIC_ORIGIN", origin)
    with pytest.raises(ValueError):
        allowed_origins()


def test_cloud_seed_password_replaces_published_passwords_without_reseeding(tmp_path, monkeypatch):
    init = import_module("student-Ethan Ting.database.init_db")
    path = tmp_path / "users.db"
    monkeypatch.setattr(init, "DATABASE_PATH", path)
    monkeypatch.setenv("SEED_PASSWORD", "GeneratedPassword1234567890123456")
    init.initialise_database()
    with sqlite3.connect(path) as database:
        rows = database.execute("SELECT password_hash FROM users").fetchall()
    assert all(check_password_hash(row[0], "GeneratedPassword1234567890123456") for row in rows)
    assert not any(check_password_hash(row[0], "AdminPass!2026") or check_password_hash(row[0], "CustomerPass!2026") for row in rows)
    monkeypatch.setenv("SEED_PASSWORD", "DifferentPassword1234567890123456")
    init.initialise_database()
    with sqlite3.connect(path) as database:
        assert database.execute("SELECT password_hash FROM users").fetchall() == rows


def test_orders_bootstrap_uses_persistent_path_and_does_not_reset_existing_data(tmp_path, monkeypatch):
    path = tmp_path / "data/orders.db"
    monkeypatch.setenv("ORDERS_DATABASE_PATH", str(path))
    code = "from importlib import import_module; import_module('student-Howard.backend.routes.order_routes')"
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)
    with sqlite3.connect(path) as database:
        database.execute("UPDATE orders SET status='delivered' WHERE order_id=1")
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)
    with sqlite3.connect(path) as database:
        assert database.execute("SELECT status FROM orders WHERE order_id=1").fetchone()[0] == "delivered"
