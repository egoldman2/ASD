"""Context fixtures are synthetic; real endpoint evidence comes from Actions."""

import json
from types import SimpleNamespace

import pytest

from shared import endpoint_ci


@pytest.fixture
def ci(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in endpoint_ci.FLAGS:
        monkeypatch.setenv(name, "false")
    for name in endpoint_ci.LIVE_OPT_INS:
        monkeypatch.setenv(name, "0")
    for name, value in {
        "GITHUB_SHA": "a" * 40, "GITHUB_REPOSITORY": "egoldman2/ASD",
        "GITHUB_WORKFLOW_REF": "egoldman2/ASD/.github/workflows/fixture.yml@refs/heads/main",
        "GITHUB_EVENT_NAME": "push", "GITHUB_REF": "refs/heads/main",
        "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
        "UNRELATED_PRIVATE_SETTING": "fixture-private-value",
    }.items():
        monkeypatch.setenv(name, value)
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(endpoint_ci.subprocess, "run", run)
    return tmp_path, calls


@pytest.mark.parametrize("feature", ["product_catalogue", "inventory", "customer_loyalty", "order_returns", "customer_support"])
def test_allocated_nodes_and_actual_context_are_retained(ci, feature):
    path, calls = ci
    assert endpoint_ci.main(["--feature", feature, "--owner", "Fixture owner"]) == 0
    raw = (path / "artifacts/test-context.json").read_text()
    context = json.loads(raw)
    assert context["feature"] == feature and context["source_sha"] == "a" * 40
    assert context["workflow"] == ".github/workflows/fixture.yml"
    assert "fixture-private-value" not in raw
    assert calls[0][0][3:5] == [entry["test_node_id"] for entry in context["endpoint_functions"]]
    assert (path / "artifacts/python-versions.txt").is_file()


def test_endpoint_failure_is_not_replaced_with_success(ci, monkeypatch):
    monkeypatch.setattr(endpoint_ci.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1))
    assert endpoint_ci.main(["--feature", "customer_support", "--owner", "Fixture owner"]) == 1


def test_enabled_live_service_prevents_endpoint_execution(ci, monkeypatch):
    monkeypatch.setenv("AI_MODE_ENABLED", "true")
    with pytest.raises(SystemExit):
        endpoint_ci.main(["--feature", "customer_support", "--owner", "Fixture owner"])
    assert ci[1] == []


def test_non_repository_test_selector_is_rejected(ci, tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"testing_rules": {"expected_endpoints": {
        "customer_support": [{"test_node_id": "--override-ini=invalid"}, {"test_node_id": "../private.py::test_private"}]
    }}}))
    monkeypatch.setattr(endpoint_ci, "CONFIG", config)
    with pytest.raises(SystemExit):
        endpoint_ci.main(["--feature", "customer_support", "--owner", "Fixture owner"])
    assert ci[1] == []
