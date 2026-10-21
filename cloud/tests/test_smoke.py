"""Fault-injected gateway protocol checks; separate Docker checks prove integration."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

import pytest

from cloud import smoke


class Response:
    def __init__(self, status, body, headers=None):
        self.code = status
        self.headers = {"Content-Type": "application/json", **(headers or {})}
        self.body = json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self, size):
        return self.body[:size]


@pytest.fixture
def gateway(monkeypatch):
    created, deleted, calls = {}, [], []
    state = {
        "failure": None,
        "cleanup_failures": set(),
        "noop_cleanup": set(),
        "disabled_body": {"error": "AI mode is disabled."},
        "mutate_disabled": False,
        "deactivated_accounts": [],
    }
    values = {
        "SEED_PASSWORD": "fixture-login-value",  # pragma: allowlist secret - Synthetic test-only credential.
        "ORIGIN_TOKEN": "fixture-origin-value",  # pragma: allowlist secret - Synthetic test-only credentials.
        "ASD_SOURCE_SHA": "a" * 40,
        "RELEASE_ID": "a" * 40 + "-1",
    }
    paths = {
        "account": "/account-api/api/admin/customers/101",
        "product": "/inventory-api/api/inventory/products/201",
        "cart": "/api/cart-items/301",
        "order": "/api/order-returns/orders/401",
        "support": "/api/support/admin/tickets/501",
    }
    bases = {
        "/account-api/api/admin/customers": ("account", 101),
        "/inventory-api/api/inventory/products": ("product", 201),
        "/api/cart-items": ("cart", 301),
        "/api/order-returns/orders": ("order", 401),
        "/api/support/customer/tickets": ("support", 501),
    }

    def open_request(request, timeout):
        path, method = urlsplit(request.full_url).path, request.get_method()
        payload = json.loads(request.data) if request.data else {}
        cookie = request.get_header("Cookie", "")
        calls.append((method, path))
        if state["failure"] == (method, path):
            raise URLError("fixture upstream failure")
        if method == "DELETE":
            deleted.append(path)
            if path in state["cleanup_failures"]:
                return Response(503, {"error": "fixture cleanup failed"})
            kind = next(
                kind for kind, stored_path in paths.items() if stored_path == path
            )
            if path in state["noop_cleanup"]:
                return Response(204 if kind == "product" else 200, {})
            record = created.pop(kind)
            if kind == "account":
                state["deactivated_accounts"].append({**record, "is_active": False})
            return Response(204 if kind == "product" else 200, {})
        if path in {
            "/",
            "/catalogue/",
            "/inventory/",
            "/account/",
            "/assets/js/site-header.js",
            "/assets/css/styles.css",
            "/orders/",
            "/support/",
        }:
            return Response(200, "fixture page")
        if path == "/account-api/api/login":
            user_id, role = (
                (1, "admin")
                if payload["email"] == "admin@asd.local"
                else (2, "customer")
                if payload["email"] == "customer@asd.local"
                else (101, "other")
            )
            return Response(
                200,
                {"user": {"id": user_id}},
                {"Set-Cookie": f"ethan_session={role}; Secure; HttpOnly; SameSite=Lax"},
            )
        if path == "/api/products":
            return Response(200, {"products": [created["product"]]})
        if not cookie:
            return Response(401, {})
        if cookie == "ethan_session=customer" and (
            path
            in {
                "/account-api/api/admin/customers",
                "/inventory-api/api/inventory/products",
                "/api/support/admin/tickets",
            }
            or (path == paths["support"] and method == "PUT")
        ):
            return Response(403, {})
        if (
            path == "/api/support/customer/tickets/501"
            and cookie == "ethan_session=other"
        ):
            return Response(404, {})
        if method == "POST" and (
            "/ai/" in path
            or "/mcp/" in path
            or "/rag/" in path
            or "/multi-agent/" in path
            or path.endswith("/ai-analysis")
        ):
            if state["mutate_disabled"] and "support" in created:
                created["support"]["status"] = "changed-by-disabled-route"
            return Response(503, state["disabled_body"])
        if method == "POST" and path in bases:
            kind, identifier = bases[path]
            record = {**payload, "id": identifier}
            if kind == "support":
                record.update(
                    status="open",
                    messages=[
                        {"sender_role": "customer", "message": payload["message"]}
                    ],
                )
            created[kind] = record
            body = (
                {"user": record}
                if kind == "account"
                else {"item": record}
                if kind == "cart"
                else {"order_id": identifier}
                if kind == "order"
                else {"ticket": record}
                if kind == "support"
                else record
            )
            return Response(201, body)
        if path == paths["support"] + "/messages":
            created["support"]["messages"].append(
                {"sender_role": "staff", "message": payload["message"]}
            )
            return Response(201, {})
        if method in {"PUT", "PATCH"}:
            kind = next(
                kind
                for kind, stored_path in paths.items()
                if path in {stored_path, stored_path + "/status"}
            )
            created[kind].update(payload)
            return Response(200, {})
        if path == "/account-api/api/admin/customers":
            return Response(
                200,
                {
                    "users": ([created["account"]] if "account" in created else [])
                    + state["deactivated_accounts"]
                },
            )
        if path == paths["product"]:
            return (
                Response(200, created["product"])
                if "product" in created
                else Response(404, {})
            )
        if path == "/api/cart-items":
            return Response(
                200, {"items": [created["cart"]] if "cart" in created else []}
            )
        if path == paths["order"]:
            return (
                Response(200, created["order"])
                if "order" in created
                else Response(404, {})
            )
        if path == paths["support"]:
            return (
                Response(200, {"ticket": created["support"]})
                if "support" in created
                else Response(404, {})
            )
        return Response(200, {})

    monkeypatch.setattr(smoke, "urlopen", open_request)
    return SimpleNamespace(
        created=created,
        deleted=deleted,
        calls=calls,
        state=state,
        values=values,
        paths=paths,
        open=open_request,
    )


def test_smoke_records_crud_disabled_responses_and_cleans_only_created_records(gateway):
    result = smoke.run("https://fixture.cloudfront.net", gateway.values)
    assert result["status"] == result["cleanup_status"] == "passed"
    assert not gateway.created and set(gateway.deleted) == set(gateway.paths.values())
    assert all(
        {"create", "read", "update", "delete"} <= set(operations)
        for operations in result["feature_crud"].values()
    )
    assert "reply" in result["feature_crud"]["customer_support"]
    assert (
        len([row for row in result["checks"] if row.get("disabled_integration")]) == 11
    )
    assert {
        "customer_support:multi_agent", "customer_loyalty:multi_agent",
        "product_catalogue:multi_agent", "inventory:multi_agent", "order_returns:multi_agent",
    } <= {row.get("disabled_integration") for row in result["checks"]}
    assert any(row["status"] == 404 for row in result["checks"])
    rendered = json.dumps(result)
    assert all(
        value not in rendered
        for value in (
            gateway.values["SEED_PASSWORD"],
            gateway.values["ORIGIN_TOKEN"],
            "ethan_session=",
        )
    )


def test_cleanup_attempts_every_record_and_preserves_the_original_failure(gateway):
    gateway.state["failure"] = ("PUT", gateway.paths["support"])
    gateway.state["cleanup_failures"].update(
        {gateway.paths["support"], gateway.paths["cart"]}
    )
    with pytest.raises(smoke.SmokeFailure) as error:
        smoke.run("https://fixture.cloudfront.net", gateway.values)
    report = error.value.report
    assert isinstance(error.value.__cause__, URLError)
    assert set(gateway.deleted) == set(gateway.paths.values())
    assert (
        report["failure"]["error_type"] == "URLError"
        and len(report["cleanup_errors"]) == 2
    )
    assert report["status"] == report["cleanup_status"] == "failed"


def test_loyalty_multi_agent_disabled_message_is_recognised(gateway):
    gateway.state["disabled_body"] = {"error": "Multi-Agent mode is disabled."}
    assert smoke.run("https://fixture.cloudfront.net", gateway.values)["status"] == "passed"


@pytest.mark.parametrize("change", ["outage", "misleading_field", "mutates"])
def test_a_503_alone_or_ticket_mutation_does_not_pass_disabled_checks(gateway, change):
    if change == "outage":
        gateway.state["disabled_body"] = {"error": "Unavailable upstream"}
    elif change == "misleading_field":
        gateway.state["disabled_body"] = {
            "disabled": False,
            "error": "Unavailable upstream",
        }
    else:
        gateway.state["mutate_disabled"] = True
    with pytest.raises(smoke.SmokeFailure) as error:
        smoke.run("https://fixture.cloudfront.net", gateway.values)
    assert error.value.report["status"] == "failed"
    assert not gateway.created


def test_cli_saves_a_sanitized_failure_artifact(gateway, tmp_path, monkeypatch, capsys):
    gateway.state["failure"] = ("GET", "/catalogue/")
    for key, value in gateway.values.items():
        monkeypatch.setenv(key, value)
    output = tmp_path / "failure.json"
    assert smoke.main(["https://fixture.cloudfront.net", "--report", str(output)]) == 1
    report = json.loads(output.read_text())
    assert (
        report["status"] == "failed" and report["failure"]["error_type"] == "URLError"
    )
    assert gateway.values["SEED_PASSWORD"] not in capsys.readouterr().out


@pytest.mark.parametrize(
    "url",
    [
        "file:///outside",
        "http://external.example",
        "https://user:pass@example.test",  # pragma: allowlist secret - Rejected synthetic credential URL.
        "https://example.test/path",
        "https://example.test?query=value",
    ],
)
def test_credentials_are_never_sent_to_invalid_origins(gateway, url):
    with pytest.raises(ValueError):
        smoke.run(url, gateway.values)
    assert not gateway.calls


def test_invalid_created_id_never_becomes_a_cleanup_target(gateway, monkeypatch):
    def malformed(request, timeout):
        if (
            request.get_method() == "POST"
            and urlsplit(request.full_url).path
            == "/inventory-api/api/inventory/products"
        ):
            return Response(201, {"id": "untrusted/pre-existing-target"})
        return gateway.open(request, timeout)

    monkeypatch.setattr(smoke, "urlopen", malformed)
    with pytest.raises(smoke.SmokeFailure) as error:
        smoke.run("https://fixture.cloudfront.net", gateway.values)
    assert gateway.deleted == [gateway.paths["account"]]
    assert (
        error.value.report["cleanup_errors"][0]["error_type"]
        == "unidentified_created_record"
    )
    assert error.value.report["cleanup_status"] == "failed"


def test_delete_acknowledgement_is_checked_against_persisted_state(gateway):
    gateway.state["noop_cleanup"].add(gateway.paths["product"])
    with pytest.raises(smoke.SmokeFailure) as error:
        smoke.run("https://fixture.cloudfront.net", gateway.values)
    assert set(gateway.deleted) == set(gateway.paths.values())
    assert error.value.report["cleanup_status"] == "failed"
    assert any(
        row["path"] == gateway.paths["product"]
        for row in error.value.report["cleanup_errors"]
    )


def test_oversized_response_is_not_saved_or_accepted(gateway, monkeypatch):
    response = Response(200, {})
    response.body = b"x" * (1024 * 1024 + 1)
    monkeypatch.setattr(smoke, "urlopen", lambda *args, **kwargs: response)
    with pytest.raises(smoke.SmokeFailure) as error:
        smoke.run("https://fixture.cloudfront.net", gateway.values)
    assert isinstance(error.value.__cause__, ValueError)
    assert len(json.dumps(error.value.report)) < 4000


def test_create_response_loss_requires_manual_check_without_guessing_an_id(gateway):
    gateway.state["failure"] = ("POST", "/inventory-api/api/inventory/products")
    with pytest.raises(smoke.SmokeFailure) as error:
        smoke.run("https://fixture.cloudfront.net", gateway.values)
    assert gateway.deleted == [gateway.paths["account"]]
    assert error.value.report["cleanup_status"] == "failed"
    assert error.value.report["unconfirmed_creations"] == [
        "/inventory-api/api/inventory/products"
    ]
    assert isinstance(error.value.__cause__, URLError)


@pytest.mark.parametrize(
    "method,cross_origin,follow",
    [("GET", False, True), ("GET", True, False), ("POST", False, False)],
)
def test_real_redirects_preserve_only_same_origin_reads(
    gateway, monkeypatch, method, cross_origin, follow
):
    visited = []

    class Redirect(BaseHTTPRequestHandler):
        def do_GET(self):
            visited.append(
                (self.command, self.path, self.headers.get("X-Origin-Verify"))
            )
            if self.path == "/":
                self.send_response(302)
                host = "localhost" if cross_origin else "127.0.0.1"
                self.send_header(
                    "Location", f"http://{host}:{self.server.server_port}/destination"
                )
            else:
                self.send_response(200)
            self.end_headers()

        do_POST = do_GET

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(
        smoke, "urlopen", smoke.build_opener(smoke.SameOriginRedirect()).open
    )
    request = smoke.Request(
        f"http://127.0.0.1:{server.server_port}/",
        method=method,
        headers={"X-Origin-Verify": gateway.values["ORIGIN_TOKEN"]},
    )
    try:
        if follow:
            with smoke.urlopen(request, timeout=5) as response:
                assert response.code == 200
            assert visited == [
                ("GET", "/", gateway.values["ORIGIN_TOKEN"]),
                ("GET", "/destination", gateway.values["ORIGIN_TOKEN"]),
            ]
        else:
            with pytest.raises(HTTPError) as error:
                smoke.urlopen(request, timeout=5)
            assert error.value.code == 302
            assert visited == [(method, "/", gateway.values["ORIGIN_TOKEN"])]
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
