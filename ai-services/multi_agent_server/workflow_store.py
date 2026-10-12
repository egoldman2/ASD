"""Thread-safe workflow history and compact coordination audit storage."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any

from multi_agent_server.agents.planner_agent import PlannerResult
from multi_agent_server.agents.reviewer_agent import ReviewerResult
from multi_agent_server.agents.worker_agent import WorkerResult
from multi_agent_server.contracts import HumanReviewRequest, WorkflowRequest


class WorkflowStoreError(RuntimeError):
    """Base class for workflow persistence failures."""


class WorkflowDataError(WorkflowStoreError):
    """Raised when persisted JSONL data is malformed or inconsistent."""


class DuplicateWorkflowError(WorkflowStoreError):
    """Raised when a workflow ID already exists."""


class WorkflowNotFoundError(WorkflowStoreError):
    """Raised when a requested workflow ID does not exist."""


class WorkflowAlreadyReviewedError(WorkflowStoreError):
    """Raised when a second human decision is submitted."""


class WorkflowStateError(WorkflowStoreError):
    """Raised when agent results do not form one completed workflow."""


_DECISION_STATUSES = {
    "accept": "accepted",
    "partially_accept": "partially_accepted",
    "reject": "rejected",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("clock must return a timezone-aware datetime.")
    return value.isoformat().replace("+00:00", "Z")


def _validated_timestamp(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty ISO 8601 timestamp.")
    clean = value.strip()
    try:
        parsed = datetime.fromisoformat(clean.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"{field} must be an ISO 8601 timestamp with a timezone."
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(
            f"{field} must be an ISO 8601 timestamp with a timezone."
        )
    return clean


class WorkflowStore:
    """Persist workflow snapshots and append-only audit events as JSONL."""

    def __init__(
        self,
        history_path: Path | str,
        audit_path: Path | str,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.history_path = Path(history_path)
        self.audit_path = Path(audit_path)
        if self.history_path.resolve() == self.audit_path.resolve():
            raise ValueError("history_path and audit_path must be different.")
        if not callable(clock):
            raise TypeError("clock must be callable.")
        self._clock = clock
        self._lock = threading.RLock()
        self._ensure_files()

    def record_workflow(
        self,
        workflow_id: str,
        workflow_request: WorkflowRequest,
        planner_result: PlannerResult,
        worker_result: WorkerResult,
        reviewer_result: ReviewerResult,
        *,
        duration_ms: int | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        """Store one completed agent chain and append its compact audit event."""

        clean_id = self._workflow_id(workflow_id)
        self._validate_stage_types(
            workflow_request,
            planner_result,
            worker_result,
            reviewer_result,
        )
        if duration_ms is not None and (
            isinstance(duration_ms, bool)
            or not isinstance(duration_ms, int)
            or duration_ms < 0
        ):
            raise ValueError("duration_ms must be a non-negative integer.")
        recorded_at = (
            self._now()
            if timestamp is None
            else _validated_timestamp(timestamp, "timestamp")
        )

        record = {
            "workflow_id": clean_id,
            "timestamp": recorded_at,
            "status": "awaiting_human_review",
            "request": workflow_request.to_dict(),
            "planner_result": planner_result.to_dict(),
            "worker_result": worker_result.to_dict(),
            "reviewer_result": reviewer_result.to_dict(),
            "human_review": None,
        }
        audit_event: dict[str, Any] = {
            "event": "workflow_completed",
            "workflow_id": clean_id,
            "timestamp": recorded_at,
            "feature": workflow_request.feature.value,
            "participating_agents": ["planner", "worker", "reviewer"],
            "models": {
                "planner": planner_result.model,
                "worker": worker_result.model,
                "reviewer": reviewer_result.model,
            },
            "evidence_ids": [
                item.evidence_id for item in workflow_request.evidence
            ],
            "evidence_count": len(workflow_request.evidence),
            "status": "awaiting_human_review",
        }
        if duration_ms is not None:
            audit_event["duration_ms"] = duration_ms

        with self._lock:
            records = self._read_history()
            self._read_jsonl(self.audit_path)
            if any(item["workflow_id"] == clean_id for item in records):
                raise DuplicateWorkflowError(
                    f"Workflow '{clean_id}' already exists."
                )
            self._append_jsonl(self.history_path, record)
            self._append_jsonl(self.audit_path, audit_event)
        return deepcopy(record)

    def apply_human_review(
        self,
        workflow_id: str,
        review: HumanReviewRequest,
        *,
        reviewed_at: str | None = None,
    ) -> dict[str, Any]:
        """Apply the workflow's single allowed human decision."""

        clean_id = self._workflow_id(workflow_id)
        if not isinstance(review, HumanReviewRequest):
            raise TypeError("review must be a HumanReviewRequest.")
        decision_time = (
            self._now()
            if reviewed_at is None
            else _validated_timestamp(reviewed_at, "reviewed_at")
        )

        with self._lock:
            records = self._read_history()
            self._read_jsonl(self.audit_path)
            matching_indexes = [
                index
                for index, item in enumerate(records)
                if item["workflow_id"] == clean_id
            ]
            if not matching_indexes:
                raise WorkflowNotFoundError(
                    f"Workflow '{clean_id}' was not found."
                )
            record = records[matching_indexes[0]]
            if record.get("human_review") is not None:
                raise WorkflowAlreadyReviewedError(
                    f"Workflow '{clean_id}' already has a human review."
                )

            review_data = review.to_dict()
            review_data["reviewed_at"] = decision_time
            record["human_review"] = review_data
            record["status"] = _DECISION_STATUSES[review.decision.value]
            self._rewrite_jsonl(self.history_path, records)
            self._append_jsonl(
                self.audit_path,
                {
                    "event": "human_review_recorded",
                    "workflow_id": clean_id,
                    "timestamp": decision_time,
                    "decision": review.decision.value,
                    "reviewed_by": review.reviewed_by,
                    "status": record["status"],
                },
            )
            return deepcopy(record)

    def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        """Return one workflow snapshot by ID."""

        clean_id = self._workflow_id(workflow_id)
        with self._lock:
            for record in self._read_history():
                if record["workflow_id"] == clean_id:
                    return deepcopy(record)
        raise WorkflowNotFoundError(f"Workflow '{clean_id}' was not found.")

    def get_latest_workflow(self) -> dict[str, Any] | None:
        """Return the most recently stored workflow, or ``None`` when empty."""

        with self._lock:
            records = self._read_history()
            return deepcopy(records[-1]) if records else None

    def list_workflows(self) -> list[dict[str, Any]]:
        """Return workflow snapshots in insertion order."""

        with self._lock:
            return deepcopy(self._read_history())

    def list_audit_events(self) -> list[dict[str, Any]]:
        """Return compact audit events in insertion order."""

        with self._lock:
            return deepcopy(self._read_jsonl(self.audit_path))

    def _ensure_files(self) -> None:
        with self._lock:
            for path in (self.history_path, self.audit_path):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch(exist_ok=True)

    def _now(self) -> str:
        return _timestamp(self._clock())

    @staticmethod
    def _workflow_id(value: str) -> str:
        if not isinstance(value, str):
            raise TypeError("workflow_id must be a string.")
        clean = value.strip()
        if not clean:
            raise ValueError("workflow_id must not be empty.")
        return clean

    @staticmethod
    def _validate_stage_types(
        workflow_request: WorkflowRequest,
        planner_result: PlannerResult,
        worker_result: WorkerResult,
        reviewer_result: ReviewerResult,
    ) -> None:
        expected = (
            (workflow_request, WorkflowRequest, "workflow_request"),
            (planner_result, PlannerResult, "planner_result"),
            (worker_result, WorkerResult, "worker_result"),
            (reviewer_result, ReviewerResult, "reviewer_result"),
        )
        for value, expected_type, name in expected:
            if not isinstance(value, expected_type):
                raise TypeError(f"{name} must be a {expected_type.__name__}.")

        evidence_ids = tuple(
            item.evidence_id for item in workflow_request.evidence
        )
        issues: list[str] = []
        for name, result, expected_agent in (
            ("planner_result", planner_result, "planner"),
            ("worker_result", worker_result, "worker"),
            ("reviewer_result", reviewer_result, "reviewer"),
        ):
            if result.status != "completed":
                issues.append(f"{name}.status must be completed")
            if result.agent != expected_agent:
                issues.append(f"{name}.agent must be {expected_agent}")
            if result.evidence_ids != evidence_ids:
                issues.append(f"{name}.evidence_ids do not match the request")
            if result.human_approval_required is not True:
                issues.append(f"{name} must require human approval")
        if planner_result.objective != workflow_request.user_request:
            issues.append("planner_result.objective does not match the request")
        if worker_result.evidence_count != len(evidence_ids):
            issues.append("worker_result.evidence_count does not match the request")
        if issues:
            raise WorkflowStateError("; ".join(issues) + ".")

    def _read_history(self) -> list[dict[str, Any]]:
        records = self._read_jsonl(self.history_path)
        seen: set[str] = set()
        for line_number, record in enumerate(records, start=1):
            workflow_id = record.get("workflow_id")
            if not isinstance(workflow_id, str) or not workflow_id.strip():
                raise WorkflowDataError(
                    f"{self.history_path} line {line_number} has no valid "
                    "workflow_id."
                )
            if workflow_id in seen:
                raise WorkflowDataError(
                    f"{self.history_path} contains duplicate workflow_id "
                    f"'{workflow_id}'."
                )
            seen.add(workflow_id)
        return records

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            raise WorkflowDataError(f"Could not read {path}: {exc}") from exc
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise WorkflowDataError(
                    f"{path} line {line_number} is invalid JSON."
                ) from exc
            if not isinstance(value, dict):
                raise WorkflowDataError(
                    f"{path} line {line_number} must contain a JSON object."
                )
            records.append(value)
        return records

    @staticmethod
    def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True)
        try:
            with path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(encoded + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        except (OSError, TypeError, ValueError) as exc:
            raise WorkflowStoreError(f"Could not write {path}: {exc}") from exc

    @staticmethod
    def _rewrite_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                newline="\n",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary_path = Path(stream.name)
                for value in values:
                    stream.write(
                        json.dumps(value, ensure_ascii=False, sort_keys=True)
                        + "\n"
                    )
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, path)
        except (OSError, TypeError, ValueError) as exc:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise WorkflowStoreError(f"Could not rewrite {path}: {exc}") from exc
