import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest


@pytest.fixture
def agentic_loop():
    project_root = Path(__file__).resolve().parents[2]
    module_path = project_root / "ai-services" / "agentic_loop.py"
    specification = importlib.util.spec_from_file_location(
        "shared_agentic_loop",
        module_path,
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_loads_chufeng_feature_prompt(agentic_loop):
    config, prompt = agentic_loop.load_feature("student-Chufeng")

    assert config["feature_name"] == "Chufeng - Product Catalogue and Shopping Cart"
    assert "Never modify code" in prompt
    assert "Review only the supplied SQLite database evidence" in config[
        "mode_prompts"
    ]["database"]


def test_database_evidence_is_read_only(agentic_loop, monkeypatch, tmp_path):
    database_path = tmp_path / "catalogue.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );
            INSERT INTO products (id, name) VALUES (1, 'Test Product');
            """
        )

    monkeypatch.setattr(agentic_loop, "PROJECT_ROOT", tmp_path)
    evidence = agentic_loop.collect_database_evidence(
        {"database": "catalogue.db"}
    )

    with sqlite3.connect(database_path) as connection:
        count_after_review = connection.execute(
            "SELECT COUNT(*) FROM products"
        ).fetchone()[0]

    assert evidence["read_only"] is True
    assert evidence["tables"]["products"]["record_count"] == 1
    assert count_after_review == 1


def test_endpoint_evidence_uses_get_only(agentic_loop, monkeypatch):
    captured_requests = []

    class FakeResponse:
        status = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"count": 1, "products": [{"id": 1}]}).encode()

    def fake_urlopen(http_request, timeout):
        captured_requests.append((http_request, timeout))
        return FakeResponse()

    monkeypatch.setattr(agentic_loop.request, "urlopen", fake_urlopen)
    evidence = agentic_loop.collect_endpoint_evidence(
        {
            "endpoints": [
                {"name": "Products", "url": "http://localhost:5000/api/products"}
            ]
        }
    )

    assert captured_requests[0][0].get_method() == "GET"
    assert evidence["method"] == "GET only"
    assert evidence["endpoints"][0]["status"] == 200
    assert evidence["endpoints"][0]["response"]["count"] == 1


def test_agentic_loop_adapts_failed_review(agentic_loop, monkeypatch):
    monkeypatch.setattr(
        agentic_loop,
        "collect_evidence",
        lambda mode, _config: {"mode": mode, "record_count": 12},
    )
    responses = iter(
        [
            "PLAN REVIEWED\nInitial review",
            "DECISION: ADAPT\nAdd evidence to the recommendation.",
            "OBSERVATIONS\nFinal evidence-based review",
        ]
    )
    prompts = []

    def fake_ollama(prompt):
        prompts.append(prompt)
        return next(responses)

    result = agentic_loop.run_agentic_loop(
        "student-Chufeng",
        "database",
        ollama_call=fake_ollama,
        save=False,
    )

    assert len(prompts) == 3
    assert "COLLECTED EVIDENCE" in prompts[0]
    assert "FIRST REVIEW" in prompts[1]
    assert "REVIEW FEEDBACK" in prompts[2]
    assert result["final_review"] == "OBSERVATIONS\nFinal evidence-based review"


def test_database_grounding_detects_unsupported_table_field(agentic_loop):
    evidence = {
        "tables": {
            "products": {
                "record_count": 12,
                "columns": [{"name": "id"}, {"name": "status"}],
            },
            "cart_items": {
                "record_count": 10,
                "columns": [
                    {"name": "id"},
                    {"name": "product_id"},
                    {"name": "quantity"},
                ],
            },
        }
    }
    candidate = (
        "`cart_items` contains `id`, `product_id`, `quantity`, and `status`.\n\n"
        "All records are valid."
    )

    issues = agentic_loop._deterministic_issues(
        "database",
        evidence,
        candidate,
    )

    assert any("unsupported columns: status" in issue for issue in issues)


def test_database_fallback_uses_verified_evidence(agentic_loop):
    evidence = {
        "tables": {
            "products": {
                "record_count": 12,
                "columns": [{"name": "id"}, {"name": "status"}],
            },
            "cart_items": {
                "record_count": 10,
                "columns": [
                    {"name": "id"},
                    {"name": "product_id"},
                    {"name": "quantity"},
                ],
                "foreign_keys": [
                    {
                        "from_column": "product_id",
                        "referenced_table": "products",
                        "to_column": "id",
                        "on_delete": "CASCADE",
                    }
                ],
            },
        }
    }

    result = agentic_loop._grounded_fallback(
        "database",
        evidence,
        ["Unsupported model claim."],
    )

    assert "`products` has 12 records" in result
    assert "`cart_items` has 10 records" in result
    assert "ON DELETE CASCADE" in result
    assert "Unsupported model claim" in result


def test_database_grounding_rejects_empty_adaptation(agentic_loop):
    evidence = {
        "tables": {
            "products": {"record_count": 12, "columns": [{"name": "id"}]},
            "cart_items": {
                "record_count": 10,
                "columns": [{"name": "id"}],
            },
        }
    }

    issues = agentic_loop._deterministic_issues(
        "database",
        evidence,
        "OBSERVATIONS\nFINDINGS\nRECOMMENDATIONS\nADAPTATION APPLIED",
    )

    assert any("too short" in issue for issue in issues)


def test_database_grounding_uses_line_scoped_table_checks(agentic_loop):
    evidence = {
        "tables": {
            "products": {
                "record_count": 12,
                "columns": [
                    {"name": "id"},
                    {"name": "name"},
                    {"name": "status"},
                ],
            },
            "cart_items": {
                "record_count": 10,
                "columns": [
                    {"name": "id"},
                    {"name": "product_id"},
                    {"name": "quantity"},
                ],
            },
        }
    }
    candidate = "\n".join(
        [
            "`cart_items` has 10 records with `id`, `product_id`, and `quantity`.",
            "The `products` table contains a single row with `id`, `name`, and `status`.",
            "Add an AI Product Assistant using Ollama and Qwen.",
        ]
    )

    issues = agentic_loop._deterministic_issues(
        "database",
        evidence,
        candidate,
    )

    assert not any("cart_items discussion assigns" in issue for issue in issues)
    assert "The products record count is 12, not 1." in issues
    assert any("ai product assistant" in issue for issue in issues)


def test_agentic_loop_accepts_passing_review(agentic_loop, monkeypatch):
    monkeypatch.setattr(
        agentic_loop,
        "collect_evidence",
        lambda _mode, _config: {"status": "available"},
    )
    responses = iter(
        [
            "PLAN REVIEWED\nEvidence-based review",
            "DECISION: PASS\nThe review is supported by the evidence.",
        ]
    )
    prompts = []

    def fake_ollama(prompt):
        prompts.append(prompt)
        return next(responses)

    result = agentic_loop.run_agentic_loop(
        "student-Chufeng",
        "architecture",
        ollama_call=fake_ollama,
        save=False,
    )

    assert len(prompts) == 2
    assert result["final_review"] == result["first_review"]
