"""Worker Agent that executes a Planner result using supplied evidence only."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from multi_agent_server.agents.planner_agent import PlannerResult
from multi_agent_server.contracts import WorkflowRequest
from multi_agent_server.evidence_context import (
    EVIDENCE_END_MARKER,
    EVIDENCE_START_MARKER,
    build_evidence_context,
)
from multi_agent_server.model_client import AgentRole, OllamaModelClient


BASE_DIR = Path(__file__).resolve().parents[1]
PROMPT_PATH = BASE_DIR / "prompts" / "worker_prompt.txt"
MAX_WORKER_ATTEMPTS = 2
PLAN_START_MARKER = "<PLANNER_PLAN>"
PLAN_END_MARKER = "</PLANNER_PLAN>"


class WorkerInputError(ValueError):
    """Raised when the Planner result does not belong to the request."""

    code = "worker_input_error"


class WorkerResponseError(RuntimeError):
    """Raised when the Worker repeatedly ignores its response contract."""

    code = "worker_response_error"

    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__(
            "Worker returned an invalid response after correction: "
            + ", ".join(issues)
            + "."
        )


@dataclass(frozen=True, slots=True)
class WorkerResult:
    """Normalised Worker output consumed by the Reviewer and Coordinator."""

    status: str
    agent: str
    model: str
    output: str
    evidence_ids: tuple[str, ...]
    evidence_count: int
    human_approval_required: bool
    elapsed_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "agent": self.agent,
            "model": self.model,
            "output": self.output,
            "evidence_ids": list(self.evidence_ids),
            "evidence_count": self.evidence_count,
            "human_approval_required": self.human_approval_required,
            "elapsed_ms": self.elapsed_ms,
        }


def load_worker_prompt(prompt_path: Path = PROMPT_PATH) -> str:
    """Load the reviewed Worker instructions from disk."""

    prompt = prompt_path.read_text(encoding="utf-8").strip()
    if not prompt:
        raise ValueError("Worker prompt must not be empty.")
    return prompt


def _validate_planner_result(
    workflow_request: WorkflowRequest,
    planner_result: PlannerResult,
) -> None:
    expected_ids = tuple(item.evidence_id for item in workflow_request.evidence)
    problems: list[str] = []
    if planner_result.status != "completed":
        problems.append("status must be completed")
    if planner_result.agent != "planner":
        problems.append("agent must be planner")
    if planner_result.objective != workflow_request.user_request:
        problems.append("objective does not match user_request")
    if planner_result.evidence_ids != expected_ids:
        problems.append("evidence_ids do not match the request")
    if planner_result.human_approval_required is not True:
        problems.append("human approval must be required")
    if not isinstance(planner_result.plan, str) or not planner_result.plan.strip():
        problems.append("plan must not be empty")
    if problems:
        raise WorkerInputError("Invalid Planner result: " + "; ".join(problems) + ".")


def _safe_plan_text(plan: str) -> str:
    return plan.replace(
        PLAN_START_MARKER,
        r"\u003cPLANNER_PLAN\u003e",
    ).replace(
        PLAN_END_MARKER,
        r"\u003c/PLANNER_PLAN\u003e",
    )


def build_worker_prompt(
    workflow_request: WorkflowRequest,
    planner_result: PlannerResult,
    *,
    instructions: str | None = None,
) -> str:
    """Build a Worker prompt from one validated request and its Planner result."""

    if not isinstance(workflow_request, WorkflowRequest):
        raise TypeError("workflow_request must be a WorkflowRequest.")
    if not isinstance(planner_result, PlannerResult):
        raise TypeError("planner_result must be a PlannerResult.")
    _validate_planner_result(workflow_request, planner_result)

    worker_instructions = (
        load_worker_prompt() if instructions is None else instructions.strip()
    )
    if not worker_instructions:
        raise ValueError("Worker instructions must not be empty.")

    evidence_context = build_evidence_context(workflow_request)
    evidence_ids = [item.evidence_id for item in workflow_request.evidence]
    evidence_references = ", ".join(
        json.dumps(item.evidence_id, ensure_ascii=False)
        for item in workflow_request.evidence
    )

    return "\n".join(
        (
            worker_instructions,
            "",
            "User Request:",
            workflow_request.user_request,
            "",
            PLAN_START_MARKER,
            _safe_plan_text(planner_result.plan),
            PLAN_END_MARKER,
            "",
            evidence_context,
            "",
            "Mandatory Evidence IDs (cite every ID in Evidence Used):",
            json.dumps(evidence_ids, ensure_ascii=False),
            "",
            "The Evidence JSON above is already supplied. Analyse its data "
            "fields now; do not request it again.",
            "",
            "Return only this exact template and fill each section:",
            "Output: <evidence-based answer to the user request>",
            f"Evidence Used: {evidence_references}.",
            "Limitations: <missing or uncertain information, or None identified>.",
        )
    )


def _response_issues(
    response_text: str,
    workflow_request: WorkflowRequest,
) -> tuple[str, ...]:
    issues: list[str] = []
    if not response_text.lstrip().startswith("Output:"):
        issues.append("content before Output:")
    if response_text.count("Output:") != 1:
        issues.append("Output: must appear exactly once")
    for section in ("Output:", "Evidence Used:", "Limitations:"):
        if section not in response_text:
            issues.append(f"missing {section}")
    forbidden_prompt_fragments = (
        PLAN_START_MARKER,
        PLAN_END_MARKER,
        EVIDENCE_START_MARKER,
        EVIDENCE_END_MARKER,
        "Mandatory Evidence IDs",
    )
    if any(fragment in response_text for fragment in forbidden_prompt_fragments):
        issues.append("copied prompt context into the response")
    for evidence_item in workflow_request.evidence:
        if evidence_item.evidence_id not in response_text:
            issues.append(f"missing evidence {evidence_item.evidence_id}")
    return tuple(issues)


class WorkerAgent:
    """Execute an approved Planner step using backend-supplied evidence."""

    def __init__(
        self,
        model_client: OllamaModelClient,
        *,
        instructions: str | None = None,
    ) -> None:
        self._model_client = model_client
        self._instructions = instructions

    def execute(
        self,
        workflow_request: WorkflowRequest,
        planner_result: PlannerResult,
    ) -> WorkerResult:
        """Generate evidence-based output; model-client failures propagate."""

        base_prompt = build_worker_prompt(
            workflow_request,
            planner_result,
            instructions=self._instructions,
        )
        prompt = base_prompt
        elapsed_ms = 0
        issues: tuple[str, ...] = ()
        for attempt in range(MAX_WORKER_ATTEMPTS):
            generation = self._model_client.generate(AgentRole.WORKER, prompt)
            elapsed_ms += generation.elapsed_ms
            issues = _response_issues(generation.text, workflow_request)
            if not issues:
                break
            if attempt + 1 < MAX_WORKER_ATTEMPTS:
                prompt = "\n".join(
                    (
                        base_prompt,
                        "",
                        "Your previous response was invalid because it was "
                        "missing required content:",
                        "; ".join(issues),
                        "Return the exact template above now. Do not add "
                        "anything else or repeat the plan or evidence JSON.",
                    )
                )
        else:
            raise WorkerResponseError(issues)

        evidence_ids = tuple(
            item.evidence_id for item in workflow_request.evidence
        )
        return WorkerResult(
            status="completed",
            agent="worker",
            model=generation.model,
            output=generation.text,
            evidence_ids=evidence_ids,
            evidence_count=len(evidence_ids),
            human_approval_required=True,
            elapsed_ms=elapsed_ms,
        )


def generate_output(
    workflow_request: WorkflowRequest,
    planner_result: PlannerResult,
    model_client: OllamaModelClient,
) -> WorkerResult:
    """Coordinator-friendly function matching the teaching example's name."""

    return WorkerAgent(model_client).execute(workflow_request, planner_result)
