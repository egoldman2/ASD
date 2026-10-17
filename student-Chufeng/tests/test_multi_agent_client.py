"""Tests for Chufeng's backend-side Multi-Agent HTTP client."""

from importlib import import_module

import pytest
import requests


module = import_module("student-Chufeng.backend.services.multi_agent_client")
CHUFENG_FEATURE = module.CHUFENG_FEATURE
ChufengMultiAgentClient = module.ChufengMultiAgentClient
MultiAgentClientError = module.MultiAgentClientError
MultiAgentClientSettings = module.MultiAgentClientSettings
MultiAgentDisabledError = module.MultiAgentDisabledError


@pytest.fixture(autouse=True)
def enable_ai_for_isolated_transport_tests(monkeypatch):
    monkeypatch.setenv("AI_MODE_ENABLED", "true")


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


def settings(enabled=True):
    return MultiAgentClientSettings(
        enabled=enabled,
        server_url="http://127.0.0.1:5004",
        timeout_seconds=180.0,
    )


def workflow(workflow_id="workflow-1", feature=CHUFENG_FEATURE):
    return {
        "workflow_id": workflow_id,
        "status": "awaiting_human_review",
        "request": {"feature": feature},
    }


def test_settings_load_environment(monkeypatch):
    monkeypatch.setenv("MULTI_AGENT_ENABLED", "yes")
    monkeypatch.setenv("MULTI_AGENT_SERVER_URL", "http://localhost:9004/")
    monkeypatch.setenv("MULTI_AGENT_CLIENT_TIMEOUT_SECONDS", "150")

    result = MultiAgentClientSettings.from_environment()

    assert result.enabled is True
    assert result.server_url == "http://localhost:9004"
    assert result.timeout_seconds == 150.0


@pytest.mark.parametrize("timeout", ["0", "-1", "nan", "invalid"])
def test_settings_reject_invalid_timeout(monkeypatch, timeout):
    monkeypatch.setenv("MULTI_AGENT_CLIENT_TIMEOUT_SECONDS", timeout)
    with pytest.raises(MultiAgentClientError):
        MultiAgentClientSettings.from_environment()


def test_disabled_client_rejects_request_before_connecting():
    client = ChufengMultiAgentClient(
        settings(enabled=False),
        http_request=lambda **_: pytest.fail("must not connect"),
    )
    with pytest.raises(MultiAgentDisabledError):
        client.health()


def test_client_calls_workflow_endpoints_with_long_timeout():
    calls = []

    def request(**arguments):
        calls.append(arguments)
        url = arguments["url"]
        if url.endswith("/health"):
            return FakeResponse({"status": "ok", "service": "multi-agent"})
        if url.endswith("/api/workflows") and arguments["method"] == "GET":
            return FakeResponse({"count": 1, "workflows": [workflow()]})
        return FakeResponse(workflow())

    client = ChufengMultiAgentClient(settings(), http_request=request)
    create_payload = {"feature": CHUFENG_FEATURE, "evidence": []}
    review_payload = {
        "decision": "accept",
        "reason": "checked",
        "reviewed_by": "reviewer@example.com",
    }

    client.health()
    client.create_workflow(create_payload)
    client.list_workflows()
    client.get_workflow("workflow-1")
    client.submit_human_review("workflow-1", review_payload)

    assert [call["method"] for call in calls] == [
        "GET",
        "POST",
        "GET",
        "GET",
        "GET",
        "POST",
    ]
    assert all(call["timeout"] == 180.0 for call in calls)
    assert calls[1]["json"] is create_payload
    assert calls[-1]["json"] is review_payload


def test_list_filters_other_features_and_latest_uses_filtered_history():
    shared = {
        "count": 3,
        "workflows": [
            workflow("catalogue-1"),
            workflow("inventory-1", "inventory"),
            workflow("catalogue-2"),
        ],
    }
    client = ChufengMultiAgentClient(
        settings(), http_request=lambda **_: FakeResponse(shared)
    )

    result = client.list_workflows()
    latest = client.latest_workflow()

    assert result["count"] == 2
    assert [item["workflow_id"] for item in result["workflows"]] == [
        "catalogue-1",
        "catalogue-2",
    ]
    assert latest["workflow_id"] == "catalogue-2"


def test_other_feature_workflow_is_hidden_as_not_found():
    client = ChufengMultiAgentClient(
        settings(),
        http_request=lambda **_: FakeResponse(workflow(feature="inventory")),
    )

    with pytest.raises(MultiAgentClientError) as failure:
        client.get_workflow("inventory-workflow")

    assert failure.value.status_code == 404
    assert failure.value.code == "workflow_not_found"


def test_review_checks_feature_before_mutating_shared_workflow():
    calls = []

    def request(**arguments):
        calls.append(arguments)
        return FakeResponse(workflow(feature="inventory"))

    client = ChufengMultiAgentClient(settings(), http_request=request)

    with pytest.raises(MultiAgentClientError) as failure:
        client.submit_human_review("inventory-workflow", {"decision": "accept"})

    assert failure.value.status_code == 404
    assert [call["method"] for call in calls] == ["GET"]


def test_malformed_success_response_is_rejected_as_bad_gateway():
    client = ChufengMultiAgentClient(
        settings(), http_request=lambda **_: FakeResponse({"unexpected": True})
    )
    with pytest.raises(MultiAgentClientError) as failure:
        client.get_workflow("workflow-1")
    assert failure.value.status_code == 502
    assert failure.value.code == "MULTI_AGENT_INVALID_RESPONSE"


@pytest.mark.parametrize(
    ("exception", "status", "code"),
    [
        (requests.ConnectionError("private socket"), 503, "MULTI_AGENT_UNAVAILABLE"),
        (requests.Timeout("private timeout"), 504, "MULTI_AGENT_TIMEOUT"),
    ],
)
def test_transport_failures_are_safe(exception, status, code):
    def fail(**_):
        raise exception

    client = ChufengMultiAgentClient(settings(), http_request=fail)
    with pytest.raises(MultiAgentClientError) as failure:
        client.health()

    assert failure.value.status_code == status
    assert failure.value.code == code
    assert "private" not in str(failure.value)


def test_server_error_envelope_preserves_safe_status_and_code():
    responses = iter(
        (
            FakeResponse(workflow()),
            FakeResponse(
                {
                    "error": {
                        "code": "workflow_already_reviewed",
                        "message": "Workflow already has a human review.",
                    }
                },
                409,
            ),
        )
    )
    client = ChufengMultiAgentClient(
        settings(), http_request=lambda **_: next(responses)
    )

    with pytest.raises(MultiAgentClientError) as failure:
        client.submit_human_review("workflow-1", {})

    assert failure.value.status_code == 409
    assert failure.value.code == "workflow_already_reviewed"
