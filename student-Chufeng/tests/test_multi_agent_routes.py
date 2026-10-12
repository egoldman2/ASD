"""Route tests for Chufeng's Product Catalogue Multi-Agent integration."""

from importlib import import_module

import pytest


controller = import_module(
    "student-Chufeng.backend.controllers.multi_agent_controller"
)
client_module = import_module(
    "student-Chufeng.backend.services.multi_agent_client"
)
DatabaseAPIError = import_module(
    "student-Chufeng.backend.models.database"
).DatabaseAPIError
MultiAgentClientError = client_module.MultiAgentClientError


def workflow(workflow_id="workflow-1", status="awaiting_human_review"):
    return {
        "workflow_id": workflow_id,
        "status": status,
        "request": {"feature": "product_catalogue"},
    }


class StubMultiAgentClient:
    def __init__(self, failure=None):
        self.failure = failure
        self.calls = []

    def _result(self, operation, *args):
        self.calls.append((operation, args))
        if self.failure is not None:
            raise self.failure
        if operation == "list_workflows":
            return {"count": 1, "workflows": [workflow()]}
        status = "accepted" if operation == "review" else "awaiting_human_review"
        return workflow(status=status)

    def health(self):
        if self.failure is not None:
            raise self.failure
        return {"status": "ok", "service": "asd-marketplace-multi-agent"}

    def create_workflow(self, payload):
        return self._result("create_workflow", payload)

    def list_workflows(self):
        return self._result("list_workflows")

    def latest_workflow(self):
        return self._result("latest_workflow")

    def get_workflow(self, workflow_id):
        return self._result("get_workflow", workflow_id)

    def submit_human_review(self, workflow_id, payload):
        return self._result("review", workflow_id, payload)


def use_stub(monkeypatch, stub):
    monkeypatch.setattr(controller, "_create_client", lambda: stub)


def test_status_reports_connected_multi_agent_service(client, monkeypatch):
    stub = StubMultiAgentClient()
    use_stub(monkeypatch, stub)

    response = client.get("/api/chufeng/multi-agent/status")

    assert response.status_code == 200
    assert response.get_json() == {
        "enabled": True,
        "available": True,
        "feature": "product_catalogue",
        "service": "asd-marketplace-multi-agent",
        "error": None,
    }


def test_status_reports_unavailable_without_failing_page(client, monkeypatch):
    failure = MultiAgentClientError(
        "The Multi-Agent server is unavailable.",
        code="MULTI_AGENT_UNAVAILABLE",
        status_code=503,
    )
    use_stub(monkeypatch, StubMultiAgentClient(failure=failure))

    response = client.get("/api/chufeng/multi-agent/status")

    assert response.status_code == 200
    assert response.get_json()["available"] is False
    assert response.get_json()["error"]["code"] == "MULTI_AGENT_UNAVAILABLE"


def test_create_workflow_uses_specific_product_from_database_api(
    client, monkeypatch
):
    stub = StubMultiAgentClient()
    use_stub(monkeypatch, stub)
    monkeypatch.setattr(
        controller,
        "_utc_timestamp",
        lambda: "2026-10-12T10:00:00Z",
    )

    response = client.post(
        "/api/chufeng/multi-agent/workflows",
        json={"question": " Is this ready for display? ", "product_id": 1},
    )

    assert response.status_code == 201
    operation, arguments = stub.calls[0]
    assert operation == "create_workflow"
    payload = arguments[0]
    assert payload["user_request"] == "Is this ready for display?"
    assert payload["feature"] == "product_catalogue"
    assert len(payload["evidence"]) == 1
    evidence = payload["evidence"][0]
    assert evidence["evidence_id"] == "catalogue-product-1"
    assert evidence["source"] == {
        "service": "product-catalogue-backend",
        "endpoint": "/api/database/products/1",
        "retrieved_at": "2026-10-12T10:00:00Z",
    }
    assert evidence["data"]["id"] == 1
    assert isinstance(evidence["data"]["name"], str)
    assert "price" in evidence["data"]


def test_create_workflow_without_id_uses_database_catalogue_snapshot(
    client, monkeypatch
):
    stub = StubMultiAgentClient()
    use_stub(monkeypatch, stub)

    response = client.post(
        "/api/chufeng/multi-agent/workflows",
        json={"question": "Which products are ready for display?"},
    )

    assert response.status_code == 201
    payload = stub.calls[0][1][0]
    evidence = payload["evidence"][0]
    assert evidence["evidence_id"] == "catalogue-products-snapshot"
    assert evidence["source"]["endpoint"] == "/api/database/products"
    assert len(evidence["data"]["products"]) > 1


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"question": ""},
        {"question": "test", "product_id": 0},
        {"question": "test", "product_id": True},
        {"question": "test", "feature": "inventory"},
        {"question": "test", "evidence": [{"data": {"price": 0}}]},
    ],
)
def test_create_rejects_invalid_or_client_supplied_evidence(
    client, monkeypatch, payload
):
    stub = StubMultiAgentClient()
    use_stub(monkeypatch, stub)

    response = client.post("/api/chufeng/multi-agent/workflows", json=payload)

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_ARGUMENT"
    assert stub.calls == []


def test_missing_product_is_404_and_does_not_call_shared_server(
    client, monkeypatch
):
    stub = StubMultiAgentClient()
    use_stub(monkeypatch, stub)

    response = client.post(
        "/api/chufeng/multi-agent/workflows",
        json={"question": "Review it", "product_id": 999999},
    )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "PRODUCT_NOT_FOUND"
    assert stub.calls == []


def test_database_failure_is_safe_and_does_not_call_shared_server(
    client, monkeypatch
):
    stub = StubMultiAgentClient()
    use_stub(monkeypatch, stub)
    monkeypatch.setattr(
        controller.product_model,
        "get_product",
        lambda _: (_ for _ in ()).throw(
            DatabaseAPIError("private database URL", 503)
        ),
    )

    response = client.post(
        "/api/chufeng/multi-agent/workflows",
        json={"question": "Review it", "product_id": 1},
    )

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "PRODUCT_DATABASE_UNAVAILABLE"
    assert "private database URL" not in response.get_data(as_text=True)
    assert stub.calls == []


def test_query_routes_forward_to_client(client, monkeypatch):
    stub = StubMultiAgentClient()
    use_stub(monkeypatch, stub)

    listed = client.get("/api/chufeng/multi-agent/workflows")
    latest = client.get("/api/chufeng/multi-agent/workflows/latest")
    selected = client.get("/api/chufeng/multi-agent/workflows/workflow-1")

    assert listed.status_code == latest.status_code == selected.status_code == 200
    assert stub.calls == [
        ("list_workflows", ()),
        ("latest_workflow", ()),
        ("get_workflow", ("workflow-1",)),
    ]


def test_review_uses_authenticated_identity_not_client_supplied_name(
    client, monkeypatch
):
    stub = StubMultiAgentClient()
    use_stub(monkeypatch, stub)

    response = client.post(
        "/api/chufeng/multi-agent/workflows/workflow-1/review",
        json={"decision": "accept", "reason": "Evidence checked."},
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "accepted"
    assert stub.calls == [
        (
            "review",
            (
                "workflow-1",
                {
                    "decision": "accept",
                    "reason": "Evidence checked.",
                    "reviewed_by": "test-admin@asd.local",
                },
            ),
        )
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"decision": "maybe", "reason": "checked"},
        {"decision": "accept", "reason": ""},
        {
            "decision": "accept",
            "reason": "checked",
            "reviewed_by": "forged@example.com",
        },
    ],
)
def test_review_rejects_invalid_or_forged_identity(
    client, monkeypatch, payload
):
    stub = StubMultiAgentClient()
    use_stub(monkeypatch, stub)

    response = client.post(
        "/api/chufeng/multi-agent/workflows/workflow-1/review",
        json=payload,
    )

    assert response.status_code == 400
    assert stub.calls == []


def test_shared_server_error_preserves_safe_status(client, monkeypatch):
    failure = MultiAgentClientError(
        "Workflow already has a human review.",
        code="workflow_already_reviewed",
        status_code=409,
    )
    stub = StubMultiAgentClient(failure=failure)
    use_stub(monkeypatch, stub)

    response = client.post(
        "/api/chufeng/multi-agent/workflows/workflow-1/review",
        json={"decision": "reject", "reason": "Already handled."},
    )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "workflow_already_reviewed"


def test_routes_require_authentication_outside_testing(monkeypatch):
    application_module = import_module("app")
    application = application_module.create_app()
    application.config.update(TESTING=False)

    response = application.test_client().post(
        "/api/chufeng/multi-agent/workflows",
        json={"question": "Review the catalogue"},
        headers={"Origin": "http://localhost:8001"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "You must sign in."
