"""Independent Reviewer Agent for completed Planner and Worker results."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from multi_agent_server.agents.planner_agent import PlannerResult
from multi_agent_server.agents.worker_agent import WorkerResult
from multi_agent_server.contracts import WorkflowRequest
from multi_agent_server.evidence_context import (
    EVIDENCE_END_MARKER,
    EVIDENCE_START_MARKER,
    build_evidence_context,
)
from multi_agent_server.model_client import AgentRole, OllamaModelClient


BASE_DIR = Path(__file__).resolve().parents[1]
PROMPT_PATH = BASE_DIR / "prompts" / "reviewer_prompt.txt"
MAX_REVIEWER_ATTEMPTS = 2
PLANNER_START_MARKER = "<PLANNER_RESULT>"
PLANNER_END_MARKER = "</PLANNER_RESULT>"
WORKER_START_MARKER = "<WORKER_RESULT>"
WORKER_END_MARKER = "</WORKER_RESULT>"


class ReviewerInputError(ValueError):
    """Raised when prior-stage results do not belong to the same workflow."""

    code = "reviewer_input_error"


class ReviewerResponseError(RuntimeError):
    """Raised when the Reviewer repeatedly ignores its response contract."""

    code = "reviewer_response_error"

    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__(
            "Reviewer returned an invalid response after correction: "
            + ", ".join(issues)
            + "."
        )


@dataclass(frozen=True, slots=True)
class ReviewerResult:
    """Normalised review presented to the human decision maker."""

    status: str
    agent: str
    model: str
    review: str
    evidence_ids: tuple[str, ...]
    human_approval_required: bool
    elapsed_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "agent": self.agent,
            "model": self.model,
            "review": self.review,
            "evidence_ids": list(self.evidence_ids),
            "human_approval_required": self.human_approval_required,
            "elapsed_ms": self.elapsed_ms,
        }


def load_reviewer_prompt(prompt_path: Path = PROMPT_PATH) -> str:
    """Load the reviewed Reviewer instructions from disk."""

    prompt = prompt_path.read_text(encoding="utf-8").strip()
    if not prompt:
        raise ValueError("Reviewer prompt must not be empty.")
    return prompt


def _validate_prior_results(
    workflow_request: WorkflowRequest,
    planner_result: PlannerResult,
    worker_result: WorkerResult,
) -> None:
    expected_ids = tuple(item.evidence_id for item in workflow_request.evidence)
    problems: list[str] = []
    if planner_result.status != "completed":
        problems.append("Planner status must be completed")
    if planner_result.agent != "planner":
        problems.append("Planner agent must be planner")
    if planner_result.objective != workflow_request.user_request:
        problems.append("Planner objective does not match user_request")
    if planner_result.evidence_ids != expected_ids:
        problems.append("Planner evidence_ids do not match the request")
    if planner_result.human_approval_required is not True:
        problems.append("Planner must require human approval")
    if not isinstance(planner_result.plan, str) or not planner_result.plan.strip():
        problems.append("Planner plan must not be empty")

    if worker_result.status != "completed":
        problems.append("Worker status must be completed")
    if worker_result.agent != "worker":
        problems.append("Worker agent must be worker")
    if worker_result.evidence_ids != expected_ids:
        problems.append("Worker evidence_ids do not match the request")
    if worker_result.evidence_count != len(expected_ids):
        problems.append("Worker evidence_count does not match the request")
    if worker_result.human_approval_required is not True:
        problems.append("Worker must require human approval")
    if not isinstance(worker_result.output, str) or not worker_result.output.strip():
        problems.append("Worker output must not be empty")

    if problems:
        raise ReviewerInputError(
            "Invalid prior-stage result: " + "; ".join(problems) + "."
        )


def _safe_json(payload: dict[str, Any]) -> str:
    """Serialise prior output while preventing it from closing prompt markers."""

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    replacements = {
        PLANNER_START_MARKER: r"\u003cPLANNER_RESULT\u003e",
        PLANNER_END_MARKER: r"\u003c/PLANNER_RESULT\u003e",
        WORKER_START_MARKER: r"\u003cWORKER_RESULT\u003e",
        WORKER_END_MARKER: r"\u003c/WORKER_RESULT\u003e",
        EVIDENCE_START_MARKER: r"\u003cEVIDENCE_JSON\u003e",
        EVIDENCE_END_MARKER: r"\u003c/EVIDENCE_JSON\u003e",
    }
    for marker, escaped in replacements.items():
        encoded = encoded.replace(marker, escaped)
    return encoded


def build_reviewer_prompt(
    workflow_request: WorkflowRequest,
    planner_result: PlannerResult,
    worker_result: WorkerResult,
    *,
    instructions: str | None = None,
) -> str:
    """Build a review prompt containing all three evidence-bearing stages."""

    if not isinstance(workflow_request, WorkflowRequest):
        raise TypeError("workflow_request must be a WorkflowRequest.")
    if not isinstance(planner_result, PlannerResult):
        raise TypeError("planner_result must be a PlannerResult.")
    if not isinstance(worker_result, WorkerResult):
        raise TypeError("worker_result must be a WorkerResult.")
    _validate_prior_results(workflow_request, planner_result, worker_result)

    reviewer_instructions = (
        load_reviewer_prompt() if instructions is None else instructions.strip()
    )
    if not reviewer_instructions:
        raise ValueError("Reviewer instructions must not be empty.")

    evidence_context = build_evidence_context(workflow_request)
    evidence_ids = [item.evidence_id for item in workflow_request.evidence]
    evidence_references = ", ".join(
        json.dumps(item.evidence_id, ensure_ascii=False)
        for item in workflow_request.evidence
    )

    return "\n".join(
        (
            reviewer_instructions,
            "",
            "User Request:",
            workflow_request.user_request,
            "",
            PLANNER_START_MARKER,
            _safe_json(planner_result.to_dict()),
            PLANNER_END_MARKER,
            "",
            WORKER_START_MARKER,
            _safe_json(worker_result.to_dict()),
            WORKER_END_MARKER,
            "",
            evidence_context,
            "",
            "Mandatory Evidence IDs (cite every ID in the review):",
            json.dumps(evidence_ids, ensure_ascii=False),
            "",
            "Before writing the review, compare every claim in both Worker "
            "Output and Worker Limitations with the Evidence JSON. A field "
            "present in Evidence JSON is not missing.",
            "",
            "Return only this exact template and fill each section:",
            "Risk: <LOW, MEDIUM, or HIGH, followed by the evidence-based reason>",
            "Correction: <required correction, or None>",
            "Retest: <specific retest, or Not required>",
            "Recommendation: <Accept, Partially Accept, or Reject for human "
            f"consideration; cite {evidence_references}>",
        )
    )


def _response_issues(
    response_text: str,
    workflow_request: WorkflowRequest,
) -> tuple[str, ...]:
    issues: list[str] = []
    if not response_text.lstrip().startswith("Risk:"):
        issues.append("content before Risk:")
    for section in ("Risk:", "Correction:", "Retest:", "Recommendation:"):
        if response_text.count(section) != 1:
            issues.append(f"{section} must appear exactly once")
    forbidden_prompt_fragments = (
        PLANNER_START_MARKER,
        PLANNER_END_MARKER,
        WORKER_START_MARKER,
        WORKER_END_MARKER,
        EVIDENCE_START_MARKER,
        EVIDENCE_END_MARKER,
        "Mandatory Evidence IDs",
    )
    if any(fragment in response_text for fragment in forbidden_prompt_fragments):
        issues.append("copied prompt context into the response")
    for evidence_item in workflow_request.evidence:
        if evidence_item.evidence_id not in response_text:
            issues.append(f"missing evidence {evidence_item.evidence_id}")
    if not any(
        recommendation in response_text
        for recommendation in ("Accept", "Partially Accept", "Reject")
    ):
        issues.append("missing a human decision recommendation")

    risk_match = re.search(r"(?im)^Risk:\s*(LOW|MEDIUM|HIGH)\b", response_text)
    correction_match = re.search(
        r"(?ims)^Correction:\s*(.*?)\s*^Retest:", response_text
    )
    retest_match = re.search(
        r"(?ims)^Retest:\s*(.*?)\s*^Recommendation:", response_text
    )
    recommendation_match = re.search(
        r"(?ims)^Recommendation:\s*(.*)$", response_text
    )
    recommendation = (
        recommendation_match.group(1).strip()
        if recommendation_match is not None
        else ""
    )
    needs_action = bool(
        (risk_match and risk_match.group(1).upper() in {"MEDIUM", "HIGH"})
        or recommendation.startswith("Partially Accept")
        or recommendation.startswith("Reject")
    )
    if needs_action:
        if correction_match and correction_match.group(1).strip().lower().startswith(
            "none"
        ):
            issues.append("Correction cannot be None for a non-accept review")
        if retest_match and retest_match.group(1).strip().lower().startswith(
            "not required"
        ):
            issues.append("Retest cannot be Not required for a non-accept review")
    return tuple(issues)


def _normalise_review_headings(response_text: str) -> str:
    """Remove harmless wrappers while preserving the strict review template."""

    normalised = response_text
    for heading in ("Risk", "Correction", "Retest", "Recommendation"):
        normalised = normalised.replace(f"**{heading}:**", f"{heading}:")
    risk_heading = re.search(r"(?im)^\s*Risk:", normalised)
    if risk_heading is not None:
        normalised = normalised[risk_heading.start() :].lstrip()
    if normalised.rstrip().endswith("```"):
        normalised = normalised.rstrip()[:-3].rstrip()
    return normalised


class ReviewerAgent:
    """Review completed work against its plan and original evidence."""

    def __init__(
        self,
        model_client: OllamaModelClient,
        *,
        instructions: str | None = None,
    ) -> None:
        self._model_client = model_client
        self._instructions = instructions

    def review(
        self,
        workflow_request: WorkflowRequest,
        planner_result: PlannerResult,
        worker_result: WorkerResult,
    ) -> ReviewerResult:
        """Generate an independent review; model-client failures propagate."""

        base_prompt = build_reviewer_prompt(
            workflow_request,
            planner_result,
            worker_result,
            instructions=self._instructions,
        )
        prompt = base_prompt
        elapsed_ms = 0
        issues: tuple[str, ...] = ()
        for attempt in range(MAX_REVIEWER_ATTEMPTS):
            generation = self._model_client.generate(AgentRole.REVIEWER, prompt)
            elapsed_ms += generation.elapsed_ms
            review_text = _normalise_review_headings(generation.text)
            issues = _response_issues(review_text, workflow_request)
            if not issues:
                break
            if attempt + 1 < MAX_REVIEWER_ATTEMPTS:
                prompt = "\n".join(
                    (
                        base_prompt,
                        "",
                        "Your previous response was invalid because it was "
                        "missing or repeating required content:",
                        "; ".join(issues),
                        "Return the exact template above now. Do not repeat "
                        "the plan, Worker result, or evidence JSON. If risk "
                        "or recommendation requires action, provide a real "
                        "Correction and Retest.",
                    )
                )
        else:
            raise ReviewerResponseError(issues)

        evidence_ids = tuple(
            item.evidence_id for item in workflow_request.evidence
        )
        return ReviewerResult(
            status="completed",
            agent="reviewer",
            model=generation.model,
            review=review_text,
            evidence_ids=evidence_ids,
            human_approval_required=True,
            elapsed_ms=elapsed_ms,
        )


def review_output(
    workflow_request: WorkflowRequest,
    planner_result: PlannerResult,
    worker_result: WorkerResult,
    model_client: OllamaModelClient,
) -> ReviewerResult:
    """Coordinator-friendly function matching the teaching example's name."""

    return ReviewerAgent(model_client).review(
        workflow_request,
        planner_result,
        worker_result,
    )
