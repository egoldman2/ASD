from __future__ import annotations

import pytest

from multi_agent_server.agents.planner_agent import PlannerResponseError
from multi_agent_server.app import SERVICE_NAME, build_coordinator, create_app
from multi_agent_server.config import MultiAgentSettings
from multi_agent_server.contracts import HumanReviewRequest, WorkflowRequest
from multi_agent_server.coordinator import WorkflowCoordinator
from multi_agent_server.model_client import (
    AgentRole,
    ModelConnectionError,
    ModelHTTPError,
    ModelResponseError,
    ModelTimeoutError,
)
from multi_agent_server.workflow_store import (
    WorkflowAlreadyReviewedError,
    WorkflowDataError,
    WorkflowNotFoundError,
)


def request_payload():
    return {
        "user_request": "商品 12 是否需要补货？",
        "feature": "inventory",
        "evidence": [
            {
                "evidence_id": "inventory-product-12",
                "source": {
                    "service": "inventory-backend",
                    "endpoint": "/api/inventory/products/12",
                    "retrieved_at": "2026-10-12T10:00:00Z",
                },
                "data": {"stock_quantity": 3, "minimum_stock": 10},
            }
        ],
    }


def workflow_record(status="awaiting_human_review"):
    return {
        "workflow_id": "workflow-1",
        "timestamp": "2026-10-12T10:00:01Z",
        "status": status,
        "request": request_payload(),
        "planner_result": {"agent": "planner"},
        "worker_result": {"agent": "worker"},
        "reviewer_result": {"agent": "reviewer"},
        "human_review": None,
    }


class FakeCoordinator:
    def __init__(self):
        self.calls = []
        self.failures = {}
        self.record = workflow_record()
        self.workflows = [self.record]

    def _invoke(self, operation, *args):
        self.calls.append((operation, args))
        failure = self.failures.get(operation)
        if failure is not None:
            raise failure

    def run(self, workflow_request):
        self._invoke("run", workflow_request)
        return self.record

    def list_workflows(self):
        self._invoke("list_workflows")
        return self.workflows

    def get_latest_workflow(self):
        self._invoke("get_latest_workflow")
        return self.workflows[-1] if self.workflows else None

    def get_workflow(self, workflow_id):
        self._invoke("get_workflow", workflow_id)
        return self.record

    def submit_human_review(self, workflow_id, review):
        self._invoke("submit_human_review", workflow_id, review)
        return {**self.record, "status": "accepted", "human_review": review.to_dict()}


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
        max_request_bytes=1_024,
        log_dir=tmp_path,
    )


@pytest.fixture
def api(settings):
    coordinator = FakeCoordinator()
    app = create_app(settings, coordinator)
    app.config.update(TESTING=True)
    return app.test_client(), coordinator, app


def test_health_is_lightweight_and_does_not_run_workflow(api):
    client, coordinator, _ = api
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json == {"status": "ok", "service": SERVICE_NAME}
    assert coordinator.calls == []


def test_create_workflow_validates_and_forwards_request(api):
    client, coordinator, _ = api
    response = client.post("/api/workflows", json=request_payload())

    assert response.status_code == 201
    assert response.json == workflow_record()
    assert len(coordinator.calls) == 1
    operation, arguments = coordinator.calls[0]
    assert operation == "run"
    assert isinstance(arguments[0], WorkflowRequest)
    assert arguments[0].to_dict() == request_payload()


def test_list_latest_and_get_workflow_routes(api):
    client, coordinator, _ = api

    listed = client.get("/api/workflows")
    latest = client.get("/api/workflows/latest")
    selected = client.get("/api/workflows/workflow-1")

    assert listed.status_code == latest.status_code == selected.status_code == 200
    assert listed.json == {"count": 1, "workflows": [workflow_record()]}
    assert latest.json == selected.json == workflow_record()
    assert coordinator.calls == [
        ("list_workflows", ()),
        ("get_latest_workflow", ()),
        ("get_workflow", ("workflow-1",)),
    ]


def test_latest_returns_404_when_history_is_empty(api):
    client, coordinator, _ = api
    coordinator.workflows = []

    response = client.get("/api/workflows/latest")

    assert response.status_code == 404
    assert response.json["error"]["code"] == "workflow_not_found"


def test_human_review_is_validated_and_forwarded(api):
    client, coordinator, _ = api
    payload = {
        "decision": "accept",
        "reason": "已核对证据。",
        "reviewed_by": "Chufeng",
    }

    response = client.post("/api/workflows/workflow-1/review", json=payload)

    assert response.status_code == 200
    assert response.json["status"] == "accepted"
    operation, arguments = coordinator.calls[0]
    assert operation == "submit_human_review"
    assert arguments[0] == "workflow-1"
    assert isinstance(arguments[1], HumanReviewRequest)
    assert arguments[1].to_dict() == payload


def test_non_json_and_malformed_json_are_rejected_without_coordinator_call(api):
    client, coordinator, _ = api

    non_json = client.post("/api/workflows", data="plain text")
    malformed = client.post(
        "/api/workflows",
        data="{",
        content_type="application/json",
    )

    assert non_json.status_code == 415
    assert non_json.json["error"]["code"] == "unsupported_media_type"
    assert malformed.status_code == 400
    assert malformed.json["error"]["code"] == "invalid_json"
    assert coordinator.calls == []


def test_contract_errors_keep_machine_readable_field(api):
    client, coordinator, _ = api
    payload = request_payload()
    payload["feature"] = "not-a-feature"

    response = client.post("/api/workflows", json=payload)

    assert response.status_code == 400
    assert response.json["error"]["code"] == "invalid_choice"
    assert response.json["error"]["field"] == "feature"
    assert coordinator.calls == []


def test_invalid_human_review_is_rejected_before_coordinator(api):
    client, coordinator, _ = api
    response = client.post(
        "/api/workflows/workflow-1/review",
        json={"decision": "maybe", "reason": "x", "reviewed_by": "human"},
    )

    assert response.status_code == 400
    assert response.json["error"]["field"] == "decision"
    assert coordinator.calls == []


def test_oversized_request_is_rejected(api):
    client, coordinator, _ = api
    response = client.post(
        "/api/workflows",
        data='{"user_request":"' + ("x" * 2_000) + '"}',
        content_type="application/json",
    )

    assert response.status_code == 413
    assert response.json["error"]["code"] == "request_too_large"
    assert "1024" in response.json["error"]["message"]
    assert coordinator.calls == []


@pytest.mark.parametrize(
    ("failure", "expected_status", "expected_code"),
    [
        (
            WorkflowNotFoundError("Workflow 'missing' was not found."),
            404,
            "workflow_not_found",
        ),
        (
            WorkflowAlreadyReviewedError("Workflow already reviewed."),
            409,
            "workflow_already_reviewed",
        ),
        (
            ModelConnectionError(
                "Could not connect to Ollama.",
                role=AgentRole.PLANNER,
                model="planner-model",
            ),
            503,
            "model_connection_error",
        ),
        (
            ModelTimeoutError(
                "Ollama timed out.",
                role=AgentRole.WORKER,
                model="worker-model",
            ),
            504,
            "model_timeout",
        ),
        (
            ModelHTTPError(
                "Ollama returned HTTP 500.",
                role=AgentRole.REVIEWER,
                model="reviewer-model",
                status_code=500,
            ),
            502,
            "model_http_error",
        ),
        (
            ModelResponseError(
                "Ollama returned invalid JSON.",
                role=AgentRole.REVIEWER,
                model="reviewer-model",
            ),
            502,
            "model_response_error",
        ),
        (
            PlannerResponseError(("missing Steps:",)),
            502,
            "planner_response_error",
        ),
    ],
)
def test_service_failures_map_to_stable_http_errors(
    api, failure, expected_status, expected_code
):
    client, coordinator, _ = api
    coordinator.failures["run"] = failure

    response = client.post("/api/workflows", json=request_payload())

    assert response.status_code == expected_status
    assert response.json["error"]["code"] == expected_code
    assert "traceback" not in response.get_data(as_text=True).lower()


def test_store_failure_hides_file_details(api):
    client, coordinator, _ = api
    coordinator.failures["list_workflows"] = WorkflowDataError(
        "C:/private/history.jsonl line 2 is invalid"
    )

    response = client.get("/api/workflows")

    assert response.status_code == 500
    assert response.json["error"]["code"] == "workflow_store_error"
    assert "C:/private" not in response.get_data(as_text=True)


def test_unexpected_error_is_hidden(api):
    client, coordinator, app = api
    coordinator.failures["run"] = RuntimeError("private prompt and evidence")
    app.config["PROPAGATE_EXCEPTIONS"] = False

    response = client.post("/api/workflows", json=request_payload())

    assert response.status_code == 500
    assert response.json["error"]["code"] == "internal_error"
    assert "private prompt" not in response.get_data(as_text=True)


def test_unknown_endpoint_and_wrong_method_return_json(api):
    client, _, _ = api
    missing = client.get("/not-real")
    wrong_method = client.delete("/api/workflows")

    assert missing.status_code == 404
    assert missing.json["error"]["code"] == "endpoint_not_found"
    assert wrong_method.status_code == 405
    assert wrong_method.json["error"]["code"] == "method_not_allowed"


def test_api_routes_include_cors_headers(api):
    client, _, _ = api
    response = client.get(
        "/api/workflows",
        headers={"Origin": "http://localhost:5000"},
    )
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5000"


def test_build_coordinator_constructs_real_graph_without_network(settings):
    instance = build_coordinator(settings)

    assert isinstance(instance, WorkflowCoordinator)
    assert settings.history_path.is_file()
    assert settings.audit_path.is_file()


def test_create_app_builds_default_coordinator(settings):
    app = create_app(settings=settings)
    assert isinstance(app.extensions["workflow_coordinator"], WorkflowCoordinator)
    assert app.config["MAX_CONTENT_LENGTH"] == 1_024
    assert app.test_client().get("/health").status_code == 200


def test_create_app_rejects_incomplete_coordinator(settings):
    with pytest.raises(TypeError, match="coordinator must provide"):
        create_app(settings, object())
