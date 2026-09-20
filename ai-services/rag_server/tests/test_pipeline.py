"""Tests for the shared RAG pipeline's main indexing and answer flow."""

import math

import chromadb
import pytest

from rag_server.ollama_client import OllamaAnswer, OllamaUnavailableError
from rag_server.rag_pipeline import (
    INSUFFICIENT_ANSWER,
    RAGPipeline,
    embed_text,
)
from rag_server.sources.base import (
    KnowledgeDocument,
    KnowledgeSource,
    SourceUnavailableError,
)


class MutableSource(KnowledgeSource):
    def __init__(self, scope="chufeng_catalogue", documents=None, failure=None):
        self._scope = scope
        self.documents = list(documents or [])
        self.failure = failure

    @property
    def scope(self):
        return self._scope

    @property
    def source_name(self):
        return "Test Catalogue"

    def load_documents(self):
        if self.failure:
            raise self.failure
        return list(self.documents)


class FakeOllama:
    def __init__(self, content="The keyboard costs AUD 109.00 [1].", failure=None):
        self.content = content
        self.failure = failure
        self.calls = []

    def generate_answer(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        if self.failure:
            raise self.failure
        return OllamaAnswer(self.content, "test-model")


def document(
    product_id=1,
    *,
    name="Mechanical Keyboard",
    description="Compact mechanical keyboard with adjustable backlighting.",
    price="109.00",
    stock=20,
    scope="chufeng_catalogue",
):
    availability = "in stock" if stock else "out of stock"
    return KnowledgeDocument(
        document_id=f"{scope}:product:{product_id}",
        scope=scope,
        source_id=f"product:{product_id}",
        citation_label=name,
        text=(
            f"Product: {name}\nCategory: Electronics\n"
            f"Description: {description}\nPrice: AUD {price}\n"
            f"Availability: {availability}\nStock quantity: {stock}"
        ),
        metadata={"product_id": product_id, "availability": availability},
    )


@pytest.fixture
def chroma_client():
    yield chromadb.EphemeralClient()


def pipeline_for(settings, client, source, ollama=None):
    return RAGPipeline(
        settings=settings,
        sources={source.scope: source},
        chroma_client=client,
        ollama_client=ollama,
    )


def test_embedding_is_deterministic_and_normalised():
    first = embed_text("Mechanical keyboard", 64)
    second = embed_text("mechanical KEYBOARD", 64)

    assert first == second
    assert len(first) == 64
    assert math.sqrt(sum(value * value for value in first)) == pytest.approx(1.0)


def test_refresh_retrieve_and_remove_stale_documents(rag_settings, chroma_client):
    source = MutableSource(
        documents=[document(1), document(2, name="USB-C Hub", price="79.00")]
    )
    pipeline = pipeline_for(rag_settings, chroma_client, source)

    first_refresh = pipeline.refresh_corpus(source.scope)
    retrieval = pipeline.retrieve_context(source.scope, "Mechanical Keyboard", 1)
    assert first_refresh["data"]["added_count"] == 2
    assert retrieval["citations"][0]["label"] == "Mechanical Keyboard"

    source.documents = [document(1, price="99.00")]
    second_refresh = pipeline.refresh_corpus(source.scope)
    assert second_refresh["data"]["updated_count"] == 1
    assert second_refresh["data"]["removed_count"] == 1


def test_empty_index_reports_insufficient_context(rag_settings, chroma_client):
    source = MutableSource()
    pipeline = pipeline_for(rag_settings, chroma_client, source)

    response = pipeline.retrieve_context(source.scope, "keyboard")

    assert response["success"] is True
    assert response["insufficient_context"] is True
    assert response["confidence"] == "insufficient"


def test_invalid_top_k_returns_structured_error(rag_settings, chroma_client):
    source = MutableSource()
    pipeline = pipeline_for(rag_settings, chroma_client, source)

    response = pipeline.retrieve_context(source.scope, "keyboard", 21)

    assert response["success"] is False
    assert response["error"]["code"] == "INVALID_ARGUMENT"


def test_source_failure_returns_structured_error(rag_settings, chroma_client):
    source = MutableSource(failure=SourceUnavailableError("catalogue offline"))
    pipeline = pipeline_for(rag_settings, chroma_client, source)

    response = pipeline.refresh_corpus(source.scope)

    assert response["error"]["code"] == "SOURCE_UNAVAILABLE"


def test_disabled_pipeline_rejects_requests(settings_factory, chroma_client):
    settings = settings_factory(enabled=False)
    source = MutableSource(documents=[document()])
    pipeline = pipeline_for(settings, chroma_client, source)

    response = pipeline.retrieve_context(source.scope, "keyboard")

    assert response["error"]["code"] == "RAG_DISABLED"


def test_answer_is_grounded_and_cited(rag_settings, chroma_client):
    source = MutableSource(documents=[document()])
    ollama = FakeOllama("The Mechanical Keyboard costs AUD 109.00 [1].")
    pipeline = pipeline_for(rag_settings, chroma_client, source, ollama)
    pipeline.refresh_corpus(source.scope)

    response = pipeline.answer_question(
        source.scope,
        "What is the price of the Mechanical Keyboard?",
        1,
    )

    assert response["success"] is True
    assert response["data"]["answer"].endswith("[1].")
    assert response["citations"][0]["label"] == "Mechanical Keyboard"
    assert response["metadata"]["grounded"] is True
    assert len(ollama.calls) == 1


def test_missing_feature_refuses_to_invoke_model(rag_settings, chroma_client):
    source = MutableSource(documents=[document()])
    ollama = FakeOllama()
    pipeline = pipeline_for(rag_settings, chroma_client, source, ollama)
    pipeline.refresh_corpus(source.scope)

    response = pipeline.answer_question(
        source.scope,
        "Does the Mechanical Keyboard support Bluetooth?",
        1,
    )

    assert response["data"]["answer"] == INSUFFICIENT_ANSWER
    assert response["insufficient_context"] is True
    assert response["metadata"]["model_invoked"] is False
    assert ollama.calls == []


def test_ollama_failure_returns_structured_error(rag_settings, chroma_client):
    source = MutableSource(documents=[document()])
    ollama = FakeOllama(failure=OllamaUnavailableError("offline"))
    pipeline = pipeline_for(rag_settings, chroma_client, source, ollama)
    pipeline.refresh_corpus(source.scope)

    response = pipeline.answer_question(source.scope, "Tell me about keyboard", 1)

    assert response["error"]["code"] == "OLLAMA_UNAVAILABLE"


def test_retrieval_does_not_cross_team_scopes(rag_settings, chroma_client):
    catalogue = MutableSource(documents=[document()])
    policy = MutableSource(
        "team_policy",
        [
            KnowledgeDocument(
                document_id="team_policy:item:1",
                scope="team_policy",
                source_id="policy:1",
                citation_label="Returns Policy",
                text="Returns are accepted within thirty days.",
                metadata={"public": True},
            )
        ],
    )
    pipeline = RAGPipeline(
        settings=rag_settings,
        sources={catalogue.scope: catalogue, policy.scope: policy},
        chroma_client=chroma_client,
    )
    pipeline.refresh_corpus(catalogue.scope)
    pipeline.refresh_corpus(policy.scope)

    response = pipeline.retrieve_context(policy.scope, "Mechanical Keyboard", 5)

    assert response["data"]["result_count"] == 1
    assert response["citations"][0]["scope"] == "team_policy"
    assert response["citations"][0]["label"] == "Returns Policy"
