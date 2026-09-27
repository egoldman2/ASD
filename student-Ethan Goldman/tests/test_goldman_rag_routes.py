"""Protected backend queries against actual scoped Chroma/HTTP knowledge."""

from dataclasses import replace
from hashlib import sha256
from importlib import import_module
from pathlib import Path
import copy
import sys

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ai-services'))
from rag_server.config import RAGSettings
from conftest import LiveServer

adapter = import_module('student-Ethan Goldman.support_backend.rag_client')
QUESTION = 'What subject and initial message lengths are required when creating a customer support ticket?'


@pytest.fixture
def rag_host(tmp_path, monkeypatch):
    pytest.importorskip('chromadb', reason='Host retrieval checks require the shared RAG runtime dependencies')
    from rag_server.ollama_client import OllamaAnswer
    from rag_server.rag_http_server import create_app
    from rag_server.rag_pipeline import RAGPipeline
    monkeypatch.setenv('AI_MODE_ENABLED', 'true')
    monkeypatch.setenv('RAG_ENABLED', 'true')
    settings = replace(RAGSettings.from_environment(), chroma_path=tmp_path / 'chroma',
                       audit_path=tmp_path / 'audit.jsonl', request_timeout_seconds=1)
    calls = []
    class Model:
        def generate_answer(self, system, user, **kwargs):
            calls.append({'system': system, 'user': user})
            assert '5 to 160' in user and '1 to 2000' in user
            return OllamaAnswer('Ticket subjects need 5 to 160 characters; initial messages need 1 to 2000 characters [1].', 'test-support-model')
    def factory():
        return RAGPipeline(settings=settings, ollama_client=Model())
    with factory() as pipeline:
        assert pipeline.refresh_corpus(adapter.SUPPORT_SCOPE)['success']
    application = create_app(settings=settings, pipeline_factory=factory)
    from flask import request
    @application.before_request
    def verify_isolated_public_knowledge_request():
        assert not request.headers.get('Cookie') and not request.headers.get('Authorization')
        if request.path == '/answer':
            assert request.get_json()['scope'] == adapter.SUPPORT_SCOPE
    host = LiveServer(application)
    monkeypatch.setenv('RAG_SERVER_URL', host.url)
    try:
        yield host, calls
    finally:
        host.close()


def test_staff_backend_uses_fixed_scope_and_actual_knowledge(support_stack, rag_host):
    host, calls = rag_host
    admin = support_stack.admin()
    before = sha256(support_stack.database_path.read_bytes()).hexdigest()
    base = support_stack.backend.url + '/api/support/admin/rag'
    response = admin.post(base + '/answer', json={'question': QUESTION}, headers=support_stack.origin_headers, timeout=10)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['success'] and result['metadata']['model_invoked'] and calls
    assert result['data']['scope'] == adapter.SUPPORT_SCOPE and result['data']['model'] == 'test-support-model'
    assert result['citations'] and '160' in result['data']['answer'] and '2000' in result['data']['answer']
    for citation in result['citations']:
        filename = citation['source_id'].split('/', 1)[1]
        source = admin.get(base + '/sources/' + filename, timeout=10)
        assert source.status_code == 200 and '5 to 160' in source.text
        assert source.headers['Content-Type'].startswith('text/plain')
        assert source.headers['X-Content-Type-Options'] == 'nosniff'
    count = len(calls)
    negative = admin.post(base + '/answer', json={'question': 'quasar orbital spectroscopy wavelengths'},
                          headers=support_stack.origin_headers, timeout=10).json()
    assert negative['insufficient_context'] and negative['confidence'] == 'insufficient'
    assert not negative['metadata']['model_invoked'] and negative['citations'] == [] and len(calls) == count
    assert sha256(support_stack.database_path.read_bytes()).hexdigest() == before
    assert admin.cookies.get('ethan_session') not in response.text


def test_denied_and_invalid_rag_requests_never_contact_host(support_stack, monkeypatch):
    monkeypatch.setattr(adapter.SupportRAGClient, 'answer_question', lambda *args: pytest.fail('Invalid/denied query contacted RAG'))
    base = support_stack.backend.url + '/api/support/admin/rag'
    payload = {'question': QUESTION}
    assert requests.post(base + '/answer', json=payload, headers=support_stack.origin_headers, timeout=10).status_code == 401
    assert requests.get(base + '/sources/ticket_workflow.md', timeout=10).status_code == 401
    customer = support_stack.customer()
    assert customer.post(base + '/answer', json=payload, headers=support_stack.origin_headers, timeout=10).status_code == 403
    assert customer.get(base + '/sources/ticket_workflow.md', timeout=10).status_code == 403
    admin = support_stack.admin()
    assert admin.post(base + '/answer', json=payload, timeout=10).status_code == 403
    for body in ({'question': ''}, {'question': 'x' * 1001}, {'question': 42}, {'question': QUESTION, 'scope': 'chufeng_catalogue'},
                 {'question': QUESTION, 'top_k': True}, {'question': QUESTION, 'top_k': '2'}, {'question': QUESTION, 'top_k': 21},
                 {'question': QUESTION, 'ethan_session': 'fake'}, []):
        assert admin.post(base + '/answer', json=body, headers=support_stack.origin_headers, timeout=10).status_code == 400
    assert admin.post(base + '/answer', json={'question': 'x' * 5000}, headers=support_stack.origin_headers, timeout=10).status_code == 413
    assert admin.post(base + '/answer', data='not JSON', headers=support_stack.origin_headers, timeout=10).status_code == 400
    for filename in ('app.py', 'missing.md', '..%2Fticket_workflow.md'):
        assert admin.get(base + '/sources/' + filename, timeout=10).status_code == 404


@pytest.mark.parametrize('flag', ['AI_MODE_ENABLED', 'RAG_ENABLED'])
def test_disabled_rag_leaves_crud_usable_and_never_opens_http(support_stack, monkeypatch, flag):
    monkeypatch.setenv(flag, 'false')
    monkeypatch.setattr(adapter.requests, 'post', lambda *args, **kwargs: pytest.fail('Disabled RAG opened HTTP'))
    admin = support_stack.admin()
    response = admin.post(support_stack.backend.url + '/api/support/admin/rag/answer', json={'question': QUESTION},
                          headers=support_stack.origin_headers, timeout=10)
    assert response.status_code == 503 and response.json()['error']['code'] == 'RAG_DISABLED'
    assert admin.get(support_stack.backend.url + '/api/support/admin/tickets', timeout=10).status_code == 200


def test_unavailable_rag_has_no_fabricated_answer(support_stack, monkeypatch):
    monkeypatch.setenv('AI_MODE_ENABLED', 'true'); monkeypatch.setenv('RAG_ENABLED', 'true')
    monkeypatch.setenv('RAG_SERVER_URL', 'http://127.0.0.1:1')
    monkeypatch.setenv('RAG_CLIENT_TIMEOUT_SECONDS', '0.2')
    admin = support_stack.admin()
    response = admin.post(support_stack.backend.url + '/api/support/admin/rag/answer', json={'question': QUESTION},
                          headers=support_stack.origin_headers, timeout=10)
    assert response.status_code == 503 and response.json()['error']['code'] == 'RAG_UNAVAILABLE'
    assert response.json()['data'] is None and response.json()['citations'] == []
    assert admin.cookies.get('ethan_session') not in response.text


def test_rag_adapter_rejects_false_generation_and_forged_sources(rag_host):
    valid = adapter.SupportRAGClient().answer_question(QUESTION)
    modifications = [lambda item: item['metadata'].update(model_invoked=False),
                     lambda item: item['data'].update(scope='chufeng_catalogue'),
                     lambda item: item['citations'][0].update(source_id=adapter.SUPPORT_SCOPE + '/../private.md'),
                     lambda item: item['citations'][0].update(document_id='made-up'),
                     lambda item: item['citations'][0].update(rank=9),
                     lambda item: item['data'].update(answer='Invented source [9].'),
                     lambda item: item['data'].update(model=None)]
    for modify in modifications:
        result = copy.deepcopy(valid); modify(result)
        with pytest.raises(adapter.RAGClientError):
            adapter.validate_answer(result, QUESTION)
    with pytest.raises(adapter.RAGClientError) as error:
        adapter.validate_answer({'success': False, 'operation': 'answer_question', 'insufficient_context': False,
                                 'citations': [], 'error': {'code': 'OLLAMA_UNAVAILABLE', 'message': 'private upstream details'}}, QUESTION)
    assert error.value.status_code == 503 and 'private' not in str(error.value)


@pytest.mark.parametrize('setting,value', [('RAG_CLIENT_TIMEOUT_SECONDS', 'nan'), ('RAG_CLIENT_TIMEOUT_SECONDS', '121'),
                                         ('RAG_SERVER_URL', 'http://['), ('RAG_SERVER_URL', 'http://user:secret@example.test')])
def test_rag_configuration_fails_safely_before_network(monkeypatch, setting, value):
    monkeypatch.setenv('AI_MODE_ENABLED', 'true'); monkeypatch.setenv('RAG_ENABLED', 'true')
    monkeypatch.setenv(setting, value)
    monkeypatch.setattr(adapter.requests, 'post', lambda *args, **kwargs: pytest.fail('Bad config opened HTTP'))
    with pytest.raises(adapter.RAGClientError) as error:
        adapter.SupportRAGClient().answer_question(QUESTION)
    assert error.value.code == 'RAG_CONFIGURATION_ERROR'


def test_rag_transport_rejects_malformed_oversized_and_redirected_replies(monkeypatch):
    from flask import Flask, Response, request
    monkeypatch.setenv('AI_MODE_ENABLED', 'true'); monkeypatch.setenv('RAG_ENABLED', 'true')
    app = Flask('rag-transport-fixture')
    replies = [('not JSON', 200), ('x' * 65537, 200), ('', 302), ('{"success":true}', 503)]
    @app.post('/answer')
    def answer():
        request.get_data()
        body, status = replies.pop(0)
        return Response(body, status=status, headers={'Location': '/unexpected-redirect'})
    host = LiveServer(app)
    monkeypatch.setenv('RAG_SERVER_URL', host.url)
    try:
        for _ in range(4):
            with pytest.raises(adapter.RAGClientError) as error:
                adapter.SupportRAGClient().answer_question(QUESTION)
            assert error.value.code == 'RAG_INVALID_RESPONSE'
        assert replies == []
    finally:
        host.close()
