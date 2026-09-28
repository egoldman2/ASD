"""Staff knowledge fragments over real auth, backend and shared retrieval."""

from dataclasses import replace
from hashlib import sha256
from importlib import import_module
import json
import os
from pathlib import Path

import pytest
import requests

from test_goldman_rag_routes import QUESTION, rag_host
from conftest import LiveServer

adapter = import_module('student-Ethan Goldman.support_backend.rag_client')


def post(stack, session, data):
    return session.post(stack.backend.url + '/api/support/ui/admin/rag/answer', data=data,
                        headers=stack.htmx_headers, timeout=95)


def test_knowledge_panel_and_actual_source_links(support_stack, rag_host):
    stack, admin = support_stack, support_stack.admin()
    before = sha256(stack.database_path.read_bytes()).hexdigest()
    queue = admin.get(stack.backend.url + '/api/support/ui/admin/tickets', timeout=10)
    workspace = admin.get(stack.backend.url + '/api/support/ui/admin/tickets/2002', timeout=10)
    for response in (queue, workspace):
        assert response.status_code == 200 and 'Support knowledge assistant' in response.text
        assert 'hx-post="/api/support/ui/admin/rag/answer"' in response.text
        assert 'hx-target="#rag-answer-result"' in response.text
        assert 'Support data assistant' in response.text
    answer = post(stack, admin, {'question': QUESTION})
    assert answer.status_code == 200 and 'Knowledge answer' in answer.text
    assert '5 to 160' in answer.text and '1 to 2000' in answer.text
    assert 'Confidence:' in answer.text and 'not a guarantee of correctness' in answer.text
    assert 'Model: test-support-model' in answer.text and 'generation attempt' in answer.text
    assert '/api/support/ui/admin/rag/sources/ticket_workflow.md' in answer.text and 'passage ' in answer.text
    assert admin.get(stack.backend.url + '/api/support/admin/rag/sources/ticket_workflow.md', timeout=10).status_code == 200
    preview = admin.get(stack.backend.url + '/api/support/ui/admin/rag/sources/ticket_workflow.md', timeout=10)
    assert preview.status_code == 200 and 'Support knowledge source' in preview.text and '5 to 160' in preview.text
    assert preview.headers['Content-Type'].startswith('text/html')
    assert sha256(stack.database_path.read_bytes()).hexdigest() == before


def test_knowledge_nonanswer_and_unavailable_states(support_stack, rag_host, monkeypatch):
    stack, admin = support_stack, support_stack.admin()
    host, calls = rag_host
    before = len(calls)
    unsupported = post(stack, admin, {'question': 'quasar orbital spectroscopy wavelengths'})
    assert unsupported.status_code == 200 and 'Insufficient context' in unsupported.text
    assert 'no AI answer was generated' in unsupported.text and 'Confidence: Insufficient' in unsupported.text
    assert 'Knowledge answer' not in unsupported.text and 'Answer sources' not in unsupported.text
    assert len(calls) == before
    monkeypatch.setenv('RAG_SERVER_URL', 'http://127.0.0.1:1')
    unavailable = post(stack, admin, {'question': QUESTION})
    assert unavailable.status_code == 503 and 'Knowledge assistant unavailable' in unavailable.text
    assert 'Try again when the service is available' in unavailable.text and 'Knowledge answer' not in unavailable.text
    monkeypatch.setenv('AI_MODE_ENABLED', 'false')
    disabled = post(stack, admin, {'question': QUESTION})
    assert disabled.status_code == 503 and 'disabled' in disabled.text.lower()
    assert admin.get(stack.backend.url + '/api/support/admin/tickets', timeout=10).status_code == 200


def test_knowledge_fragment_rejects_unauthorised_and_forged_forms(support_stack, monkeypatch):
    monkeypatch.setattr(adapter.SupportRAGClient, 'answer_question', lambda *args: pytest.fail('Invalid form called RAG'))
    stack, admin = support_stack, support_stack.admin()
    anonymous = post(stack, requests.Session(), {'question': QUESTION})
    customer = post(stack, stack.customer(), {'question': QUESTION})
    assert anonymous.status_code == 401 and customer.status_code == 403
    assert 'id="rag-answer-result"' not in anonymous.text
    for data in ({'question': ''}, {'question': 'x' * 1001}, {'question': QUESTION, 'scope': 'other'},
                 {'question': QUESTION, 'scope': ''}, {'question': QUESTION, 'top_k': '1'},
                 [('question', 'one'), ('question', 'two')]):
        invalid = post(stack, admin, data)
        assert invalid.status_code == 400 and 'Check your question' in invalid.text
    assert post(stack, admin, {'question': 'x' * 5000}).status_code == 413
    no_origin = admin.post(stack.backend.url + '/api/support/ui/admin/rag/answer', data={'question': QUESTION}, timeout=10)
    assert no_origin.status_code == 403


def test_knowledge_output_and_citation_labels_are_escaped(support_stack, rag_host):
    result = adapter.SupportRAGClient().answer_question(QUESTION)
    result['data']['answer'] = '<img src=x onerror=alert(1)> Ticket fields need review [1].'
    result['citations'][0]['label'] = '<script>alert(1)</script>'
    class Client:
        def answer_question(self, *args):
            return result
    support_stack.backend.server.app.extensions['support_rag_client'] = Client()
    response = post(support_stack, support_stack.admin(), {'question': QUESTION})
    assert response.status_code == 200 and '&lt;img' in response.text and '&lt;script&gt;' in response.text
    assert '<img' not in response.text and '<script>' not in response.text
    assert 'target="_blank" rel="noopener"' in response.text


@pytest.mark.skipif(os.getenv('RUN_LIVE_RAG_AI') != '1', reason='Opt-in actual model through protected staff fragments')
def test_live_staff_knowledge_examples_use_actual_model(support_stack, tmp_path, monkeypatch):
    pytest.importorskip('chromadb')
    from rag_server.config import RAGSettings
    from rag_server.ollama_client import OllamaClient
    from rag_server.rag_http_server import create_app
    from rag_server.rag_pipeline import RAGPipeline
    monkeypatch.setenv('AI_MODE_ENABLED', 'true'); monkeypatch.setenv('RAG_ENABLED', 'true')
    settings = replace(RAGSettings.from_environment(), ollama_url='http://127.0.0.1:11434', ollama_model='qwen2.5:3b',
                       request_timeout_seconds=45, chroma_path=tmp_path / 'chroma', audit_path=tmp_path / 'audit.jsonl')
    traces = []
    class Model(OllamaClient):
        def generate_answer(self, system, user, **kwargs):
            output = super().generate_answer(system, user, **kwargs)
            traces[-1]['generation'].append({'system_prompt': system, 'user_prompt': user,
                                             'model': output.model, 'content': output.content})
            return output
    model = Model(settings=settings)
    def factory():
        return RAGPipeline(settings=settings, ollama_client=model)
    with factory() as pipeline:
        assert pipeline.refresh_corpus(adapter.SUPPORT_SCOPE)['success']
    host = LiveServer(create_app(settings=settings, pipeline_factory=factory))
    monkeypatch.setenv('RAG_SERVER_URL', host.url)
    admin = support_stack.admin()
    before = sha256(support_stack.database_path.read_bytes()).hexdigest()
    try:
        for question, expected in ((QUESTION, ['160', '2000']),
            ('Which statuses and priorities are allowed when staff triage a ticket?', ['needs_triage', 'open', 'pending', 'solved', 'urgent']),
            ('Why are unresolved tickets included in the attention list, and what does inactivity mean?', ['48', 'inactivity'])):
            traces.append({'question': question, 'generation': []})
            with factory() as pipeline:
                traces[-1]['retrieval'] = pipeline.retrieve_context(adapter.SUPPORT_SCOPE, question)
            response = post(support_stack, admin, {'question': question})
            traces[-1].update(status=response.status_code, fragment=response.text)
            assert response.status_code == 200 and 'Knowledge answer' in response.text, response.text
            assert 'Model: qwen2.5:3b' in response.text and '/api/support/ui/admin/rag/sources/' in response.text
            assert traces[-1]['generation']
            for value in expected:
                assert value.casefold() in response.text.casefold(), response.text
        count = sum(len(item['generation']) for item in traces)
        traces.append({'question': 'quasar orbital spectroscopy wavelengths', 'generation': []})
        response = post(support_stack, admin, {'question': traces[-1]['question']})
        traces[-1].update(status=response.status_code, fragment=response.text)
        assert response.status_code == 200 and 'Insufficient context' in response.text
        assert sum(len(item['generation']) for item in traces) == count
        assert sha256(support_stack.database_path.read_bytes()).hexdigest() == before
    finally:
        Path('/tmp/asd-support-rag-ui-live.json').write_text(json.dumps(traces, indent=2))
        host.close()


def test_source_preview_is_staff_only_bounded_and_escaped(support_stack, tmp_path, monkeypatch):
    monkeypatch.setattr(adapter, 'KNOWLEDGE_DIRECTORY', tmp_path)
    file = tmp_path / 'review.md'
    file.write_text('# Review source\n\n<script>alert(1)</script>\n\nA documented workflow fact.')
    url = support_stack.backend.url + '/api/support/ui/admin/rag/sources/review.md'
    assert requests.get(url, timeout=10).status_code == 401
    assert support_stack.customer().get(url, timeout=10).status_code == 403
    admin = support_stack.admin()
    response = admin.get(url, timeout=10)
    assert response.status_code == 200 and '&lt;script&gt;' in response.text and '<script>' not in response.text
    assert 'A documented workflow fact.' in response.text and response.headers['Cache-Control'] == 'no-store'
    file.write_bytes(b'\xff')
    assert admin.get(url, timeout=10).status_code == 404
    file.write_text('x' * 65537)
    assert admin.get(url, timeout=10).status_code == 404
    assert admin.get(url.replace('review.md', 'missing.md'), timeout=10).status_code == 404
