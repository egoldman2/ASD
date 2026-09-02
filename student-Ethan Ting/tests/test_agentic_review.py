import importlib.util
import json
import sqlite3
from pathlib import Path


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
    }
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
        status = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"status": "healthy"}).encode("utf-8")

    monkeypatch.setattr(
        agentic_loop.request,
        "urlopen",
        lambda request_object, timeout: FakeResponse(),
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
