from __future__ import annotations

from io import StringIO
import json
from pathlib import Path

import pytest

from multi_agent_server.config import ConfigurationError, MultiAgentSettings
from multi_agent_server.contracts import Feature, WorkflowRequest
from multi_agent_server.model_client import AgentRole, ModelConnectionError
from multi_agent_server.workflow_runner import (
    EXIT_INPUT_ERROR,
    EXIT_INTERNAL_ERROR,
    EXIT_MODEL_ERROR,
    EXIT_OK,
    EXIT_SERVICE_ERROR,
    load_workflow_request,
    run_cli,
)
from multi_agent_server.workflow_store import WorkflowDataError


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def request_payload(feature="inventory", secret="中文证据内容"):
    return {
        "user_request": "商品 12 是否需要补货？",
        "feature": feature,
        "evidence": [
            {
                "evidence_id": "evidence-12",
                "source": {
                    "service": "feature-backend",
                    "endpoint": "/api/items/12",
                    "retrieved_at": "2026-10-12T10:00:00Z",
                },
                "data": {"secret": secret, "quantity": 3},
            }
        ],
    }


def workflow_result(workflow_request):
    evidence_ids = [item.evidence_id for item in workflow_request.evidence]
    return {
        "workflow_id": "workflow-1",
        "timestamp": "2026-10-12T10:00:01Z",
        "status": "awaiting_human_review",
        "request": workflow_request.to_dict(),
        "planner_result": {
            "status": "completed",
            "agent": "planner",
            "model": "planner-model",
            "objective": workflow_request.user_request,
            "plan": "Planner 中文计划",
            "evidence_ids": evidence_ids,
            "human_approval_required": True,
            "elapsed_ms": 10,
        },
        "worker_result": {
            "status": "completed",
            "agent": "worker",
            "model": "worker-model",
            "output": "Worker 中文结论",
            "evidence_ids": evidence_ids,
            "evidence_count": len(evidence_ids),
            "human_approval_required": True,
            "elapsed_ms": 20,
        },
        "reviewer_result": {
            "status": "completed",
            "agent": "reviewer",
            "model": "reviewer-model",
            "review": "Reviewer 中文审核",
            "evidence_ids": evidence_ids,
            "human_approval_required": True,
            "elapsed_ms": 30,
        },
        "human_review": None,
    }


class FakeCoordinator:
    def __init__(self, *, failure=None):
        self.failure = failure
        self.requests = []

    def run(self, workflow_request):
        self.requests.append(workflow_request)
        if self.failure is not None:
            raise self.failure
        return workflow_result(workflow_request)


@pytest.fixture
def settings(tmp_path):
    return MultiAgentSettings(
        host="127.0.0.1",
        port=5004,
        ollama_url="http://localhost:11434",
        planner_model="planner-model",
        worker_model="worker-model",
        reviewer_model="reviewer-model",
        timeout_seconds=2.0,
        max_request_bytes=65_536,
        log_dir=tmp_path,
    )


def write_request(tmp_path, payload=None):
    path = tmp_path / "request.json"
    path.write_text(
        json.dumps(payload or request_payload(), ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def invoke(path, settings, coordinator, *extra_args):
    stdout = StringIO()
    stderr = StringIO()
    factories = []

    def factory(received_settings):
        factories.append(received_settings)
        return coordinator

    exit_code = run_cli(
        ["--input", str(path), *extra_args],
        settings_loader=lambda: settings,
        coordinator_factory=factory,
        stdout=stdout,
        stderr=stderr,
    )
    return exit_code, stdout.getvalue(), stderr.getvalue(), factories


def test_human_output_runs_validated_request_and_prints_summary(tmp_path, settings):
    path = write_request(tmp_path)
    coordinator = FakeCoordinator()

    exit_code, stdout, stderr, factories = invoke(path, settings, coordinator)

    assert exit_code == EXIT_OK
    assert stderr == ""
    assert factories == [settings]
    assert len(coordinator.requests) == 1
    assert isinstance(coordinator.requests[0], WorkflowRequest)
    assert "Workflow ID: workflow-1" in stdout
    assert "Feature: inventory" in stdout
    assert "Evidence IDs: evidence-12" in stdout
    assert "Planner 中文计划" in stdout
    assert "Worker 中文结论" in stdout
    assert "Reviewer 中文审核" in stdout
    assert str(settings.history_path) in stdout


def test_json_output_is_parseable_and_preserves_unicode(tmp_path, settings):
    path = write_request(tmp_path)

    exit_code, stdout, stderr, _ = invoke(
        path, settings, FakeCoordinator(), "--json"
    )

    assert exit_code == EXIT_OK
    assert stderr == ""
    decoded = json.loads(stdout)
    assert decoded["workflow_id"] == "workflow-1"
    assert decoded["request"]["user_request"] == "商品 12 是否需要补货？"
    assert "商品" in stdout
    assert "\\u5546" not in stdout


@pytest.mark.parametrize(
    ("filename", "feature"),
    [
        ("inventory_request.json", Feature.INVENTORY),
        ("product_catalogue_request.json", Feature.PRODUCT_CATALOGUE),
    ],
)
def test_checked_in_examples_are_valid_and_feature_neutral(filename, feature):
    workflow_request = load_workflow_request(EXAMPLES_DIR / filename)
    assert workflow_request.feature is feature
    assert workflow_request.evidence[0].data


def test_missing_file_returns_input_error_without_building_coordinator(
    tmp_path, settings
):
    coordinator = FakeCoordinator()
    exit_code, stdout, stderr, factories = invoke(
        tmp_path / "missing.json", settings, coordinator
    )

    assert exit_code == EXIT_INPUT_ERROR
    assert stdout == ""
    assert "input_not_found" in stderr
    assert factories == []
    assert coordinator.requests == []


def test_directory_path_returns_input_error(tmp_path, settings):
    exit_code, _, stderr, factories = invoke(
        tmp_path, settings, FakeCoordinator()
    )
    assert exit_code == EXIT_INPUT_ERROR
    assert "invalid_input_path" in stderr
    assert factories == []


def test_non_utf8_file_returns_input_error(tmp_path, settings):
    path = tmp_path / "request.json"
    path.write_bytes(b"\xff\xfe\x00")

    exit_code, _, stderr, factories = invoke(path, settings, FakeCoordinator())

    assert exit_code == EXIT_INPUT_ERROR
    assert "invalid_encoding" in stderr
    assert factories == []


def test_malformed_json_reports_location_without_traceback(tmp_path, settings):
    path = tmp_path / "request.json"
    path.write_text('{"user_request": }', encoding="utf-8")

    exit_code, _, stderr, factories = invoke(path, settings, FakeCoordinator())

    assert exit_code == EXIT_INPUT_ERROR
    assert "invalid_json" in stderr
    assert "line 1" in stderr
    assert "Traceback" not in stderr
    assert factories == []


def test_contract_error_is_machine_readable_and_does_not_run(tmp_path, settings):
    payload = request_payload()
    payload["feature"] = "unknown"
    path = write_request(tmp_path, payload)
    coordinator = FakeCoordinator()

    exit_code, _, stderr, factories = invoke(path, settings, coordinator)

    assert exit_code == EXIT_INPUT_ERROR
    assert "invalid_choice" in stderr
    assert "feature:" in stderr
    assert factories == []
    assert coordinator.requests == []


def test_model_error_uses_nonzero_exit_without_leaking_evidence(tmp_path, settings):
    secret = "DO-NOT-LEAK-EVIDENCE"
    path = write_request(tmp_path, request_payload(secret=secret))
    failure = ModelConnectionError(
        "Could not connect to the Ollama server.",
        role=AgentRole.PLANNER,
        model="planner-model",
    )

    exit_code, stdout, stderr, _ = invoke(
        path, settings, FakeCoordinator(failure=failure)
    )

    assert exit_code == EXIT_MODEL_ERROR
    assert stdout == ""
    assert "model_connection_error" in stderr
    assert secret not in stderr
    assert "Traceback" not in stderr


def test_store_error_hides_private_path(tmp_path, settings):
    path = write_request(tmp_path)
    failure = WorkflowDataError("C:/private/history.jsonl is damaged")

    exit_code, _, stderr, _ = invoke(
        path, settings, FakeCoordinator(failure=failure)
    )

    assert exit_code == EXIT_SERVICE_ERROR
    assert "workflow_store_error" in stderr
    assert "C:/private" not in stderr


def test_configuration_error_has_service_exit_code(tmp_path, settings):
    path = write_request(tmp_path)
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli(
        ["--input", str(path)],
        settings_loader=lambda: (_ for _ in ()).throw(
            ConfigurationError("MULTI_AGENT_PORT must be an integer.")
        ),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == EXIT_SERVICE_ERROR
    assert stdout.getvalue() == ""
    assert "configuration_error" in stderr.getvalue()


def test_unexpected_error_is_hidden(tmp_path, settings):
    secret = "private prompt contents"
    path = write_request(tmp_path)

    exit_code, stdout, stderr, _ = invoke(
        path,
        settings,
        FakeCoordinator(failure=RuntimeError(secret)),
    )

    assert exit_code == EXIT_INTERNAL_ERROR
    assert stdout == ""
    assert "internal_error" in stderr
    assert secret not in stderr
    assert "Traceback" not in stderr
