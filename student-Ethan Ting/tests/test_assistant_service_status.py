"""HTMX fragments report service reachability, never unverified readiness."""
import importlib.util
from pathlib import Path
from html.parser import HTMLParser
import re

import httpx
import pytest


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" if (ROOT / "frontend").is_dir() else ROOT / "student-Ethan Ting/frontend"
STATUS = "/api/admin/assistant/service-status"


@pytest.fixture
def module(monkeypatch):
    spec = importlib.util.spec_from_file_location("assistant_status_app", ROOT / "backend/app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.config.update(TESTING=True, SECRET_KEY="status-test-key")
    for flag in ("AI_MODE_ENABLED", "MCP_ENABLED", "RAG_ENABLED"):
        monkeypatch.setenv(flag, "true")
    monkeypatch.setenv("MCP_SERVER_URL", "http://mcp.test:8765/mcp")
    monkeypatch.setenv("RAG_SERVER_URL", "http://rag.test:5003")
    monkeypatch.setattr(module, "database_request", lambda *args: {
        "user": {"id": 1, "role": "admin", "is_active": 1, "email": "admin@asd.local", "full_name": "Admin"},
    })
    return module


def sign_in(client, role="admin"):
    with client.session_transaction() as session:
        session["user"] = {"id": 1, "role": role, "email": "admin@asd.local", "full_name": "Admin"}


def healthy(kind):
    return {"status": "healthy", "service": f"asd-marketplace-{kind}",
            "enabled": True, "available_scopes": ["ethan_ting_accounts_loyalty"]}


def install_transport(module, monkeypatch, handler):
    client_class = httpx.Client
    def client(**kwargs):
        assert kwargs == {"timeout": 2, "follow_redirects": False}
        return client_class(transport=httpx.MockTransport(handler), **kwargs)
    monkeypatch.setattr(module.httpx, "Client", client)


def test_status_is_admin_only(module, monkeypatch):
    monkeypatch.setattr(module, "assistant_service_health", lambda *args: pytest.fail("Unauthorised probe"))
    with module.app.test_client() as client:
        assert client.get(STATUS).status_code == 401
        sign_in(client, "customer")
        assert client.get(STATUS).status_code == 403


def test_disabled_admin_cannot_check_status(module, monkeypatch):
    monkeypatch.setattr(module, "database_request", lambda *args: {"user": {"id": 1, "role": "admin", "is_active": 0}})
    monkeypatch.setattr(module, "assistant_service_health", lambda *args: pytest.fail("Disabled user probe"))
    with module.app.test_client() as client:
        sign_in(client)
        assert client.get(STATUS).status_code in (401, 403)


@pytest.mark.parametrize("fault", [TimeoutError, OSError])
def test_authentication_database_failure_is_safe(module, monkeypatch, fault):
    def unavailable(*args): raise fault("private database details")
    monkeypatch.setattr(module, "database_request", unavailable)
    monkeypatch.setattr(module, "assistant_service_health", lambda *args: pytest.fail("No verified admin"))
    with module.app.test_client() as client:
        sign_in(client)
        result = client.get(STATUS)
    assert result.status_code == 503
    assert "private database details" not in result.get_data(as_text=True)


@pytest.mark.parametrize("user", ["invalid", 4, []])
def test_malformed_session_is_rejected_without_a_probe(module, monkeypatch, user):
    monkeypatch.setattr(module, "assistant_service_health", lambda *args: pytest.fail("No verified admin"))
    with module.app.test_client() as client:
        with client.session_transaction() as session: session["user"] = user
        assert client.get(STATUS).status_code == 401


def test_fragment_uses_fixed_health_urls_without_customer_credentials(module, monkeypatch):
    calls = []
    def handler(request):
        calls.append(str(request.url))
        assert request.method == "GET" and "cookie" not in request.headers
        assert "authorization" not in request.headers
        kind = "mcp" if request.url.host == "mcp.test" else "rag"
        return httpx.Response(200, json=healthy(kind))
    install_transport(module, monkeypatch, handler)
    with module.app.test_client() as client:
        sign_in(client)
        result = client.get(STATUS + "?url=http://untrusted.test&customer_id=2")
    text = result.get_data(as_text=True)
    assert result.status_code == 200 and result.mimetype == "text/html"
    assert "MCP: Reachable" in text and "RAG: Reachable" in text
    assert "requests may still fail" in text
    assert "no-store" in result.headers["Cache-Control"]
    assert "Cookie" in result.headers["Vary"]
    assert sorted(calls) == ["http://mcp.test:8765/health", "http://rag.test:5003/health"]
    assert "customer" not in text and "admin@" not in text


@pytest.mark.parametrize("kind,flag", [("MCP", "MCP_ENABLED"), ("RAG", "RAG_ENABLED"), ("RAG", "AI_MODE_ENABLED")])
def test_disabled_flags_skip_network(module, monkeypatch, kind, flag):
    monkeypatch.setenv(flag, "false")
    monkeypatch.setattr(module.httpx, "Client", lambda **kw: pytest.fail("Disabled service network call"))
    assert module.assistant_service_health(kind) == (kind, "disabled", "Disabled")


@pytest.mark.parametrize("fault", ["timeout", "redirect", "wrong_service", "unhealthy", "invalid_json", "oversized", "wrong_scope", "scope_type", "disabled"])
def test_unhealthy_or_untrusted_services_are_not_shown_as_live(module, monkeypatch, fault):
    def handler(request):
        if fault == "timeout":
            raise httpx.ReadTimeout("private host details", request=request)
        if fault == "redirect":
            return httpx.Response(302, headers={"Location": "http://untrusted.test"})
        if fault == "invalid_json":
            return httpx.Response(200, text="<script>alert('private')</script>")
        if fault == "oversized":
            return httpx.Response(200, content=b"x" * 16385)
        payload = healthy("rag")
        if fault == "wrong_service": payload["service"] = "untrusted"
        if fault == "unhealthy": payload["status"] = "disabled"
        if fault == "wrong_scope": payload["available_scopes"] = ["chufeng_catalogue"]
        if fault == "scope_type": payload["available_scopes"] = "ethan_ting_accounts_loyalty"
        if fault == "disabled": payload["enabled"] = False
        return httpx.Response(200, json=payload)
    install_transport(module, monkeypatch, handler)
    assert module.assistant_service_health("RAG")[1] == "offline"


@pytest.mark.parametrize("url", ["file:///private", "http://[broken", "", "http://secret:password@rag.test"])
def test_bad_config_is_safe_and_does_not_connect(module, monkeypatch, url):
    monkeypatch.setenv("RAG_SERVER_URL", url)
    monkeypatch.setattr(module.httpx, "Client", lambda **kw: pytest.fail("Invalid URL network call"))
    assert module.assistant_service_health("RAG") == ("RAG", "offline", "Unavailable")


def test_outage_is_a_rendered_retryable_state(module, monkeypatch):
    monkeypatch.setattr(module, "assistant_service_health", lambda kind: (kind, "offline", "Unavailable"))
    with module.app.test_client() as client:
        sign_in(client)
        result = client.get(STATUS)
    assert result.status_code == 200
    assert "MCP: Unavailable" in result.get_data(as_text=True)


def test_admin_pages_share_one_component_and_existing_htmx_asset():
    for page in ("admin.html", "admin-loyalty.html"):
        html = (FRONTEND / page).read_text()
        assert html.count('id="customerAssistant"') == 1
        assert 'js/customer-assistant.js' in html
        assert 'http://localhost:8000/js/htmx.min.js' in html
        assert 'id="customerInsightForm"' not in html
    source = (FRONTEND / "js/customer-assistant.js").read_text()
    assert 'hx-trigger="load, every 30s"' in source
    assert 'Confirmation required</span>' not in source
    assert 'customer@asd.local' not in source
    assert 'sessionStorage.getItem("ethan.assistant.customer")' in source
    assert 'event.key === "ArrowRight"' in source


def test_shared_guide_examples_cover_account_and_loyalty_help():
    source = (FRONTEND / "js/customer-assistant.js").read_text()
    for label, question in (
        ("Change password", "How can a customer change their password, and what are the requirements?"),
        ("Profile changes", "How can a customer update their profile name and email?"),
        ("Getting points", "How do customers get loyalty points, and are purchases rewarded automatically?"),
        ("Viewing history", "Where can a customer check their loyalty point history?"),
    ):
        assert f'data-rag-question="{question}">{label}</button>' in source
    assert 'This does not look up live customers or change data.' in source


def test_component_markup_has_unique_ids_and_resolved_labels():
    source = (FRONTEND / "js/customer-assistant.js").read_text()
    markup = source.split('host.innerHTML = `', 1)[1].split('`;', 1)[0]
    class Parser(HTMLParser):
        def __init__(self): super().__init__(); self.ids = []; self.references = []
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if "id" in attrs: self.ids.append(attrs["id"])
            for key in ("for", "aria-controls", "aria-labelledby"):
                if key in attrs: self.references.extend(attrs[key].split())
    parser = Parser(); parser.feed(markup)
    assert len(parser.ids) == len(set(parser.ids))
    assert set(parser.references).issubset(set(parser.ids))
    for referenced in re.findall(r'document.querySelector\("#([\w-]+)"\)', source):
        assert referenced in parser.ids or referenced == "customerAssistant"


def test_both_page_lists_refresh_after_an_approved_edit():
    for script in ("admin.js", "admin-loyalty.js"):
        source = (FRONTEND / "js" / script).read_text()
        assert 'document.addEventListener("customer-assistant:updated"' in source
