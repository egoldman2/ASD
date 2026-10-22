import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest


STUDENT_FOLDER = Path(__file__).resolve().parents[1]
if (STUDENT_FOLDER / "ai-services" / "agentic_loop.py").is_file():
    PROJECT_ROOT = STUDENT_FOLDER
else:
    PROJECT_ROOT = STUDENT_FOLDER.parent
AGENTIC_LOOP_PATH = PROJECT_ROOT / "ai-services" / "agentic_loop.py"


def load_agentic_loop(module_name="ethan_agentic_loop"):
    specification = importlib.util.spec_from_file_location(
        module_name,
        AGENTIC_LOOP_PATH,
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    module.PROJECT_ROOT = PROJECT_ROOT
    return module


def test_ethan_feature_is_discoverable_and_complete():
    agentic_loop = load_agentic_loop()

    assert "student-Ethan Ting" in agentic_loop.discover_features()

    config, prompt = agentic_loop.load_feature("student-Ethan Ting")

    assert config["feature_name"] == (
        "Ethan Ting - Customer Accounts and Loyalty"
    )
    assert set(config["mode_prompts"]) == {
        "database",
        "endpoints",
        "architecture",
        "mcp",
        "rag",
        "multi-agent",
    }
    assert config["mcp_rules"]["required_tools"] == ["ethan_ting_calculate_loyalty_tier", "ethan_ting_get_loyalty_history"]
    assert config["rag_rules"]["required_scope"] == "ethan_ting_accounts_loyalty"
    assert {probe["expected"] for probe in config["rag_rules"]["probes"]} == {
        "grounded", "insufficient",
    }
    assert config["multi_agent_rules"]["expected_feature"] == "customer_loyalty"
    assert config["multi_agent_rules"]["require_selected_workflow"] is True
    for mode in ("mcp", "rag", "multi-agent"):
        assert all((PROJECT_ROOT / path).is_file() for path in config[f"{mode}_files"])
    assert set(config["database_rules"]["required_tables"]) == {
        "users",
        "loyalty_accounts",
        "loyalty_transactions",
    }
    assert all(
        endpoint["expected_status"] in {200, 401}
        for endpoint in config["endpoints"]
    )
    assert all(
        (PROJECT_ROOT / path).is_file()
        for path in config["architecture_files"]
    )
    assert "Plan -> Act -> Observe -> Adapt" in prompt
    assert "must not be claimed" in prompt


def test_loyalty_multi_agent_source_checks_pass_without_live_calls(monkeypatch):
    runner = load_agentic_loop("loyalty_review_static")
    config, _ = runner.load_feature("student-Ethan Ting")
    monkeypatch.setenv("AI_MODE_ENABLED", "false")
    monkeypatch.setenv("MULTI_AGENT_ENABLED", "true")

    def forbidden(_):
        pytest.fail("Disabled review contacted the host")

    evidence = runner.collect_multi_agent_evidence(config, runtime_probe=forbidden)
    checks = evidence["verified_checks"]
    assert not checks["missing_files"]
    assert all(checks["source_checks"].values())
    for field in ("all_required_agents_wired", "agent_order_in_coordinator",
                  "all_group_features_supported", "all_required_endpoints_registered",
                  "human_review_gate_present", "multi_agent_server_not_in_compose"):
        assert checks[field] is True
    assert evidence["runtime"]["attempted"] is False
    assert evidence["runtime"]["review_evidence_complete"] is False


def test_loyalty_review_requires_selected_id_before_network(monkeypatch):
    runner = load_agentic_loop("loyalty_review_selected_id")
    config, _ = runner.load_feature("student-Ethan Ting")
    import multi_agent_validation as validation

    monkeypatch.setenv("AI_MODE_ENABLED", "true")
    monkeypatch.setenv("MULTI_AGENT_ENABLED", "true")
    monkeypatch.delenv("MULTI_AGENT_REVIEW_WORKFLOW_ID", raising=False)
    monkeypatch.setattr(validation, "read_json", lambda *args, **kwargs: pytest.fail("Network call made"))
    with pytest.raises(validation.ProbeConfigurationError, match="selected workflow ID"):
        validation.probe_runtime(config, project_root=PROJECT_ROOT)


@pytest.mark.parametrize("returned_feature,returned_id", [
    ("customer_support", "selected-workflow"),
    ("customer_loyalty", "another-workflow"),
])
def test_loyalty_review_rejects_other_feature_or_workflow(monkeypatch, returned_feature, returned_id):
    runner = load_agentic_loop("loyalty_review_scope")
    config, _ = runner.load_feature("student-Ethan Ting")
    import multi_agent_validation as validation

    monkeypatch.setenv("AI_MODE_ENABLED", "true")
    monkeypatch.setenv("MULTI_AGENT_ENABLED", "true")
    monkeypatch.setenv("MULTI_AGENT_SERVER_URL", "http://127.0.0.1:5054")
    monkeypatch.setenv("MULTI_AGENT_REVIEW_WORKFLOW_ID", "selected-workflow")
    request = {"feature": returned_feature, "user_request": "Review synthetic fixture evidence.",
        "evidence": [{"evidence_id": "fixture-1", "data": {"points_balance": 720},
            "source": {"service": "fixture", "endpoint": "/fixture", "retrieved_at": "2026-10-22T00:00:00+11:00"}}]}
    workflow = {"workflow_id": returned_id, "request": request,
        "status": "awaiting_human_review", "timestamp": "2026-10-22T00:00:00+11:00", "human_review": None}
    for agent, output in (("planner", "plan"), ("worker", "output"), ("reviewer", "review")):
        workflow[f"{agent}_result"] = {"agent": agent, "status": "completed", "model": "fixture-model",
            "evidence_ids": ["fixture-1"], "human_approval_required": True, output: "Synthetic output only."}
    workflow["planner_result"]["objective"] = request["user_request"]
    workflow["worker_result"]["evidence_count"] = 1
    calls = []

    def read(method, url, **kwargs):
        calls.append((method, url))
        return (200, {"status": "ok", "service": "asd-marketplace-multi-agent"}) if url.endswith("/health") else (200, workflow)

    monkeypatch.setattr(validation, "read_json", read)
    monkeypatch.setattr(validation, "_verify_logs", lambda *args: pytest.fail("Wrong-scope logs accepted"))
    runtime = validation.probe_runtime(config, project_root=PROJECT_ROOT)
    assert runtime["scope_verified"] is False
    assert runtime["latest_workflow_verified"] is False
    assert runtime["review_evidence_complete"] is False
    assert calls == [("GET", "http://127.0.0.1:5054/health"),
                     ("GET", "http://127.0.0.1:5054/api/workflows/selected-workflow")]


def test_database_evidence_redacts_password_hashes(tmp_path):
    database_path = tmp_path / "review.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                email TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                api_token TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO users (id, email, password_hash, api_token)
            VALUES (1, 'customer@example.test', 'secret-hash', 'secret-token')
            """
        )

    agentic_loop = load_agentic_loop("ethan_agentic_redaction")
    agentic_loop.PROJECT_ROOT = tmp_path
    evidence = agentic_loop.collect_database_evidence({
        "database": "review.db",
        "database_rules": {
            "redacted_columns": {"users": ["password_hash"]},
        },
    })

    sample = evidence["tables"]["users"]["sample_records"][0]
    assert sample == {
        "id": 1,
        "email": "customer@example.test",
        "password_hash": "<redacted>",
        "api_token": "<redacted>",
    }


def test_architecture_evidence_redacts_credential_like_values(tmp_path):
    source_path = tmp_path / "seed.py"
    source_path.write_text(
        'USERS = [("admin@example.test", "AdminPass!2026")]\n'
        'SECRET_KEY = "development-only-secret"\n'
        'safe_setting = "visible"\n',
        encoding="utf-8",
    )

    agentic_loop = load_agentic_loop("ethan_architecture_redaction")
    agentic_loop.PROJECT_ROOT = tmp_path
    evidence = agentic_loop.collect_architecture_evidence({
        "architecture_files": ["seed.py"],
    })
    excerpt = evidence["files"][0]["content"]

    assert "AdminPass!2026" not in excerpt
    assert "development-only-secret" not in excerpt
    assert excerpt.count("<redacted>") == 2
    assert 'safe_setting = "visible"' in excerpt


def test_database_fallback_uses_feature_specific_tables():
    agentic_loop = load_agentic_loop("ethan_agentic_fallback")
    evidence = {
        "tables": {
            "users": {
                "record_count": 11,
                "columns": [{"name": "id"}, {"name": "email"}],
                "foreign_keys": [],
            },
            "loyalty_accounts": {
                "record_count": 10,
                "columns": [
                    {"name": "user_id"},
                    {"name": "points_balance"},
                ],
                "foreign_keys": [{
                    "from_column": "user_id",
                    "referenced_table": "users",
                    "to_column": "id",
                    "on_delete": "CASCADE",
                }],
            },
            "loyalty_transactions": {
                "record_count": 10,
                "columns": [
                    {"name": "id"},
                    {"name": "user_id"},
                    {"name": "points_change"},
                ],
                "foreign_keys": [{
                    "from_column": "user_id",
                    "referenced_table": "users",
                    "to_column": "id",
                    "on_delete": "CASCADE",
                }],
            },
        }
    }
    config = {
        "database_rules": {
            "required_tables": [
                "users",
                "loyalty_accounts",
                "loyalty_transactions",
            ],
            "minimum_records": {
                "users": 10,
                "loyalty_accounts": 10,
                "loyalty_transactions": 10,
            },
            "foreign_key_tables": [
                "loyalty_accounts",
                "loyalty_transactions",
            ],
        }
    }

    fallback = agentic_loop._grounded_fallback(
        "database",
        evidence,
        ["Model grounding issue"],
        config,
    )

    assert "`users` has 11 records" in fallback
    assert "`loyalty_accounts` has 10 records" in fallback
    assert "`loyalty_transactions` has 10 records" in fallback
    assert "products" not in fallback
    assert "cart_items" not in fallback


def test_database_grounding_rejects_false_authentication_claims():
    agentic_loop = load_agentic_loop("ethan_agentic_grounding")
    evidence = {
        "tables": {
            "users": {
                "record_count": 10,
                "columns": [
                    {"name": "id"},
                    {"name": "password_hash"},
                ],
            }
        }
    }

    issues = agentic_loop._deterministic_issues(
        "database",
        evidence,
        (
            "The users table does not contain any authentication fields. "
            "The password_hash field is redacted and not used for authentication."
        ),
    )

    assert any("schema contains: password_hash" in issue for issue in issues)
    assert any("does not prove" in issue for issue in issues)


def test_endpoint_evidence_records_expected_status(monkeypatch):
    agentic_loop = load_agentic_loop("ethan_agentic_endpoints")

    class FakeResponse:
        status_code = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def iter_content(self, size):
            yield json.dumps({"status": "healthy"}).encode("utf-8")

    monkeypatch.setattr(
        agentic_loop.requests,
        "get",
        lambda url, **kwargs: FakeResponse(),
    )

    evidence = agentic_loop.collect_endpoint_evidence({
        "endpoints": [{
            "name": "Health",
            "url": "http://localhost:6002/health",
            "expected_status": 200,
        }]
    })

    assert evidence["method"] == "GET only"
    assert evidence["endpoints"][0]["status"] == 200
    assert evidence["endpoints"][0]["expected_status"] == 200


def test_endpoint_grounding_treats_expected_401_as_protection():
    agentic_loop = load_agentic_loop("ethan_agentic_endpoint_grounding")
    evidence = {
        "endpoints": [{
            "name": "Profile protection",
            "url": "http://localhost:6002/api/profile",
            "expected_status": 401,
            "status": 401,
        }]
    }

    issues = agentic_loop._deterministic_issues(
        "endpoints",
        evidence,
        (
            "The /api/profile endpoint returns a 401, so it is not secure enough. "
            "It should be updated to return 200. High: protection is correctly passing."
        ),
    )
    fallback = agentic_loop._grounded_fallback(
        "endpoints",
        evidence,
        issues,
        {},
    )

    assert any("not evidence that the service is insecure" in issue for issue in issues)
    assert any("contradicting their configured 401" in issue for issue in issues)
    assert any("should not be labelled" in issue for issue in issues)
    assert "PASS: GET `/api/profile` expected 401 and observed 401" in fallback
    assert "correctly rejected the signed-out request" in fallback


def test_architecture_review_covers_completed_runtime_ai_controls():
    agentic_loop = load_agentic_loop("ethan_agentic_architecture")
    config, _ = agentic_loop.load_feature("student-Ethan Ting")
    evidence = agentic_loop.collect_architecture_evidence(config)
    checks = evidence["verified_checks"]

    assert checks["separate_docker_services"] is True
    assert checks["backend_uses_database_api"] is True
    assert checks["backend_opens_sqlite_directly"] is False
    assert checks["database_container_owns_sqlite"] is True
    assert checks["http_only_session_cookie"] is True
    assert checks["active_account_revalidated"] is True
    assert checks["admin_role_guard"] is True
    assert checks["tier_boundary_tests_include_499_and_999"] is True
    assert checks["negative_balance_rejected_in_database"] is True
    assert checks["runtime_ai_in_ethan_frontend_or_backend"] is True
    assert checks["customer_insight_route_is_admin_only"] is True
    assert checks["customer_insight_uses_allow_listed_records"] is True
    assert checks["customer_insight_validates_model_output"] is True
    assert checks["customer_insight_prompt_is_read_only"] is True
    assert checks["customer_insight_security_tests_present"] is True

    issues = agentic_loop._deterministic_issues(
        "architecture",
        evidence,
        (
            "The tier tests do not include cases for 499 and 999 points. "
            "The system does not have a mechanism for negative balances. "
            "The adaptation has been applied to the codebase."
        ),
    )
    fallback = agentic_loop._grounded_fallback(
        "architecture",
        evidence,
        issues,
        config,
    )

    assert any("fewer than three configured files" in issue for issue in issues)
    assert any("explicitly include 499 and 999" in issue for issue in issues)
    assert any("explicitly rejects new_balance" in issue for issue in issues)
    assert any("omits the observed runtime Customer Insight" in issue for issue in issues)
    assert any("loop is read-only" in issue for issue in issues)
    assert "High Release 0 gap" not in fallback
    assert "Runtime AI integration markers were observed" in fallback
    assert "Keep Customer Insight administrator-only and read-only" in fallback
