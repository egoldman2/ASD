"""Cloud mode wiring with synthetic captures/replies, never live release proof."""

from importlib import import_module
from hashlib import sha256
import json
from pathlib import Path

import pytest

from test_cloud_report_validation import cloud_capture  # noqa: F401
from test_report_validation import capture, SOURCE  # noqa: F401


@pytest.fixture
def cloud_runner(cloud_capture, monkeypatch):
    runner = import_module("agentic_loop")
    config, prompt = runner.load_feature("shared")
    config["cloud_deployment_rules"] = {
        "manifest": "cloud-manifest.json",
        "required_workflows": cloud_capture.cloud_paths,
    }
    cloud_capture.cloud_collect()
    monkeypatch.setenv("RELEASE_REVIEW_SOURCE_SHA", SOURCE)
    monkeypatch.delenv("CLOUD_DEPLOYMENT_REVIEW_MANIFEST", raising=False)
    monkeypatch.setattr(runner, "PROJECT_ROOT", cloud_capture.root)
    monkeypatch.setattr(runner, "load_feature", lambda _: (config, prompt))
    return runner, config


@pytest.mark.parametrize(
    "decision,status",
    [
        ("accept", "pass"),
        (None, "incomplete"),
        ("reject", "fail"),
        ("conditional_accept", "incomplete"),
    ],
)
def test_cloud_loop_preserves_technical_and_human_results(
    cloud_runner, cloud_capture, decision, status
):
    runner, _ = cloud_runner
    if decision is None:
        cloud_capture.reports.pop("human_release")
    else:
        cloud_capture.reports["human_release"].update(
            decision=decision, conditions="Synthetic pending conditions."
        )
    cloud_capture.cloud_collect()
    responses = []

    def model(prompt):
        responses.append(prompt)
        assert len(prompt) <= 24000
        return "DETERMINISTIC STATUS: pass\nRelease approved. All gates passed."

    result = runner.run_agentic_loop("shared", "cloud-deployment", ollama_call=model)
    log = json.loads(Path(result["validation_path"]).read_text())
    assert log["status"] == result["evidence"]["status"] == status
    assert log["evidence"]["technical_status"] == "pass"
    assert (
        log["review_sha256"]
        == sha256(Path(result["output_path"]).read_bytes()).hexdigest()
    )
    assert "Technical status: pass" in result["final_review"]
    assert (
        "recorded human decision: " + (decision or "missing") in result["final_review"]
    )
    assert "Release approved" not in result["final_review"]
    assert len(responses) == 3 and log["model_grounding_issues"]


def test_cloud_mode_cannot_guess_workflow_allocation(cloud_runner):
    runner, config = cloud_runner
    config["cloud_deployment_rules"]["required_workflows"] = []
    evidence = runner.collect_cloud_deployment_evidence(config)
    assert evidence["status"] == "incomplete"
    assert evidence["issues"] == ["missing_or_invalid_review_configuration"]
    assert not evidence["remote_authenticity_verified"]


def test_cloud_mode_cli_menu_configs_and_exit_status(cloud_capture, monkeypatch):
    runner = import_module("agentic_loop")
    assert (
        runner.build_parser()
        .parse_args(["--feature", "shared", "--mode", "cloud-deployment"])
        .mode
        == "cloud-deployment"
    )
    monkeypatch.setattr("builtins.input", lambda _: "10")
    assert runner._choose_mode() == "cloud-deployment"
    for feature in ("shared", "student-Ethan Goldman"):
        config, _ = runner.load_feature(feature)
        assert "cloud-deployment" in config["mode_prompts"]
        assert "DETERMINISTIC STATUS" in config["mode_prompts"]["cloud-deployment"]
        mapping = json.loads((Path(__file__).resolve().parents[2] / "cloud/student-workflows.json").read_text())
        assert config["cloud_deployment_rules"]["required_workflows"] == [row["path"] for row in mapping["workflows"]]
    monkeypatch.setattr(
        runner,
        "run_agentic_loop",
        lambda *args, **kwargs: {"evidence": {"status": "incomplete"}},
    )
    assert (
        runner.main(["--feature", "shared", "--mode", "cloud-deployment", "--no-save"])
        == 1
    )
