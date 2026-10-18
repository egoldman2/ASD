"""Feature-scoped transport checks; all responses are deterministic fixtures."""

from copy import deepcopy

import pytest
import requests

from shared.multi_agent_client import (
    MultiAgentClient,
    MultiAgentClientError,
    MultiAgentClientSettings,
    MultiAgentDisabledError,
)


@pytest.fixture(autouse=True)
def enable_test_ai(monkeypatch):
    monkeypatch.setenv("AI_MODE_ENABLED", "true")


def workflow(feature="customer_support", workflow_id="workflow-1"):
    evidence_id = "support-ticket-2002"
    record = {
        "workflow_id": workflow_id,
        "timestamp": "2026-10-17T00:00:00Z",
        "status": "awaiting_human_review",
        "request": {
            "feature": feature,
            "user_request": "Propose a reply; do not change the ticket.",
            "evidence": [
                {
                    "evidence_id": evidence_id,
                    "source": {
                        "service": "support-database",
                        "endpoint": "/tickets/2002/context",
                        "retrieved_at": "2026-10-17T00:00:00Z",
                    },
                    "data": {"ticket_id": 2002},
                }
            ],
        },
        "human_review": None,
    }
    for agent, field in (
        ("planner", "plan"),
        ("worker", "output"),
        ("reviewer", "review"),
    ):
        record[f"{agent}_result"] = {
            "agent": agent,
            "status": "completed",
            "model": "fixture-model",
            "evidence_ids": [evidence_id],
            "human_approval_required": True,
            field: "Fixture output for human review.",
        }
    return record


class Response:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        return deepcopy(self.payload)


def client(feature="customer_support", response=None, request=None, enabled=True):
    settings = MultiAgentClientSettings(enabled, "http://127.0.0.1:5004", 180)
    return MultiAgentClient(
        feature, settings, http_request=request or (lambda **_: Response(response))
    )


@pytest.mark.parametrize("feature", ["customer_support", "product_catalogue"])
def test_feature_creation_listing_and_encoded_retrieval(feature):
    calls = []
    record = workflow(feature, "a/b?c")

    def request(**kwargs):
        calls.append(kwargs)
        if kwargs["method"] == "GET" and kwargs["url"].endswith("/api/workflows"):
            other = (
                "product_catalogue"
                if feature == "customer_support"
                else "customer_support"
            )
            return Response({"workflows": [workflow(other), record]})
        return Response(record)

    adapter = client(feature, request=request)
    assert adapter.create_workflow(record["request"]) == record
    assert adapter.list_workflows() == {"count": 1, "workflows": [record]}
    assert adapter.get_workflow("a/b?c") == record
    assert calls[-1]["url"].endswith("/a%2Fb%3Fc")
    assert all(
        call["timeout"] == 180 and call["allow_redirects"] is False for call in calls
    )
    with pytest.raises(ValueError):
        adapter.create_workflow({"feature": "inventory"})


@pytest.mark.parametrize("flag", ["AI_MODE_ENABLED", "MULTI_AGENT_ENABLED"])
def test_disabled_flags_prevent_network(monkeypatch, flag):
    monkeypatch.setenv("AI_MODE_ENABLED", "true")
    monkeypatch.setenv("MULTI_AGENT_ENABLED", "true")
    monkeypatch.setenv(flag, "false")
    monkeypatch.setenv("MULTI_AGENT_SERVER_URL", "http://127.0.0.1:5004")
    adapter = MultiAgentClient(
        "customer_support", http_request=lambda **_: pytest.fail("network")
    )
    for action in (
        adapter.health,
        adapter.list_workflows,
        lambda: adapter.get_workflow("one"),
        lambda: adapter.create_workflow({"feature": "customer_support"}),
        lambda: adapter.submit_human_review("one", {"decision": "accept"}),
    ):
        with pytest.raises(MultiAgentDisabledError):
            action()


@pytest.mark.parametrize("feature", ["customer_support", "product_catalogue"])
def test_wrong_feature_cannot_be_read_or_reviewed(feature):
    calls = []

    def request(**kwargs):
        calls.append(kwargs)
        return Response(workflow("inventory"))

    adapter = client(feature, request=request)
    for operation in (
        lambda: adapter.get_workflow("workflow-1"),
        lambda: adapter.submit_human_review("workflow-1", {"decision": "accept"}),
    ):
        with pytest.raises(MultiAgentClientError) as error:
            operation()
        assert error.value.status_code == 404
    assert [call["method"] for call in calls] == ["GET", "GET"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "accepted"),
        ("timestamp", "not-a-date"),
        ("planner_result", None),
        ("worker_result", {}),
        ("reviewer_result", []),
        ("human_review", {}),
    ],
)
def test_support_rejects_incomplete_or_inconsistent_workflow(field, value):
    record = workflow()
    record[field] = value
    with pytest.raises(MultiAgentClientError) as error:
        client(response=record).get_workflow("workflow-1")
    assert error.value.status_code == 502


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "pending"),
        ("agent", "worker"),
        ("model", ""),
        ("plan", None),
        ("evidence_ids", ["other-ticket"]),
        ("human_approval_required", False),
    ],
)
def test_support_rejects_invalid_agent_fields(field, value):
    record = workflow()
    record["planner_result"][field] = value
    with pytest.raises(MultiAgentClientError):
        client(response=record).get_workflow("workflow-1")


@pytest.mark.parametrize("evidence", [None, [], [None], [{"evidence_id": "one"}]])
def test_support_requires_structured_evidence(evidence):
    record = workflow()
    record["request"]["evidence"] = evidence
    with pytest.raises(MultiAgentClientError):
        client(response=record).get_workflow("workflow-1")


@pytest.mark.parametrize(
    "decision,status",
    [
        ("accept", "accepted"),
        ("partially_accept", "partially_accepted"),
        ("reject", "rejected"),
    ],
)
def test_support_accepts_matching_recorded_human_decision(decision, status):
    record = workflow()
    record.update(
        status=status,
        human_review={
            "decision": decision,
            "reason": "Fixture decision",
            "reviewed_by": "staff:1",
            "reviewed_at": "2026-10-17T00:01:00Z",
        },
    )
    assert client(response=record).get_workflow("workflow-1") == record


def test_mismatched_returned_id_is_invalid_before_review_post():
    calls = []

    def request(**kwargs):
        calls.append(kwargs)
        return Response(workflow(workflow_id="other"))

    with pytest.raises(MultiAgentClientError) as error:
        client(request=request).submit_human_review(
            "workflow-1", {"decision": "accept"}
        )
    assert error.value.status_code == 502
    assert len(calls) == 1 and calls[0]["method"] == "GET"


@pytest.mark.parametrize(
    "failure,status",
    [
        (requests.Timeout("private"), 504),
        (requests.ConnectionError("private"), 503),
        (requests.RequestException("private"), 502),
    ],
)
def test_transport_errors_do_not_expose_private_details(failure, status):
    def request(**_):
        raise failure

    with pytest.raises(MultiAgentClientError) as error:
        client(request=request).list_workflows()
    assert error.value.status_code == status and "private" not in str(error.value)


@pytest.mark.parametrize("timeout", ["0", "-1", "inf", "nan", "361"])
def test_timeout_budget_is_finite_and_bounded(monkeypatch, timeout):
    monkeypatch.setenv("MULTI_AGENT_CLIENT_TIMEOUT_SECONDS", timeout)
    with pytest.raises(MultiAgentClientError):
        MultiAgentClientSettings.from_environment()


@pytest.mark.parametrize(
    "payload", [None, [], {}, {"workflows": None}, {"workflows": [None]}]
)
def test_malformed_list_is_invalid(payload):
    with pytest.raises(MultiAgentClientError) as error:
        client(response=payload).list_workflows()
    assert error.value.status_code == 502


@pytest.mark.parametrize(
    "url",
    [
        "http://[",
        "http://localhost:bad",
        "http://localhost:0",
        "file:///tmp/server",
        "http://user:password@example.test",  # pragma: allowlist secret -- rejected synthetic URL
    ],
)
def test_invalid_server_configuration_is_safe(monkeypatch, url):
    monkeypatch.setenv("MULTI_AGENT_SERVER_URL", url)
    with pytest.raises(MultiAgentClientError) as error:
        MultiAgentClientSettings.from_environment()
    assert error.value.status_code == 500
    assert url not in str(error.value)


def test_review_conflict_and_malformed_upstream_json():
    responses = iter(
        [
            Response(workflow()),
            Response(
                {
                    "error": {
                        "code": "workflow_already_reviewed",
                        "message": "Already reviewed.",
                    }
                },
                409,
            ),
        ]
    )
    with pytest.raises(MultiAgentClientError) as error:
        client(request=lambda **_: next(responses)).submit_human_review(
            "workflow-1", {}
        )
    assert (
        error.value.status_code == 409
        and error.value.code == "workflow_already_reviewed"
    )

    class InvalidJSON:
        status_code = 200

        def json(self):
            raise ValueError("private upstream body")

    with pytest.raises(MultiAgentClientError) as error:
        client(request=lambda **_: InvalidJSON()).list_workflows()
    assert error.value.status_code == 502 and "private" not in str(error.value)
