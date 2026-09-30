"""Curated accounts/loyalty scope is registered and isolated."""

from rag_server.config import BASE_DIR
from rag_server.rag_pipeline import _default_sources, _system_prompt


SCOPE = "ethan_ting_accounts_loyalty"


def test_guide_source_contains_implemented_rules_without_customer_records(rag_settings):
    source = _default_sources(rag_settings)[SCOPE]
    documents = source.load_documents()
    text = "\n".join(document.text for document in documents)

    assert documents
    assert all(document.scope == SCOPE for document in documents)
    assert all(document.source_id.startswith(f"{SCOPE}/") for document in documents)
    assert "Bronze covers 0 to 499 points" in text
    assert "1,000,000 points" in text
    assert "does not automatically award points" in text
    assert "customer@asd.local" not in text
    assert (BASE_DIR / "knowledge" / "ethan_ting" / "accounts_and_loyalty.md").is_file()


def test_feature_prompt_requires_sources_and_abstention():
    prompt = _system_prompt(SCOPE)
    assert "Cite each factual paragraph" in prompt
    assert "Insufficient context to answer this question." in prompt
    assert "live customer's identity" in prompt
