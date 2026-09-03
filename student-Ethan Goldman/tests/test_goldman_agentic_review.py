"""Focused tests for Ethan Goldman's uniquely named agentic-review registration."""

import importlib.util
from pathlib import Path
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENTIC_LOOP_PATH = PROJECT_ROOT / "ai-services" / "agentic_loop.py"


def load_agentic_loop(name="ethan_goldman_agentic_loop"):
    specification = importlib.util.spec_from_file_location(name, AGENTIC_LOOP_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_goldman_review_config_is_discoverable_and_complete():
    agentic_loop = load_agentic_loop()
    config, prompt = agentic_loop.load_feature("student-Ethan Goldman")

    assert "student-Ethan Goldman" in agentic_loop.discover_features()
    assert config["contributor"] == "Ethan Goldman"
    assert set(config["mode_prompts"]) == {
        "database",
        "implementation",
        "architecture",
        "devops",
    }
    assert "read-only" in prompt
    for key in ("implementation_files", "architecture_files", "devops_files"):
        assert config[key]
        assert all((PROJECT_ROOT / path).is_file() for path in config[key])


def test_file_review_collectors_are_read_only_and_redact_secrets(tmp_path):
    agentic_loop = load_agentic_loop("ethan_goldman_file_evidence")
    source = tmp_path / "workflow.yml"
    source.write_text('token: "private-token"\nrun: pytest\n', encoding="utf-8")
    before = source.read_bytes()
    agentic_loop.PROJECT_ROOT = tmp_path

    evidence = agentic_loop.collect_file_evidence(
        {"devops_files": ["workflow.yml"]},
        "devops",
    )

    assert evidence["read_only"] is True
    assert evidence["verified_checks"]["present_files"] == 1
    assert "private-token" not in evidence["files"][0]["content"]
    assert "<redacted>" in evidence["files"][0]["content"]
    assert source.read_bytes() == before


def test_goldman_database_evidence_redacts_identity_and_message_data(tmp_path):
    agentic_loop = load_agentic_loop("ethan_goldman_database_evidence")
    database_path = tmp_path / "support.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE support_tickets (
                id INTEGER PRIMARY KEY,
                customer_user_id TEXT NOT NULL,
                customer_name_snapshot TEXT NOT NULL,
                customer_email_snapshot TEXT NOT NULL
            );
            CREATE TABLE support_ticket_messages (
                id INTEGER PRIMARY KEY,
                ticket_id INTEGER NOT NULL REFERENCES support_tickets(id),
                author_name TEXT NOT NULL,
                message TEXT NOT NULL
            );
            INSERT INTO support_tickets VALUES
                (1, 'user-1', 'Private Name', 'private@example.test');
            INSERT INTO support_ticket_messages VALUES
                (1, 1, 'Private Name', 'Private ticket text');
            """
        )
    before = database_path.read_bytes()
    agentic_loop.PROJECT_ROOT = tmp_path

    evidence = agentic_loop.collect_database_evidence(
        {
            "database": "support.db",
            "database_rules": {
                "redacted_columns": {
                    "support_tickets": [
                        "customer_user_id",
                        "customer_name_snapshot",
                        "customer_email_snapshot",
                    ],
                    "support_ticket_messages": ["author_name", "message"],
                }
            },
        }
    )

    ticket = evidence["tables"]["support_tickets"]["sample_records"][0]
    message = evidence["tables"]["support_ticket_messages"]["sample_records"][0]
    assert ticket["customer_user_id"] == "<redacted>"
    assert ticket["customer_name_snapshot"] == "<redacted>"
    assert ticket["customer_email_snapshot"] == "<redacted>"
    assert message["author_name"] == "<redacted>"
    assert message["message"] == "<redacted>"
    assert database_path.read_bytes() == before


def test_goldman_static_review_modes_have_no_missing_files():
    agentic_loop = load_agentic_loop("ethan_goldman_static_evidence")
    config, _ = agentic_loop.load_feature("student-Ethan Goldman")

    for mode in ("implementation", "architecture", "devops"):
        evidence = agentic_loop.collect_evidence(mode, config)
        checks = evidence["verified_checks"]
        assert checks["configured_files"] == checks["present_files"]
        assert checks["missing_files"] == []
        assert checks["source_checks"]
        assert all(checks["source_checks"].values())


def test_static_review_rejects_truncation_and_mutation_claims():
    agentic_loop = load_agentic_loop("ethan_goldman_static_grounding")
    evidence = {
        "files": [
            {"path": ".github/workflows/EthanGoldman.yml"},
            {"path": "docker-compose.yml"},
            {"path": "student-Ethan Goldman/Dockerfile"},
        ]
    }
    candidate = """OBSERVATIONS
.github/workflows/EthanGoldman.yml, docker-compose.yml, and student-Ethan Goldman/Dockerfile are truncated, indicating they are not fully configured.
FINDINGS
The files have been reviewed and updated.
RECOMMENDATIONS
Keep the verified fully functional pipeline.
"""

    issues = agentic_loop._deterministic_issues("devops", evidence, candidate)

    assert any("does not imply" in issue for issue in issues)
    assert any("cannot claim" in issue for issue in issues)
    assert any("cannot verify" in issue for issue in issues)


def test_cli_accepts_all_four_goldman_review_modes():
    agentic_loop = load_agentic_loop("ethan_goldman_parser")
    parser = agentic_loop.build_parser()

    for mode in ("database", "implementation", "architecture", "devops"):
        parsed = parser.parse_args(
            ["--feature", "student-Ethan Goldman", "--mode", mode, "--no-save"]
        )
        assert parsed.mode == mode
