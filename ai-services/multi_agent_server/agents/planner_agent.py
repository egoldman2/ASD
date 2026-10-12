"""Planner Agent for feature-neutral workflow planning."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from multi_agent_server.contracts import WorkflowRequest
from multi_agent_server.model_client import (
    AgentRole,
    OllamaModelClient,
)


BASE_DIR = Path(__file__).resolve().parents[1]
PROMPT_PATH = BASE_DIR / "prompts" / "planner_prompt.txt"
MAX_PLANNER_ATTEMPTS = 2


class PlannerResponseError(RuntimeError):
    """Raised when the Planner repeatedly ignores its response contract."""

    code = "planner_response_error"

    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__(
            "Planner returned an invalid response after correction: "
            + ", ".join(issues)
            + "."
        )


@dataclass(frozen=True, slots=True)
class PlannerResult:
    """Normalised Planner output consumed by the workflow coordinator."""

    status: str
    agent: str
    model: str
    objective: str
    plan: str
    evidence_ids: tuple[str, ...]
    human_approval_required: bool
    elapsed_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "agent": self.agent,
            "model": self.model,
            "objective": self.objective,
            "plan": self.plan,
            "evidence_ids": list(self.evidence_ids),
            "human_approval_required": self.human_approval_required,
            "elapsed_ms": self.elapsed_ms,
        }


def load_planner_prompt(prompt_path: Path = PROMPT_PATH) -> str:
    """Load the reviewed Planner instructions from disk."""

    prompt = prompt_path.read_text(encoding="utf-8").strip()
    if not prompt:
        raise ValueError("Planner prompt must not be empty.")
    return prompt


def build_planner_prompt(
    workflow_request: WorkflowRequest,
    *,
    instructions: str | None = None,
) -> str:
    """Build a prompt containing request details and evidence metadata only."""

    if not isinstance(workflow_request, WorkflowRequest):
        raise TypeError("workflow_request must be a WorkflowRequest.")

    planner_instructions = (
        load_planner_prompt() if instructions is None else instructions.strip()
    )
    if not planner_instructions:
        raise ValueError("Planner instructions must not be empty.")

    evidence_metadata = [
        {
            "evidence_id": item.evidence_id,
            "source": item.source.to_dict(),
        }
        for item in workflow_request.evidence
    ]
    evidence_ids = [item.evidence_id for item in workflow_request.evidence]
    metadata_json = json.dumps(
        evidence_metadata,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    evidence_references = ", ".join(
        f"{json.dumps(item.evidence_id, ensure_ascii=False)} from "
        f"{json.dumps(item.source.service, ensure_ascii=False)}"
        for item in workflow_request.evidence
    )

    return "\n".join(
        (
            planner_instructions,
            "",
            "User Request:",
            workflow_request.user_request,
            "",
            "Feature:",
            workflow_request.feature.value,
            "",
            "Available Evidence Metadata:",
            metadata_json,
            "",
            "Mandatory Evidence IDs (list every ID in Evidence Required):",
            json.dumps(evidence_ids, ensure_ascii=False),
            "",
            "Return only this exact template and fill each line:",
            "Objective: <planning objective>",
            "Steps:",
            f"1. Worker Agent: analyse {evidence_references} only.",
            "2. Reviewer Agent: validate the Worker output against the same "
            "evidence.",
            "3. Human Reviewer: accept, partially accept, or reject.",
            f"Evidence Required: {evidence_references}.",
            "Human Approval: Required.",
        )
    )


def _response_issues(
    response_text: str,
    workflow_request: WorkflowRequest,
) -> tuple[str, ...]:
    issues: list[str] = []
    required_sections = (
        "Objective:",
        "Steps:",
        "Evidence Required:",
        "Human Approval:",
    )
    for section in required_sections:
        if section not in response_text:
            issues.append(f"missing {section}")

    for role in ("Worker Agent", "Reviewer Agent", "Human Reviewer"):
        if role not in response_text:
            issues.append(f"missing {role}")

    for step_number in (1, 2, 3):
        if not re.search(rf"(?m)^\s*{step_number}\.\s+", response_text):
            issues.append(f"missing step {step_number}")

    for evidence_item in workflow_request.evidence:
        if evidence_item.evidence_id not in response_text:
            issues.append(f"missing evidence {evidence_item.evidence_id}")

    if not re.search(
        r"(?im)^\s*Human Approval:\s*Required\.?\s*$",
        response_text,
    ):
        issues.append("human approval must be Required")

    return tuple(issues)


def _apply_mandatory_human_approval(response_text: str) -> str:
    """Add the server-owned governance policy when the model omits its line."""

    if "Human Approval:" not in response_text:
        return response_text.rstrip() + "\nHuman Approval: Required."
    return response_text


class PlannerAgent:
    """Create a plan without retrieving data or answering the user request."""

    def __init__(
        self,
        model_client: OllamaModelClient,
        *,
        instructions: str | None = None,
    ) -> None:
        self._model_client = model_client
        self._instructions = instructions

    def plan(self, workflow_request: WorkflowRequest) -> PlannerResult:
        """Generate a plan; model-client failures intentionally propagate."""

        base_prompt = build_planner_prompt(
            workflow_request,
            instructions=self._instructions,
        )
        prompt = base_prompt
        elapsed_ms = 0
        issues: tuple[str, ...] = ()
        for attempt in range(MAX_PLANNER_ATTEMPTS):
            generation = self._model_client.generate(AgentRole.PLANNER, prompt)
            elapsed_ms += generation.elapsed_ms
            plan_text = _apply_mandatory_human_approval(generation.text)
            issues = _response_issues(plan_text, workflow_request)
            if not issues:
                break
            if attempt + 1 < MAX_PLANNER_ATTEMPTS:
                prompt = "\n".join(
                    (
                        base_prompt,
                        "",
                        "Your previous response was invalid because it was "
                        "missing required content:",
                        "; ".join(issues),
                        "Return the exact template above now. Do not add "
                        "anything else.",
                    )
                )
        else:
            raise PlannerResponseError(issues)

        return PlannerResult(
            status="completed",
            agent="planner",
            model=generation.model,
            objective=workflow_request.user_request,
            plan=plan_text,
            evidence_ids=tuple(
                item.evidence_id for item in workflow_request.evidence
            ),
            human_approval_required=True,
            elapsed_ms=elapsed_ms,
        )


def plan_workflow(
    workflow_request: WorkflowRequest,
    model_client: OllamaModelClient,
) -> PlannerResult:
    """Coordinator-friendly function matching the teaching example's shape."""

    return PlannerAgent(model_client).plan(workflow_request)
