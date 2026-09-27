"""Actual Chroma retrieval over curated sources, without AI generation."""

from dataclasses import replace
from pathlib import Path
import threading

import pytest
import requests
from werkzeug.serving import make_server

from rag_server.config import BASE_DIR, ConfigurationError, RAGSettings
from rag_server.rag_http_server import create_app
from rag_server.rag_pipeline import RAGPipeline
from rag_server.sources import MarkdownKnowledgeSource, SourceDataError


SUPPORT_SCOPE = 'ethan_goldman_support'


def source(directory, scope=SUPPORT_SCOPE):
    return MarkdownKnowledgeSource(scope=scope, directory=directory, source_name='Curated test knowledge')


def test_source_chunks_are_bounded_attributed_and_reproducible(tmp_path):
    text = '# Support workflow\n\n## Ticket creation\n\n' + 'Customer ticket message. ' * 120
    (tmp_path / 'workflow.md').write_text(text)
    first = source(tmp_path).load_documents()
    second = source(tmp_path).load_documents()
    assert len(first) > 1 and first == second
    assert all(doc.document_id.startswith(SUPPORT_SCOPE + ':') for doc in first)
    assert all(doc.source_id == SUPPORT_SCOPE + '/workflow.md' for doc in first)
    assert all(doc.citation_label == 'Support workflow: Ticket creation' for doc in first)
    assert all(len(doc.text) < 1400 and doc.metadata['curated'] for doc in first)
    assert [doc.metadata['chunk_index'] for doc in first] == list(range(len(first)))


def test_curated_source_rejects_symlinks_bad_encoding_and_oversized_files(tmp_path):
    corpus = tmp_path / 'corpus'
    corpus.mkdir()
    outside = tmp_path / 'private.md'
    outside.write_text('Private data must not enter an approved corpus.')
    pointer = corpus / 'linked.md'
    pointer.symlink_to(outside)
    with pytest.raises(SourceDataError):
        source(corpus).load_documents()
    pointer.unlink()
    pointer.write_bytes(b'\xff')
    with pytest.raises(SourceDataError):
        source(corpus).load_documents()
    pointer.write_text('x' * (64 * 1024 + 1))
    with pytest.raises(SourceDataError):
        source(corpus).load_documents()
    pointer.write_text('')
    with pytest.raises(SourceDataError):
        source(corpus).load_documents()
    link = tmp_path / 'linked-directory'
    link.symlink_to(corpus, target_is_directory=True)
    with pytest.raises(SourceDataError):
        source(link).load_documents()


def test_real_persistent_index_scope_updates_and_failure_preservation(rag_settings, tmp_path):
    support_dir, other_dir = tmp_path / 'support', tmp_path / 'other'
    support_dir.mkdir(); other_dir.mkdir()
    file = support_dir / 'workflow.md'
    file.write_text('# Support\n\nCustomer ticket creation needs a subject and initial message.\n\nStaff triage uses category and priority.')
    (other_dir / 'product.md').write_text('# Catalogue\n\nKeyboard product inventory stock availability.')
    settings = replace(rag_settings, min_relevance_score=0.25, embedding_dimensions=256)
    support, other = source(support_dir), source(other_dir, 'catalogue_fixture')
    sources = {support.scope: support, other.scope: other}
    class NoModel:
        def generate_answer(self, *args):
            raise AssertionError('Retrieval must not call a model')
    with RAGPipeline(settings=settings, sources=sources, ollama_client=NoModel()) as pipeline:
        assert pipeline.refresh_corpus(support.scope)['success']
        assert pipeline.refresh_corpus(other.scope)['success']
        found = pipeline.retrieve_context(support.scope, 'customer ticket subject message', 2)
        assert found['success'] and found['data']['result_count'] > 0
        assert all(item['scope'] == support.scope for item in found['citations'])
        unrelated = pipeline.retrieve_context(support.scope, 'quasar orbital spectroscopy wavelengths', 2)
        assert unrelated['insufficient_context'] and unrelated['data']['results'] == []
        old_revision = found['data']['results'][0]['metadata']['revision']
        file.write_text('# Support\n\nCustomer ticket creation needs a subject and initial message. Updated workflow guidance.')
        changed = pipeline.refresh_corpus(support.scope)
        assert changed['data']['updated_count'] == 1 and changed['data']['removed_count'] == 1
        found = pipeline.retrieve_context(support.scope, 'customer ticket subject message', 2)
        assert found['data']['results'][0]['metadata']['revision'] != old_revision
        file.write_bytes(b'\xff')
        failed = pipeline.refresh_corpus(support.scope)
        assert not failed['success'] and failed['error']['code'] == 'SOURCE_DATA_INVALID'
        assert pipeline.retrieve_context(support.scope, 'customer ticket subject message', 2)['data']['result_count'] == 1
        assert pipeline.retrieve_context(other.scope, 'keyboard product stock', 1)['data']['result_count'] == 1
    with RAGPipeline(settings=settings, sources=sources, ollama_client=NoModel()) as restarted:
        assert restarted.retrieve_context(support.scope, 'customer ticket subject message', 1)['data']['result_count'] == 1


def test_host_http_retrieves_actual_support_knowledge_and_rejects_bad_requests(rag_settings):
    settings = replace(rag_settings, min_relevance_score=0.25, embedding_dimensions=256)
    server = make_server('127.0.0.1', 0, create_app(settings=settings), threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{server.server_port}'
    try:
        health = requests.get(url + '/health', timeout=10).json()
        assert health['available_scopes'] == ['chufeng_catalogue', SUPPORT_SCOPE]
        refresh = requests.post(url + '/refresh', json={'scope': SUPPORT_SCOPE}, timeout=10)
        assert refresh.status_code == 200 and refresh.json()['data']['document_count'] >= 2
        found = requests.post(url + '/retrieve', json={'scope': SUPPORT_SCOPE, 'query': 'subject initial message customer ticket characters'}, timeout=10)
        assert found.status_code == 200 and found.json()['data']['result_count'] > 0
        result = found.json()
        assert all(citation['scope'] == SUPPORT_SCOPE for citation in result['citations'])
        assert any('5 to 160' in row['text'] for row in result['data']['results'])
        assert all((BASE_DIR / 'knowledge' / 'ethan_goldman' / row['metadata']['source_file']).is_file()
                   for row in result['data']['results'])
        unsupported = requests.post(url + '/retrieve', json={'scope': SUPPORT_SCOPE, 'query': 'quasar orbital spectroscopy wavelengths'}, timeout=10)
        assert unsupported.json()['insufficient_context']
        for payload in ({'scope': SUPPORT_SCOPE, 'query': ''}, {'scope': SUPPORT_SCOPE, 'query': 'x' * 1001},
                        {'scope': SUPPORT_SCOPE, 'query': 'ticket', 'top_k': True},
                        {'scope': SUPPORT_SCOPE, 'query': 'ticket', 'top_k': 21},
                        {'scope': SUPPORT_SCOPE, 'query': 'ticket', 'path': '/private/file'},
                        {'scope': 'unregistered_scope', 'query': 'ticket'}):
            assert requests.post(url + '/retrieve', json=payload, timeout=10).status_code in (400, 404)
        assert requests.post(url + '/retrieve', json=['ticket'], timeout=10).status_code == 400
        assert requests.post(url + '/retrieve', data='not JSON', timeout=10).status_code == 400
        assert requests.post(url + '/retrieve', json={'query': 'x' * 70000}, timeout=10).status_code == 413
    finally:
        server.shutdown(); thread.join(timeout=5); server.server_close()


@pytest.mark.parametrize('value', ['nan', 'inf', '0', '91'])
def test_rag_timeout_settings_are_finite_and_bounded(value, monkeypatch):
    monkeypatch.setenv('RAG_REQUEST_TIMEOUT_SECONDS', value)
    with pytest.raises(ConfigurationError):
        RAGSettings.from_environment()
