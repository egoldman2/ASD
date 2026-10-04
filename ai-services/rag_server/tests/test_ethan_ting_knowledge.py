"""Curated accounts/loyalty scope is registered and isolated."""

from dataclasses import replace
import re

import pytest

from rag_server.config import BASE_DIR
from rag_server.ollama_client import OllamaAnswer
from rag_server.rag_pipeline import INSUFFICIENT_ANSWER, RAGPipeline, _default_sources, _system_prompt


SCOPE = "ethan_ting_accounts_loyalty"


def test_guide_source_contains_implemented_rules_without_customer_records(rag_settings):
    source = _default_sources(rag_settings)[SCOPE]
    documents = source.load_documents()
    text = "\n".join(document.text for document in documents)

    assert documents
    assert all(document.scope == SCOPE for document in documents)
    assert all(document.source_id.startswith(f"{SCOPE}/") for document in documents)
    assert "Bronze covers 0 to 499 points" in text
    assert "do not assume that a selected customer has zero points" in text
    assert "required total balance, not the points remaining" in text
    assert "1,000,000 points" in text
    assert "does not automatically award points" in text
    assert "customer@asd.local" not in text
    assert (BASE_DIR / "knowledge" / "ethan_ting" / "accounts_and_loyalty.md").is_file()


def test_feature_prompt_requires_sources_and_abstention():
    prompt = _system_prompt(SCOPE)
    assert "Cite each factual paragraph" in prompt
    assert "Insufficient context to answer this question." in prompt
    assert "live customer's identity" in prompt
    assert "one plain-text paragraph" in prompt
    assert "Never describe administrator-only tools" in prompt


@pytest.fixture
def guide_pipeline(rag_settings):
    # Exercise the actual curated corpus, Chroma index and deployed retrieval settings.
    settings = replace(rag_settings, embedding_dimensions=256, min_relevance_score=0.25)
    guide = _default_sources(settings)[SCOPE]
    with RAGPipeline(settings=settings, sources={SCOPE: guide}) as pipeline:
        assert pipeline.refresh_corpus(SCOPE)["success"]
        yield pipeline


@pytest.mark.parametrize("question,fact", [
    ("How can a customer change their password, and what are the requirements?", "current password must be correct"),
    ("Can a customer reuse the current password as the new password?", "different from the current password"),
    ("How can a customer update their profile name and email?", "selects Save changes"),
    ("Can two customer accounts register with the same email?", "Email addresses must be unique"),
    ("How do customers get loyalty points, and are purchases rewarded automatically?", "does not automatically award points"),
    ("Where can a customer check their loyalty point history?", "recent point history"),
    ("Can administrators remove points, and what are the limits?", "cannot make the balance negative"),
    ("How many points are needed for Gold?", "Gold begins at 1,000 points"),
    ("Can a customer request a forgotten-password recovery email?", "cannot send a password reset email"),
    ("Can disabled accounts sign in?", "Disabled accounts cannot sign in"),
    ("Can customers use the administrator Customer assistant Point history tool?", "not available to customer-role accounts"),
])
def test_guide_questions_retrieve_real_relevant_passages(guide_pipeline, question, fact):
    found = guide_pipeline.retrieve_context(SCOPE, question, 5)
    assert found["success"] and not found["insufficient_context"]
    assert any(fact in row["text"] for row in found["data"]["results"])
    assert all(citation["source_id"] == f"{SCOPE}/accounts_and_loyalty.md"
               for citation in found["citations"])
    assert found["confidence"] in {"low", "medium", "high"}


def test_password_answer_has_real_citation_and_passes_only_approved_context(guide_pipeline):
    class Model:
        def generate_answer(self, system_prompt, user_prompt, **kwargs):
            assert "current password must be correct" in user_prompt
            assert "different from the current password" in user_prompt
            assert "Never enter a password into the assistant" in user_prompt
            # Select the citation number from the actual retrieved password passage.
            passages = re.findall(r'<source number="(\d+)"[^>]*>(.*?)</source>', user_prompt, re.S)
            rank = next(rank for rank, passage in passages if "current password must be correct" in passage)
            return OllamaAnswer(
                f"The current password must be correct. The new password needs at least 8 characters, "
                f"must match its confirmation and differ from the current password. [{rank}]",
                "test-guide-model",
            )
    guide_pipeline._ollama_client = Model()
    result = guide_pipeline.answer_question(SCOPE, "How can a customer change their password, and what are the requirements?", 5)
    assert result["success"] and not result["insufficient_context"]
    assert result["data"]["model"] == "test-guide-model"
    assert all(citation["source_id"] == f"{SCOPE}/accounts_and_loyalty.md" for citation in result["citations"])
    assert result["metadata"]["confidence_basis"] == "retrieval_similarity_not_probability_of_correctness"


def test_expanded_guide_still_abstains_for_unrelated_questions(guide_pipeline):
    class NoModel:
        def generate_answer(self, *args, **kwargs):
            pytest.fail("Unrelated questions must not invoke the model")
    guide_pipeline._ollama_client = NoModel()
    result = guide_pipeline.answer_question(SCOPE, "quasar orbital spectroscopy wavelengths", 5)
    assert result["success"] and result["insufficient_context"]
    assert result["data"]["answer"] == INSUFFICIENT_ANSWER
    assert result["citations"] == []
    assert not result["metadata"]["model_invoked"]
