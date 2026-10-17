"""Existing loop wiring with synthetic evidence/model replies, never live proof."""

from hashlib import sha256
from importlib import import_module
import json
from pathlib import Path

import pytest

from test_report_validation import capture, SOURCE  # noqa: F401


@pytest.fixture
def report_runner(capture, monkeypatch):
    runner = import_module("agentic_loop")
    config, prompt = runner.load_feature("student-Ethan Goldman")
    config["testing_rules"]["manifest"] = "manifest.json"
    capture.collect()
    monkeypatch.setenv("RELEASE_REVIEW_SOURCE_SHA", SOURCE)
    monkeypatch.delenv("TESTING_REVIEW_MANIFEST", raising=False)
    monkeypatch.setattr(runner, "PROJECT_ROOT", capture.root)
    monkeypatch.setattr(runner, "load_feature", lambda _: (config, prompt))
    return runner, config


@pytest.mark.parametrize(
    "status", ["pass", "fail", "incomplete", "pass_with_exceptions"]
)
def test_loop_saves_review_and_independent_hashed_validation(
    report_runner, capture, status, capsys
):
    runner, _ = report_runner
    if status == "fail":
        capture.scans[0]["report"] = capture.write("ruff.json", [{"code": "S104"}])
        capture.scans[0]["exit_code"] = 1
    elif status == "incomplete":
        capture.manifest["security"].pop()
    elif status == "pass_with_exceptions":
        entry = capture.scans[2]
        entry["exit_code"] = 1
        entry["report"] = capture.write(
            "audit-findings.json",
            {
                "dependencies": [
                    {
                        "name": "fixture",
                        "version": "1.0",
                        "vulns": [{"id": "PYSEC-2026-311"}],
                    }
                ]
            },
        )
        entry["exceptions"] = [
            {
                "id": "PYSEC-2026-311",
                "reason": "Fixture limitation.",
                "record": capture.write(
                    "exception.md", b"Synthetic exception document."
                ),
            }
        ]
    capture.collect()
    before = {
        path: path.read_bytes() for path in capture.root.iterdir() if path.is_file()
    }
    prompts = []

    def model(prompt):
        prompts.append(prompt)
        assert len(prompt) <= 24000
        # Deliberately unsupported: the loop must preserve deterministic results.
        return "DETERMINISTIC STATUS: pass\nAll CI tests passed. Release approved."

    result = runner.run_agentic_loop(
        "student-Ethan Goldman", "testing", ollama_call=model
    )
    validation = json.loads(Path(result["validation_path"]).read_text())
    assert (
        validation["status"]
        == validation["evidence"]["status"]
        == result["evidence"]["status"]
        == status
    )
    assert (
        validation["source_sha"] == SOURCE
        and validation["evidence"]["remote_authenticity_verified"] is False
    )
    report = Path(result["output_path"])
    assert validation["review_sha256"] == sha256(report.read_bytes()).hexdigest()
    assert Path(result["validation_path"]).name in report.read_text()
    assert result["final_review"].startswith("DETERMINISTIC STATUS: " + status)
    assert "Release approved" not in result["final_review"]
    assert (
        "offline" in result["final_review"].lower()
        and "authenticity" in result["final_review"]
    )
    assert validation["model_grounding_issues"] and len(prompts) == 3
    assert "[VALIDATE]" in capsys.readouterr().out
    assert all(path.read_bytes() == raw for path, raw in before.items())
    if status == "pass_with_exceptions":
        assert (
            "PYSEC-2026-311" in result["final_review"]
            and "findings: 1" in result["final_review"]
        )


def test_missing_configuration_is_visible_and_no_save_writes_nothing(
    report_runner, capture, monkeypatch
):
    runner, _ = report_runner
    monkeypatch.delenv("RELEASE_REVIEW_SOURCE_SHA")
    evidence = runner.collect_testing_evidence(
        {"testing_rules": {"manifest": "manifest.json"}}
    )
    assert evidence["status"] == "incomplete" and evidence["source_sha"] is None
    assert evidence["issues"] == ["missing_or_invalid_review_configuration"]
    monkeypatch.setenv("RELEASE_REVIEW_SOURCE_SHA", SOURCE)
    before = set(capture.root.rglob("*"))
    model = lambda _: (
        "DETERMINISTIC STATUS: pass\nOffline authenticity is not independently verified. "
        + "Evidence refers to captured tests and security reports. " * 5
    )
    result = runner.run_agentic_loop(
        "student-Ethan Goldman", "testing", ollama_call=model, save=False
    )
    assert result["validation_path"] is None and result["output_path"] is None
    assert set(capture.root.rglob("*")) == before


def test_digest_keeps_every_outcome_but_bounds_file_references(report_runner):
    runner, config = report_runner
    evidence = runner.collect_testing_evidence(config)
    evidence["inputs"] *= 40
    digest = runner._evidence_digest("testing", evidence)
    decoded = json.loads(digest)
    assert (
        decoded["security"] == evidence["security"]
        and decoded["students"] == evidence["students"]
    )
    assert len(decoded["input_manifest"]) == 1 and decoded["input_count"] == len(
        evidence["inputs"]
    )
    assert len(digest) < 14000
    issues = runner._deterministic_issues(
        "testing",
        evidence,
        "DETERMINISTIC STATUS: pass\nOffline review complete. Remote authenticity is verified. "
        + "Captured evidence is sufficient. " * 10,
    )
    assert any("independently verify" in issue for issue in issues)


def test_testing_cli_menu_and_both_configurations_are_registered(capture, monkeypatch):
    runner = import_module("agentic_loop")
    assert (
        runner.build_parser()
        .parse_args(["--feature", "shared", "--mode", "testing"])
        .mode
        == "testing"
    )
    monkeypatch.setattr("builtins.input", lambda _: "9")
    assert runner._choose_mode() == "testing"
    for feature in ("shared", "student-Ethan Goldman"):
        config, _ = runner.load_feature(feature)
        assert "testing" in config["mode_prompts"]
        assert "DETERMINISTIC STATUS" in config["mode_prompts"]["testing"]
        assert (
            runner.PROJECT_ROOT / feature / "agentic" / "testing_prompt.txt"
        ).is_file()
        expected = 5 if feature == "shared" else 1
        assert len(config["testing_rules"]["required_features"]) == expected


@pytest.mark.parametrize(
    "status,code",
    [("pass", 0), ("pass_with_exceptions", 0), ("fail", 1), ("incomplete", 1)],
)
def test_report_cli_exit_status_follows_deterministic_result(
    capture, monkeypatch, status, code
):
    runner = import_module("agentic_loop")
    monkeypatch.setattr(
        runner,
        "run_agentic_loop",
        lambda *args, **kwargs: {"evidence": {"status": status}},
    )
    assert (
        runner.main(["--feature", "shared", "--mode", "testing", "--no-save"]) == code
    )


def test_repeated_saved_reviews_preserve_both_artifact_pairs(report_runner):
    runner, _ = report_runner
    text = (
        "DETERMINISTIC STATUS: pass\nOffline capture authenticity is not independently verified. "
        + "This review describes supplied structured evidence and does not establish a human decision. "
        * 3
    )
    first = runner.run_agentic_loop(
        "student-Ethan Goldman", "testing", ollama_call=lambda _: text
    )
    before = Path(first["output_path"]).read_bytes()
    second = runner.run_agentic_loop(
        "student-Ethan Goldman", "testing", ollama_call=lambda _: text
    )
    assert (
        first["output_path"] != second["output_path"]
        and first["validation_path"] != second["validation_path"]
    )
    assert Path(first["output_path"]).read_bytes() == before
    for result in (first, second):
        log = json.loads(Path(result["validation_path"]).read_text())
        assert (
            log["review_sha256"]
            == sha256(Path(result["output_path"]).read_bytes()).hexdigest()
        )
