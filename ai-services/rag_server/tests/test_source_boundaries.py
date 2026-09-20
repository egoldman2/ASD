"""Essential shared-team knowledge-source boundary tests."""

import pytest

from rag_server.rag_pipeline import RAGPipeline
from rag_server.sources.base import KnowledgeDocument, KnowledgeSource


class StubSource(KnowledgeSource):
    def __init__(self, scope):
        self._scope = scope

    @property
    def scope(self):
        return self._scope

    @property
    def source_name(self):
        return "Stub Team Source"

    def load_documents(self):
        return []


def test_knowledge_document_validates_and_copies_metadata():
    original_metadata = {"public": True}
    document = KnowledgeDocument(
        document_id="team_scope:item:1",
        scope="team_scope",
        source_id="item:1",
        citation_label="Example Item",
        text="A safe public knowledge record.",
        metadata=original_metadata,
    )
    original_metadata["private"] = "secret"

    assert document.metadata == {"public": True}
    with pytest.raises(ValueError, match="text"):
        KnowledgeDocument(
            document_id="item:2",
            scope="team_scope",
            source_id="item:2",
            citation_label="Invalid",
            text="",
            metadata={},
        )


def test_pipeline_registry_enforces_and_sorts_team_scopes(rag_settings):
    with pytest.raises(ValueError, match="does not match"):
        RAGPipeline(
            settings=rag_settings,
            sources={"wrong_scope": StubSource("actual_scope")},
        )

    pipeline = RAGPipeline(
        settings=rag_settings,
        sources={
            "z_scope": StubSource("z_scope"),
            "a_scope": StubSource("a_scope"),
        },
    )
    assert pipeline.available_scopes == ("a_scope", "z_scope")
