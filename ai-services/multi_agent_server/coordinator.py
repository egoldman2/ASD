"""Planner, Worker, Reviewer, and human-review workflow coordination."""

from __future__ import annotations

from collections.abc import Callable
from time import monotonic
from typing import Any, Protocol
from uuid import UUID, uuid4

from multi_agent_server.agents.planner_agent import PlannerResult
from multi_agent_server.agents.reviewer_agent import ReviewerResult
from multi_agent_server.agents.worker_agent import WorkerResult
from multi_agent_server.contracts import HumanReviewRequest, WorkflowRequest
from multi_agent_server.workflow_store import WorkflowStore


class Planner(Protocol):
    """Planner interface required by the coordinator."""

    def plan(self, workflow_request: WorkflowRequest) -> PlannerResult:
        """Create a plan for one validated workflow request."""


class Worker(Protocol):
    """Worker interface required by the coordinator."""

    def execute(
        self,
        workflow_request: WorkflowRequest,
        planner_result: PlannerResult,
    ) -> WorkerResult:
        """Execute a completed plan against supplied evidence."""


class Reviewer(Protocol):
    """Reviewer interface required by the coordinator."""

    def review(
        self,
        workflow_request: WorkflowRequest,
        planner_result: PlannerResult,
        worker_result: WorkerResult,
    ) -> ReviewerResult:
        """Review completed work against the original evidence."""


class WorkflowCoordinator:
    """Run one evidence-bound agent chain and expose its stored state."""

    def __init__(
        self,
        planner: Planner,
        worker: Worker,
        reviewer: Reviewer,
        store: WorkflowStore,
        *,
        id_factory: Callable[[], str | UUID] = uuid4,
        timer: Callable[[], float] = monotonic,
    ) -> None:
        for dependency, method_name, name in (
            (planner, "plan", "planner"),
            (worker, "execute", "worker"),
            (reviewer, "review", "reviewer"),
        ):
            if not callable(getattr(dependency, method_name, None)):
                raise TypeError(f"{name} must provide a callable {method_name}().")
        if not isinstance(store, WorkflowStore):
            raise TypeError("store must be a WorkflowStore.")
        if not callable(id_factory):
            raise TypeError("id_factory must be callable.")
        if not callable(timer):
            raise TypeError("timer must be callable.")

        self._planner = planner
        self._worker = worker
        self._reviewer = reviewer
        self._store = store
        self._id_factory = id_factory
        self._timer = timer

    def run(self, workflow_request: WorkflowRequest) -> dict[str, Any]:
        """Run all three agents and persist only a completely reviewed chain."""

        if not isinstance(workflow_request, WorkflowRequest):
            raise TypeError("workflow_request must be a WorkflowRequest.")

        workflow_id = self._new_workflow_id()
        started_at = self._time()
        planner_result = self._planner.plan(workflow_request)
        worker_result = self._worker.execute(workflow_request, planner_result)
        reviewer_result = self._reviewer.review(
            workflow_request,
            planner_result,
            worker_result,
        )
        duration_ms = max(0, round((self._time() - started_at) * 1_000))

        return self._store.record_workflow(
            workflow_id,
            workflow_request,
            planner_result,
            worker_result,
            reviewer_result,
            duration_ms=duration_ms,
        )

    def submit_human_review(
        self,
        workflow_id: str,
        review: HumanReviewRequest,
    ) -> dict[str, Any]:
        """Apply the single human decision allowed for a stored workflow."""

        return self._store.apply_human_review(workflow_id, review)

    def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        """Return one stored workflow by ID."""

        return self._store.get_workflow(workflow_id)

    def get_latest_workflow(self) -> dict[str, Any] | None:
        """Return the latest stored workflow, if one exists."""

        return self._store.get_latest_workflow()

    def list_workflows(self) -> list[dict[str, Any]]:
        """Return all stored workflows in insertion order."""

        return self._store.list_workflows()

    def _new_workflow_id(self) -> str:
        value = self._id_factory()
        if not isinstance(value, (str, UUID)):
            raise TypeError("id_factory must return a string or UUID.")
        workflow_id = str(value).strip()
        if not workflow_id:
            raise ValueError("id_factory must return a non-empty workflow ID.")
        return workflow_id

    def _time(self) -> float:
        value = self._timer()
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("timer must return a number.")
        return float(value)
