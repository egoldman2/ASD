from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import pytest

from multi_agent_server.agents.planner_agent import PlannerAgent, PlannerResult
from multi_agent_server.agents.reviewer_agent import ReviewerAgent, ReviewerResult
from multi_agent_server.agents.worker_agent import WorkerAgent, WorkerResult
from multi_agent_server.contracts import HumanReviewRequest, WorkflowRequest
from multi_agent_server.coordinator import WorkflowCoordinator
from multi_agent_server.model_client import AgentRole, ModelGeneration
from multi_agent_server.workflow_store import WorkflowStore


WORKFLOW_UUID = UUID("12345678-1234-5678-1234-567812345678")


def request() -> WorkflowRequest:
    return WorkflowRequest.from_dict(
        {
            "user_request": "Determine whether product 12 needs restocking.",
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
    )


def planner_result() -> PlannerResult:
    return PlannerResult(
        status="completed",
        agent="planner",
        model="planner-model",
        objective="Determine whether product 12 needs restocking.",
        plan="Analyse the supplied stock evidence.",
        evidence_ids=("inventory-product-12",),
        human_approval_required=True,
        elapsed_ms=10,
    )


def worker_result() -> WorkerResult:
    return WorkerResult(
        status="completed",
        agent="worker",
        model="worker-model",
        output="Product 12 needs restocking.",
        evidence_ids=("inventory-product-12",),
        evidence_count=1,
        human_approval_required=True,
        elapsed_ms=20,
    )


def reviewer_result() -> ReviewerResult:
    return ReviewerResult(
        status="completed",
        agent="reviewer",
        model="reviewer-model",
        review="The conclusion is supported; human approval is still required.",
        evidence_ids=("inventory-product-12",),
        human_approval_required=True,
        elapsed_ms=30,
    )


class RecordingPlanner:
    def __init__(self, events, result=None, error=None):
        self.events = events
        self.result = result or planner_result()
        self.error = error

    def plan(self, workflow_request):
        self.events.append(("planner", workflow_request))
        if self.error:
            raise self.error
        return self.result


class RecordingWorker:
    def __init__(self, events, result=None, error=None):
        self.events = events
        self.result = result or worker_result()
        self.error = error

    def execute(self, workflow_request, plan):
        self.events.append(("worker", workflow_request, plan))
        if self.error:
            raise self.error
        return self.result


class RecordingReviewer:
    def __init__(self, events, result=None, error=None):
        self.events = events
        self.result = result or reviewer_result()
        self.error = error

    def review(self, workflow_request, plan, output):
        self.events.append(("reviewer", workflow_request, plan, output))
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def store(tmp_path):
    return WorkflowStore(tmp_path / "history.jsonl", tmp_path / "audit.jsonl")


def coordinator(store, *, planner=None, worker=None, reviewer=None, timer=None):
    events = []
    instance = WorkflowCoordinator(
        planner or RecordingPlanner(events),
        worker or RecordingWorker(events),
        reviewer or RecordingReviewer(events),
        store,
        id_factory=lambda: WORKFLOW_UUID,
        timer=timer or iter((10.0, 10.125)).__next__,
    )
    return instance, events


def test_run_executes_agents_in_order_and_forwards_exact_results(store):
    workflow_request = request()
    instance, events = coordinator(store)

    saved = instance.run(workflow_request)

    assert [event[0] for event in events] == ["planner", "worker", "reviewer"]
    assert events[0][1] is workflow_request
    assert events[1][1] is workflow_request
    assert events[1][2] == planner_result()
    assert events[2][1] is workflow_request
    assert events[2][2] == planner_result()
    assert events[2][3] == worker_result()
    assert saved["planner_result"] == planner_result().to_dict()
    assert saved["worker_result"] == worker_result().to_dict()
    assert saved["reviewer_result"] == reviewer_result().to_dict()


def test_run_generates_uuid_tracks_duration_and_persists_once(store):
    instance, _ = coordinator(store)

    saved = instance.run(request())

    assert saved["workflow_id"] == str(WORKFLOW_UUID)
    assert saved["status"] == "awaiting_human_review"
    assert len(store.list_workflows()) == 1
    audit = store.list_audit_events()
    assert len(audit) == 1
    assert audit[0]["duration_ms"] == 125


def test_coordinator_integrates_real_agent_classes(store):
    responses = {
        AgentRole.PLANNER: """Objective: Decide whether to restock product 12.
Steps:
1. Worker Agent: analyse inventory-product-12 only.
2. Reviewer Agent: verify the Worker Agent result.
3. Human Reviewer: decide whether to accept it.
Evidence Required: inventory-product-12.
Human Approval: Required.""",
        AgentRole.WORKER: """Output: Product 12 needs restocking.
Evidence Used: inventory-product-12.
Limitations: None identified.""",
        AgentRole.REVIEWER: """Risk: LOW because inventory-product-12 supports the output.
Correction: None
Retest: Not required
Recommendation: Accept for human consideration based on inventory-product-12.""",
    }

    class ScriptedModelClient:
        def generate(self, role, prompt):
            return ModelGeneration(
                role=role,
                model=f"{role.value}-model",
                text=responses[role],
                elapsed_ms=5,
            )

    client = ScriptedModelClient()
    instance = WorkflowCoordinator(
        PlannerAgent(client),
        WorkerAgent(client),
        ReviewerAgent(client),
        store,
        id_factory=lambda: WORKFLOW_UUID,
        timer=iter((1.0, 1.2)).__next__,
    )

    saved = instance.run(request())

    assert saved["planner_result"]["agent"] == "planner"
    assert saved["worker_result"]["agent"] == "worker"
    assert saved["reviewer_result"]["agent"] == "reviewer"
    assert saved["status"] == "awaiting_human_review"


@pytest.mark.parametrize("stage", ["planner", "worker", "reviewer"])
def test_agent_failure_stops_chain_and_does_not_persist(store, stage):
    events = []
    failure = RuntimeError(f"{stage} failed")
    planner = RecordingPlanner(events, error=failure if stage == "planner" else None)
    worker = RecordingWorker(events, error=failure if stage == "worker" else None)
    reviewer = RecordingReviewer(
        events, error=failure if stage == "reviewer" else None
    )
    instance = WorkflowCoordinator(
        planner,
        worker,
        reviewer,
        store,
        id_factory=lambda: WORKFLOW_UUID,
    )

    with pytest.raises(RuntimeError, match=f"{stage} failed"):
        instance.run(request())

    expected_events = {
        "planner": ["planner"],
        "worker": ["planner", "worker"],
        "reviewer": ["planner", "worker", "reviewer"],
    }[stage]
    assert [event[0] for event in events] == expected_events
    assert store.list_workflows() == []
    assert store.list_audit_events() == []


def test_store_validation_failure_propagates_without_partial_record(store):
    events = []
    bad_reviewer = replace(reviewer_result(), evidence_ids=("wrong-id",))
    instance = WorkflowCoordinator(
        RecordingPlanner(events),
        RecordingWorker(events),
        RecordingReviewer(events, result=bad_reviewer),
        store,
        id_factory=lambda: WORKFLOW_UUID,
    )

    with pytest.raises(RuntimeError, match="evidence_ids"):
        instance.run(request())

    assert store.list_workflows() == []


def test_negative_elapsed_time_is_clamped_to_zero(store):
    instance, _ = coordinator(store, timer=iter((20.0, 19.0)).__next__)
    instance.run(request())
    assert store.list_audit_events()[0]["duration_ms"] == 0


def test_submit_human_review_and_queries_delegate_to_store(store):
    instance, _ = coordinator(store)
    saved = instance.run(request())
    review = HumanReviewRequest.from_dict(
        {
            "decision": "accept",
            "reason": "Evidence checked.",
            "reviewed_by": "Chufeng",
        }
    )

    reviewed = instance.submit_human_review(saved["workflow_id"], review)

    assert reviewed["status"] == "accepted"
    assert instance.get_workflow(saved["workflow_id"]) == reviewed
    assert instance.get_latest_workflow() == reviewed
    assert instance.list_workflows() == [reviewed]


@pytest.mark.parametrize("bad_request", [None, {}, "request"])
def test_run_requires_validated_workflow_request(store, bad_request):
    instance, events = coordinator(store)
    with pytest.raises(TypeError, match="must be a WorkflowRequest"):
        instance.run(bad_request)
    assert events == []


@pytest.mark.parametrize("bad_id", ["", "   "])
def test_id_factory_must_return_non_empty_id(store, bad_id):
    events = []
    instance = WorkflowCoordinator(
        RecordingPlanner(events),
        RecordingWorker(events),
        RecordingReviewer(events),
        store,
        id_factory=lambda: bad_id,
    )
    with pytest.raises(ValueError, match="non-empty"):
        instance.run(request())
    assert events == []


def test_id_factory_must_return_string_or_uuid(store):
    events = []
    instance = WorkflowCoordinator(
        RecordingPlanner(events),
        RecordingWorker(events),
        RecordingReviewer(events),
        store,
        id_factory=lambda: 123,
    )
    with pytest.raises(TypeError, match="string or UUID"):
        instance.run(request())
    assert events == []


def test_timer_must_return_number(store):
    instance, _ = coordinator(store, timer=lambda: "now")
    with pytest.raises(TypeError, match="timer must return a number"):
        instance.run(request())
    assert store.list_workflows() == []


@pytest.mark.parametrize(
    ("position", "replacement", "message"),
    [
        (0, object(), "planner must provide"),
        (1, object(), "worker must provide"),
        (2, object(), "reviewer must provide"),
    ],
)
def test_constructor_validates_agent_interfaces(
    store, position, replacement, message
):
    events = []
    dependencies = [
        RecordingPlanner(events),
        RecordingWorker(events),
        RecordingReviewer(events),
    ]
    dependencies[position] = replacement
    with pytest.raises(TypeError, match=message):
        WorkflowCoordinator(*dependencies, store)


def test_constructor_requires_workflow_store(tmp_path):
    events = []
    with pytest.raises(TypeError, match="store must be a WorkflowStore"):
        WorkflowCoordinator(
            RecordingPlanner(events),
            RecordingWorker(events),
            RecordingReviewer(events),
            object(),
        )
