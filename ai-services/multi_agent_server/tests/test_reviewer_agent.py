"""Tests for the independent Reviewer Agent."""

from dataclasses import FrozenInstanceError, replace
from unittest.mock import Mock

import pytest

from multi_agent_server.agents.planner_agent import PlannerResult
from multi_agent_server.agents.reviewer_agent import (
    ReviewerAgent,
    ReviewerInputError,
    ReviewerResponseError,
    ReviewerResult,
    build_reviewer_prompt,
    load_reviewer_prompt,
    review_output,
)
from multi_agent_server.agents.worker_agent import WorkerResult
from multi_agent_server.contracts import Feature, WorkflowRequest
from multi_agent_server.evidence_context import UNTRUSTED_EVIDENCE_NOTICE
from multi_agent_server.model_client import (
    AgentRole,
    ModelGeneration,
    ModelTimeoutError,
)


def workflow_request(feature="inventory"):
    return WorkflowRequest.from_dict(
        {
            "user_request": "Determine whether product 12 needs restocking.",
            "feature": feature,
            "evidence": [
                {
                    "evidence_id": f"{feature}-record-12",
                    "source": {
                        "service": f"{feature}-backend",
                        "endpoint": f"/api/{feature}/records/12",
                        "retrieved_at": "2026-10-12T10:00:00Z",
                    },
                    "data": {"stock_quantity": 3, "minimum_stock": 10},
                }
            ],
        }
    )


def planner_result(request):
    evidence_id = request.evidence[0].evidence_id
    return PlannerResult(
        status="completed",
        agent="planner",
        model="qwen2.5:0.5b",
        objective=request.user_request,
        plan=f"Worker analyses {evidence_id}; Reviewer validates; Human decides.",
        evidence_ids=(evidence_id,),
        human_approval_required=True,
        elapsed_ms=100,
    )


def worker_result(request):
    evidence_id = request.evidence[0].evidence_id
    return WorkerResult(
        status="completed",
        agent="worker",
        model="qwen2.5:0.5b",
        output=(
            "Output: Stock 3 is below minimum 10; restocking is needed.\n"
            f"Evidence Used: {evidence_id}.\n"
            "Limitations: None identified."
        ),
        evidence_ids=(evidence_id,),
        evidence_count=1,
        human_approval_required=True,
        elapsed_ms=200,
    )


def completed_generation(evidence_id="inventory-record-12"):
    return ModelGeneration(
        role=AgentRole.REVIEWER,
        model="llama3.1:8b",
        text=(
            f"Risk: LOW; the conclusion matches {evidence_id}.\n"
            "Correction: None.\n"
            "Retest: Not required.\n"
            "Recommendation: Accept for human consideration."
        ),
        elapsed_ms=900,
    )


def test_reviewer_prompt_file_defines_independent_review_checks():
    prompt = load_reviewer_prompt()

    assert "against the Planner result and original evidence" in prompt
    assert "numerical comparison" in prompt
    assert "unsupported claims" in prompt
    assert "Output and Limitations" in prompt
    assert "Recommend Accept only" in prompt
    assert "Correction must describe" in prompt
    assert "never make the final decision" in prompt


def test_prompt_contains_plan_worker_output_evidence_and_template():
    request = workflow_request()

    prompt = build_reviewer_prompt(
        request,
        planner_result(request),
        worker_result(request),
        instructions="Review independently.",
    )

    assert "Review independently." in prompt
    assert "<PLANNER_RESULT>" in prompt
    assert "<WORKER_RESULT>" in prompt
    assert "Stock 3 is below minimum 10" in prompt
    assert UNTRUSTED_EVIDENCE_NOTICE in prompt
    assert '"stock_quantity": 3' in prompt
    assert "A field present in Evidence JSON is not missing" in prompt
    assert "Risk:" in prompt
    assert "Correction:" in prompt
    assert "Retest:" in prompt
    assert "Recommendation:" in prompt


def test_reviewer_uses_review_model_and_returns_normalised_result():
    request = workflow_request()
    client = Mock()
    client.generate.return_value = completed_generation()

    result = ReviewerAgent(client, instructions="Review independently.").review(
        request, planner_result(request), worker_result(request)
    )

    client.generate.assert_called_once()
    assert client.generate.call_args.args[0] is AgentRole.REVIEWER
    assert isinstance(result, ReviewerResult)
    assert result.status == "completed"
    assert result.agent == "reviewer"
    assert result.model == "llama3.1:8b"
    assert result.evidence_ids == ("inventory-record-12",)
    assert result.human_approval_required is True
    assert result.elapsed_ms == 900
    assert result.to_dict()["evidence_ids"] == ["inventory-record-12"]


@pytest.mark.parametrize("feature", [feature.value for feature in Feature])
def test_reviewer_supports_every_release_two_feature(feature):
    request = workflow_request(feature)
    client = Mock()
    client.generate.return_value = completed_generation(f"{feature}-record-12")

    result = ReviewerAgent(client, instructions="Review independently.").review(
        request, planner_result(request), worker_result(request)
    )

    prompt = client.generate.call_args.args[1]
    assert f"Feature: {feature}" in prompt
    assert f"{feature}-record-12" in prompt
    assert result.evidence_ids == (f"{feature}-record-12",)


@pytest.mark.parametrize(
    ("target", "change", "message"),
    [
        ("planner", {"status": "failed"}, "Planner status must be completed"),
        ("planner", {"objective": "wrong"}, "Planner objective does not match"),
        ("planner", {"evidence_ids": ("wrong",)}, "Planner evidence_ids"),
        ("worker", {"status": "failed"}, "Worker status must be completed"),
        ("worker", {"agent": "other"}, "Worker agent must be worker"),
        ("worker", {"evidence_ids": ("wrong",)}, "Worker evidence_ids"),
        ("worker", {"evidence_count": 2}, "Worker evidence_count"),
        ("worker", {"output": "   "}, "Worker output must not be empty"),
    ],
)
def test_reviewer_rejects_mismatched_prior_results(target, change, message):
    request = workflow_request()
    plan = planner_result(request)
    work = worker_result(request)
    if target == "planner":
        plan = replace(plan, **change)
    else:
        work = replace(work, **change)
    client = Mock()

    with pytest.raises(ReviewerInputError, match=message):
        ReviewerAgent(client, instructions="Review independently.").review(
            request, plan, work
        )

    client.generate.assert_not_called()


def test_model_failures_propagate_without_fake_review():
    request = workflow_request()
    failure = ModelTimeoutError(
        "Ollama generation timed out.",
        role=AgentRole.REVIEWER,
        model="llama3.1:8b",
    )
    client = Mock()
    client.generate.side_effect = failure

    with pytest.raises(ModelTimeoutError) as caught:
        ReviewerAgent(client, instructions="Review independently.").review(
            request, planner_result(request), worker_result(request)
        )

    assert caught.value is failure


def test_invalid_first_response_is_corrected_once():
    request = workflow_request()
    invalid = ModelGeneration(
        role=AgentRole.REVIEWER,
        model="llama3.1:8b",
        text="Looks fine.",
        elapsed_ms=100,
    )
    client = Mock()
    client.generate.side_effect = [invalid, completed_generation()]

    result = ReviewerAgent(client, instructions="Review independently.").review(
        request, planner_result(request), worker_result(request)
    )

    assert client.generate.call_count == 2
    assert "previous response was invalid" in client.generate.call_args.args[1]
    assert result.elapsed_ms == 1000


def test_markdown_bold_headings_are_normalised_without_retry():
    request = workflow_request()
    valid = completed_generation()
    markdown = ModelGeneration(
        role=valid.role,
        model=valid.model,
        text=valid.text.replace("Risk:", "**Risk:**")
        .replace("Correction:", "**Correction:**")
        .replace("Retest:", "**Retest:**")
        .replace("Recommendation:", "**Recommendation:**"),
        elapsed_ms=valid.elapsed_ms,
    )
    client = Mock()
    client.generate.return_value = markdown

    result = ReviewerAgent(client, instructions="Review independently.").review(
        request, planner_result(request), worker_result(request)
    )

    client.generate.assert_called_once()
    assert result.review.startswith("Risk:")
    assert "**" not in result.review


def test_harmless_preamble_and_code_fence_are_normalised_without_retry():
    request = workflow_request()
    valid = completed_generation()
    wrapped = ModelGeneration(
        role=valid.role,
        model=valid.model,
        text="Here is the review:\n\n```text\n" + valid.text + "\n```",
        elapsed_ms=valid.elapsed_ms,
    )
    client = Mock()
    client.generate.return_value = wrapped

    result = ReviewerAgent(client, instructions="Review independently.").review(
        request, planner_result(request), worker_result(request)
    )

    client.generate.assert_called_once()
    assert result.review == valid.text
    assert result.review.startswith("Risk:")
    assert "Here is the review" not in result.review
    assert "```" not in result.review


def test_non_accept_review_requires_correction_and_retest():
    request = workflow_request()
    inconsistent = ModelGeneration(
        role=AgentRole.REVIEWER,
        model="llama3.1:8b",
        text=(
            "Risk: MEDIUM; the Worker conclusion is incomplete.\n"
            "Correction: None.\n"
            "Retest: Not required.\n"
            "Recommendation: Partially Accept inventory-record-12."
        ),
        elapsed_ms=100,
    )
    client = Mock()
    client.generate.side_effect = [inconsistent, completed_generation()]

    result = ReviewerAgent(client, instructions="Review independently.").review(
        request, planner_result(request), worker_result(request)
    )

    assert client.generate.call_count == 2
    correction_prompt = client.generate.call_args.args[1]
    assert "Correction cannot be None" in correction_prompt
    assert "Retest cannot be Not required" in correction_prompt
    assert result.review.startswith("Risk: LOW")


def test_negative_problem_language_does_not_invalidate_accept_review():
    request = workflow_request()
    valid = ModelGeneration(
        role=AgentRole.REVIEWER,
        model="llama3.1:8b",
        text=(
            "Risk: LOW; no unsupported claims, contradictions, or omissions "
            "were found.\n"
            "Correction: None.\n"
            "Retest: Not required.\n"
            "Recommendation: Accept inventory-record-12."
        ),
        elapsed_ms=100,
    )
    client = Mock()
    client.generate.return_value = valid

    result = ReviewerAgent(client, instructions="Review independently.").review(
        request, planner_result(request), worker_result(request)
    )

    client.generate.assert_called_once()
    assert result.review.startswith("Risk: LOW")


def test_explanatory_reject_word_does_not_override_accept_recommendation():
    request = workflow_request()
    valid = ModelGeneration(
        role=AgentRole.REVIEWER,
        model="llama3.1:8b",
        text=(
            "Risk: LOW; the evidence supports the answer.\n"
            "Correction: None.\n"
            "Retest: Not required.\n"
            "Recommendation: Accept inventory-record-12. The human reviewer "
            "does not need to reject this supported result."
        ),
        elapsed_ms=100,
    )
    client = Mock()
    client.generate.return_value = valid

    result = ReviewerAgent(client, instructions="Review independently.").review(
        request, planner_result(request), worker_result(request)
    )

    client.generate.assert_called_once()
    assert result.review.startswith("Risk: LOW")


def test_repeated_invalid_response_is_not_reported_as_success():
    request = workflow_request()
    invalid = ModelGeneration(
        role=AgentRole.REVIEWER,
        model="llama3.1:8b",
        text="Unsupported review.",
        elapsed_ms=100,
    )
    client = Mock()
    client.generate.return_value = invalid

    with pytest.raises(ReviewerResponseError) as caught:
        ReviewerAgent(client, instructions="Review independently.").review(
            request, planner_result(request), worker_result(request)
        )

    assert client.generate.call_count == 2
    assert caught.value.code == "reviewer_response_error"
    assert "Risk: must appear exactly once" in caught.value.issues


def test_copied_prompt_context_is_corrected_once():
    request = workflow_request()
    valid = completed_generation()
    leaked = ModelGeneration(
        role=valid.role,
        model=valid.model,
        text=(
            "Risk: LOW.\n"
            "<PLANNER_RESULT>copied</PLANNER_RESULT>\n"
            "<WORKER_RESULT>copied</WORKER_RESULT>\n"
            "Correction: None.\n"
            "Retest: None.\n"
            "Recommendation: Accept inventory-record-12."
        ),
        elapsed_ms=100,
    )
    client = Mock()
    client.generate.side_effect = [leaked, valid]

    result = ReviewerAgent(client, instructions="Review independently.").review(
        request, planner_result(request), worker_result(request)
    )

    assert client.generate.call_count == 2
    assert "copied prompt context" in client.generate.call_args.args[1]
    assert "<PLANNER_RESULT>" not in result.review


def test_review_does_not_modify_inputs_and_result_is_immutable():
    request = workflow_request()
    plan = planner_result(request)
    work = worker_result(request)
    before = (request.to_dict(), plan.to_dict(), work.to_dict())
    client = Mock()
    client.generate.return_value = completed_generation()

    result = ReviewerAgent(client, instructions="Review independently.").review(
        request, plan, work
    )

    assert (request.to_dict(), plan.to_dict(), work.to_dict()) == before
    with pytest.raises(FrozenInstanceError):
        result.status = "failed"


def test_review_output_convenience_function_uses_default_prompt():
    request = workflow_request()
    client = Mock()
    client.generate.return_value = completed_generation()

    result = review_output(
        request, planner_result(request), worker_result(request), client
    )

    assert result.status == "completed"
    assert load_reviewer_prompt() in client.generate.call_args.args[1]


def test_prompt_builder_rejects_raw_prior_results():
    request = workflow_request()
    with pytest.raises(TypeError, match="planner_result must be a PlannerResult"):
        build_reviewer_prompt(
            request,
            {"status": "completed"},
            worker_result(request),
            instructions="Review independently.",
        )
    with pytest.raises(TypeError, match="worker_result must be a WorkerResult"):
        build_reviewer_prompt(
            request,
            planner_result(request),
            {"status": "completed"},
            instructions="Review independently.",
        )


def test_empty_instruction_override_is_rejected():
    request = workflow_request()
    with pytest.raises(ValueError, match="instructions must not be empty"):
        build_reviewer_prompt(
            request,
            planner_result(request),
            worker_result(request),
            instructions="   ",
        )
