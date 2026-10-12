from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json

import pytest

from multi_agent_server.agents.planner_agent import PlannerResult
from multi_agent_server.agents.reviewer_agent import ReviewerResult
from multi_agent_server.agents.worker_agent import WorkerResult
from multi_agent_server.contracts import HumanReviewRequest, WorkflowRequest
from multi_agent_server.workflow_store import (
    DuplicateWorkflowError,
    WorkflowAlreadyReviewedError,
    WorkflowDataError,
    WorkflowNotFoundError,
    WorkflowStateError,
    WorkflowStore,
)


NOW = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)


def workflow_request() -> WorkflowRequest:
    return WorkflowRequest.from_dict(
        {
            "user_request": "商品 12 是否需要补货？",
            "feature": "inventory",
            "evidence": [
                {
                    "evidence_id": "inventory-product-12",
                    "source": {
                        "service": "inventory-backend",
                        "endpoint": "/api/inventory/products/12",
                        "retrieved_at": "2026-10-12T09:59:00Z",
                    },
                    "data": {"stock_quantity": 3, "minimum_stock": 10},
                }
            ],
        }
    )


def results():
    evidence_ids = ("inventory-product-12",)
    return (
        PlannerResult(
            status="completed",
            agent="planner",
            model="qwen2.5:0.5b",
            objective="商品 12 是否需要补货？",
            plan="Check the supplied stock evidence.",
            evidence_ids=evidence_ids,
            human_approval_required=True,
            elapsed_ms=10,
        ),
        WorkerResult(
            status="completed",
            agent="worker",
            model="qwen2.5:0.5b",
            output="库存低于最低库存，应补货。",
            evidence_ids=evidence_ids,
            evidence_count=1,
            human_approval_required=True,
            elapsed_ms=20,
        ),
        ReviewerResult(
            status="completed",
            agent="reviewer",
            model="llama3.1:8b",
            review="结论有证据支持，等待人工确认。",
            evidence_ids=evidence_ids,
            human_approval_required=True,
            elapsed_ms=30,
        ),
    )


@pytest.fixture
def store(tmp_path):
    return WorkflowStore(
        tmp_path / "nested" / "workflow_history.jsonl",
        tmp_path / "nested" / "coordination_audit.jsonl",
        clock=lambda: NOW,
    )


def record(store: WorkflowStore, workflow_id: str = "workflow-1"):
    planner, worker, reviewer = results()
    return store.record_workflow(
        workflow_id,
        workflow_request(),
        planner,
        worker,
        reviewer,
        duration_ms=60,
    )


def test_constructor_creates_parent_directories_and_empty_files(store):
    assert store.history_path.is_file()
    assert store.audit_path.is_file()
    assert store.list_workflows() == []
    assert store.list_audit_events() == []
    assert store.get_latest_workflow() is None


def test_paths_must_be_different(tmp_path):
    path = tmp_path / "same.jsonl"
    with pytest.raises(ValueError, match="must be different"):
        WorkflowStore(path, path)


def test_record_and_query_workflow(store):
    saved = record(store)

    assert saved["workflow_id"] == "workflow-1"
    assert saved["timestamp"] == "2026-10-12T10:00:00Z"
    assert saved["status"] == "awaiting_human_review"
    assert saved["request"]["user_request"] == "商品 12 是否需要补货？"
    assert saved["human_review"] is None
    assert store.get_workflow("workflow-1") == saved
    assert store.get_latest_workflow() == saved
    assert store.list_workflows() == [saved]


def test_audit_event_is_compact_and_excludes_raw_evidence(store):
    record(store)
    audit = store.list_audit_events()[0]

    assert audit["event"] == "workflow_completed"
    assert audit["feature"] == "inventory"
    assert audit["participating_agents"] == ["planner", "worker", "reviewer"]
    assert audit["evidence_ids"] == ["inventory-product-12"]
    assert audit["evidence_count"] == 1
    assert audit["duration_ms"] == 60
    assert "evidence" not in audit
    assert "stock_quantity" not in json.dumps(audit)


def test_unicode_is_preserved_in_jsonl(store):
    record(store)
    raw = store.history_path.read_text(encoding="utf-8")
    assert "商品 12 是否需要补货？" in raw
    assert "\\u5546" not in raw


def test_duplicate_workflow_is_rejected(store):
    record(store)
    with pytest.raises(DuplicateWorkflowError, match="already exists"):
        record(store)


@pytest.mark.parametrize(
    ("decision", "expected_status"),
    [
        ("accept", "accepted"),
        ("partially_accept", "partially_accepted"),
        ("reject", "rejected"),
    ],
)
def test_human_review_updates_snapshot_and_audit(
    store, decision, expected_status
):
    record(store)
    review = HumanReviewRequest.from_dict(
        {
            "decision": decision,
            "reason": "已人工核对。",
            "reviewed_by": "Chufeng",
        }
    )

    updated = store.apply_human_review("workflow-1", review)

    assert updated["status"] == expected_status
    assert updated["human_review"] == {
        "decision": decision,
        "reason": "已人工核对。",
        "reviewed_by": "Chufeng",
        "reviewed_at": "2026-10-12T10:00:00Z",
    }
    assert len(store.list_workflows()) == 1
    audit = store.list_audit_events()[-1]
    assert audit["event"] == "human_review_recorded"
    assert audit["status"] == expected_status
    assert audit["reviewed_by"] == "Chufeng"
    assert "reason" not in audit


def test_repeated_human_review_is_rejected(store):
    record(store)
    review = HumanReviewRequest.from_dict(
        {"decision": "accept", "reason": "checked", "reviewed_by": "human"}
    )
    store.apply_human_review("workflow-1", review)

    with pytest.raises(WorkflowAlreadyReviewedError, match="already"):
        store.apply_human_review("workflow-1", review)


def test_missing_workflow_is_rejected(store):
    review = HumanReviewRequest.from_dict(
        {"decision": "reject", "reason": "wrong", "reviewed_by": "human"}
    )
    with pytest.raises(WorkflowNotFoundError, match="not found"):
        store.get_workflow("missing")
    with pytest.raises(WorkflowNotFoundError, match="not found"):
        store.apply_human_review("missing", review)


def test_query_results_are_independent_copies(store):
    saved = record(store)
    saved["status"] = "tampered"
    listed = store.list_workflows()
    listed[0]["request"]["evidence"][0]["data"]["stock_quantity"] = 999

    persisted = store.get_workflow("workflow-1")
    assert persisted["status"] == "awaiting_human_review"
    assert persisted["request"]["evidence"][0]["data"]["stock_quantity"] == 3


@pytest.mark.parametrize("bad_line", ["{bad json}", "[]"])
def test_corrupt_jsonl_reports_file_and_line(tmp_path, bad_line):
    history = tmp_path / "history.jsonl"
    history.write_text("\n" + bad_line + "\n", encoding="utf-8")
    store = WorkflowStore(history, tmp_path / "audit.jsonl")

    with pytest.raises(WorkflowDataError, match=r"line 2"):
        store.list_workflows()


def test_duplicate_ids_inside_history_are_detected(store):
    record(store)
    raw = store.history_path.read_text(encoding="utf-8")
    store.history_path.write_text(raw + raw, encoding="utf-8")

    with pytest.raises(WorkflowDataError, match="duplicate workflow_id"):
        store.list_workflows()


def test_missing_workflow_id_inside_history_is_detected(store):
    store.history_path.write_text('{"status":"broken"}\n', encoding="utf-8")
    with pytest.raises(WorkflowDataError, match="no valid workflow_id"):
        store.list_workflows()


def test_workflow_id_and_duration_are_validated(store):
    planner, worker, reviewer = results()
    with pytest.raises(ValueError, match="must not be empty"):
        store.record_workflow(
            " ", workflow_request(), planner, worker, reviewer
        )
    with pytest.raises(ValueError, match="non-negative"):
        store.record_workflow(
            "workflow-1",
            workflow_request(),
            planner,
            worker,
            reviewer,
            duration_ms=-1,
        )


@pytest.mark.parametrize("field", ["timestamp", "reviewed_at"])
def test_explicit_timestamps_require_timezone(store, field):
    if field == "timestamp":
        planner, worker, reviewer = results()
        with pytest.raises(ValueError, match="with a timezone"):
            store.record_workflow(
                "workflow-1",
                workflow_request(),
                planner,
                worker,
                reviewer,
                timestamp="2026-10-12T10:00:00",
            )
    else:
        record(store)
        review = HumanReviewRequest.from_dict(
            {"decision": "accept", "reason": "checked", "reviewed_by": "human"}
        )
        with pytest.raises(ValueError, match="with a timezone"):
            store.apply_human_review(
                "workflow-1", review, reviewed_at="2026-10-12T10:00:00"
            )


def test_inconsistent_agent_chain_is_rejected(store):
    planner, worker, reviewer = results()
    bad_worker = WorkerResult(
        status=worker.status,
        agent=worker.agent,
        model=worker.model,
        output=worker.output,
        evidence_ids=("different-evidence",),
        evidence_count=worker.evidence_count,
        human_approval_required=worker.human_approval_required,
        elapsed_ms=worker.elapsed_ms,
    )

    with pytest.raises(WorkflowStateError, match="evidence_ids"):
        store.record_workflow(
            "workflow-1",
            workflow_request(),
            planner,
            bad_worker,
            reviewer,
        )


def test_corrupt_audit_is_detected_before_history_changes(store):
    store.audit_path.write_text("not-json\n", encoding="utf-8")

    with pytest.raises(WorkflowDataError, match="invalid JSON"):
        record(store)

    assert store.list_workflows() == []


def test_clock_must_return_timezone_aware_datetime(tmp_path):
    store = WorkflowStore(
        tmp_path / "history.jsonl",
        tmp_path / "audit.jsonl",
        clock=lambda: datetime(2026, 10, 12, 10, 0),
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        record(store)


def test_concurrent_writes_do_not_lose_records(store):
    with ThreadPoolExecutor(max_workers=8) as executor:
        saved = list(
            executor.map(lambda index: record(store, f"workflow-{index}"), range(20))
        )

    assert len(saved) == 20
    assert len(store.list_workflows()) == 20
    assert len(store.list_audit_events()) == 20


def test_concurrent_duplicate_id_has_exactly_one_success(store):
    def try_record():
        try:
            record(store, "same-id")
            return "saved"
        except DuplicateWorkflowError:
            return "duplicate"

    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes = list(executor.map(lambda _: try_record(), range(8)))

    assert outcomes.count("saved") == 1
    assert outcomes.count("duplicate") == 7
    assert len(store.list_workflows()) == 1
