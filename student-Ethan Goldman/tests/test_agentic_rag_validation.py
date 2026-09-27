"""Scoped runner proofs from actual Chroma retrieval and bounded local HTTP."""

import copy
from dataclasses import replace
from importlib import import_module
import json
import os
from pathlib import Path
import sys
from threading import Thread

import pytest
from werkzeug.serving import make_server

from test_goldman_agentic_review import load_agentic_loop

sys.path.insert(0, str(Path(__file__).parents[2] / 'ai-services'))
import rag_validation
from rag_server.config import RAGSettings

QUESTION = 'What subject and initial message lengths are required when creating a customer support ticket?'
UNSUPPORTED = 'quasar orbital spectroscopy wavelengths'
SCOPE = 'ethan_goldman_support'


@pytest.fixture
def runner():
    return load_agentic_loop('feature_rag_validation')


@pytest.fixture
def feature_config(runner):
    config, _ = runner.load_feature('student-Ethan Goldman')
    base = 'student-Ethan Goldman/support_backend/'
    roles = {'server': 'ai-services/rag_server/rag_server.py', 'pipeline': 'ai-services/rag_server/rag_pipeline.py',
        'registry': 'ai-services/rag_server/rag_pipeline.py', 'source': 'ai-services/rag_server/sources/markdown_knowledge.py',
        'client': base + 'rag_client.py', 'frontend': base + 'templates/support_ui/admin/rag_panel.html',
        'routes': base + 'ui.py', 'controller': base + 'rag_routes.py', 'compose': 'docker-compose.yml'}
    config['rag_files'] = list(dict.fromkeys(roles.values()))
    config['rag_rules'] = {'required_scope': SCOPE, 'required_operations': sorted(rag_validation.OPERATIONS),
        'source_files': roles, 'frontend_route_prefix': '/api/support/ui/admin/rag/', 'backend_client_marker': 'SupportRAGClient',
        'probes': [{'name': 'supported', 'question': QUESTION, 'expected': 'grounded'},
                   {'name': 'unsupported', 'question': UNSUPPORTED, 'expected': 'insufficient'}]}
    return config


@pytest.fixture
def rag_host(tmp_path, monkeypatch):
    pytest.importorskip('chromadb', reason='Shared host retrieval dependencies required')
    from rag_server.rag_http_server import create_app
    from rag_server.rag_pipeline import RAGPipeline
    from rag_server.ollama_client import OllamaAnswer, OllamaClient
    monkeypatch.setenv('AI_MODE_ENABLED', 'true')
    monkeypatch.setenv('RAG_ENABLED', 'true')
    settings = replace(RAGSettings.from_environment(), chroma_path=tmp_path / 'chroma', audit_path=tmp_path / 'audit.jsonl',
        ollama_url='http://127.0.0.1:11434', ollama_model='qwen2.5:3b')
    calls = []
    class Model:
        def generate_answer(self, system, user, **kwargs):
            calls.append({'system': system, 'user': user})
            return OllamaAnswer('The cited passage contains the relevant recorded workflow guidance [1].', 'deterministic-test-model')
    control = {"settings": settings, "model": Model()}
    def factory():
        return RAGPipeline(settings=control["settings"], ollama_client=control["model"])
    app = create_app(settings=settings, pipeline_factory=factory)
    from flask import request
    @app.before_request
    def no_private_context():
        assert not request.headers.get('Cookie') and not request.headers.get('Authorization')
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv('RAG_SERVER_URL', f'http://127.0.0.1:{server.server_port}')
    try:
        yield {'calls': calls, 'settings': settings, 'factory': factory,
               'set_model': lambda value: control.update(model=value),
               'set_settings': lambda value: control.update(settings=value), 'ollama_type': OllamaClient}
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.parametrize('flag', ['AI_MODE_ENABLED', 'RAG_ENABLED'])
def test_disabled_runner_preserves_source_checks_without_opening_http(runner, feature_config, monkeypatch, flag):
    monkeypatch.setenv('AI_MODE_ENABLED', 'true')
    monkeypatch.setenv('RAG_ENABLED', 'true')
    monkeypatch.setenv(flag, 'false')
    monkeypatch.setattr(rag_validation, 'read_json', lambda *a, **k: pytest.fail('Disabled HTTP'))
    evidence = runner.collect_evidence('rag', feature_config)
    checks, runtime = evidence['verified_checks'], evidence['runtime']
    assert all(checks[name] for name in ('required_scope_registered', 'all_required_operations_registered',
        'grounding_controls_present', 'frontend_uses_backend_rag_routes', 'rag_server_not_in_compose'))
    assert not runtime['attempted'] and not runtime['validation_complete'] and flag in runtime['skip_reason']


def test_runner_retains_passages_answer_sources_and_model_free_negative(runner, feature_config, rag_host):
    runtime = runner.collect_evidence('rag', feature_config)['runtime']
    assert runtime['validation_complete'] and runtime['refresh_verified'], runtime
    supported, unsupported = runtime['probes']
    assert supported['retrieval']['data']['results'][0]['text']
    assert supported['answer']['citations'] and supported['answer']['confidence'] in {'low', 'medium', 'high'}
    assert supported['answer']['data']['model'] == 'deterministic-test-model'
    assert unsupported['generation_skipped'] and unsupported['answer']['citations'] == []
    assert unsupported['answer']['data']['model'] is None and len(rag_host['calls']) == 1
    assert '5 to 160' in rag_host['calls'][0]['user'] and '1 to 2000' in rag_host['calls'][0]['user']


def test_metadata_and_citation_counts_cannot_validate_forged_answers(runner, feature_config, rag_host):
    supported = runner.collect_evidence('rag', feature_config)['runtime']['probes'][0]
    retrieval, original = supported['retrieval'], supported['answer']
    mutations = [lambda x: x['data'].update(scope='chufeng_catalogue'),
        lambda x: x['data'].update(question='Other query'), lambda x: x['metadata'].update(model_invoked=False),
        lambda x: x['data'].update(model=None), lambda x: x['data'].update(retrieved_count=True),
        lambda x: x['citations'][0].update(source_id='invented-source'), lambda x: x['citations'][0].update(document_id='invented'),
        lambda x: x['citations'][0].update(rank=19), lambda x: x['data'].update(answer='Unsupported new paragraph.\n\nCited text [1].'),
        lambda x: x['data'].update(answer='Invented citation [19].'), lambda x: x['citations'].append(copy.deepcopy(x['citations'][0]))]
    for mutation in mutations:
        changed = copy.deepcopy(original)
        mutation(changed)
        assert rag_validation.answer_state(changed, retrieval, SCOPE, QUESTION) == 'invalid'
    changed = copy.deepcopy(retrieval)
    changed['citations'][0]['scope'] = 'chufeng_catalogue'
    assert not rag_validation.valid_retrieval(changed, SCOPE, QUESTION, 5)


def test_failed_positive_retains_negative_and_reports_incomplete_evidence(runner, feature_config, rag_host):
    unavailable = rag_host['ollama_type'](settings=replace(rag_host['settings'], ollama_url='http://127.0.0.1:1', request_timeout_seconds=0.1))
    rag_host['set_model'](unavailable)
    evidence = runner.collect_evidence('rag', feature_config)
    runtime = evidence['runtime']
    assert runtime['available'] and not runtime['validation_complete'] and runtime['insufficient_context_verified']
    assert runtime['probes'][0]['state'] == 'unavailable' and runtime['probes'][0]['answer_status'] == 503
    assert runtime['probes'][0]['answer']['data'] is None
    assert runtime['probes'][1]['verified'] and not runtime['grounded_answer_verified']
    review = runner._grounded_fallback('rag', evidence, [])
    assert 'workflow did not pass' in review and 'ethan_goldman_support' in review


def test_expected_values_and_missing_negative_cannot_pass_complete_validation(runner, feature_config, rag_host):
    feature_config['rag_rules']['probes'][0]['expect'] = [{'path': 'data.model', 'value': 'fabricated-model'}]
    runtime = runner.collect_evidence('rag', feature_config)['runtime']
    assert not runtime['validation_complete'] and not runtime['probes'][0]['verified']
    assert runtime['probes'][0]['state'] == 'grounded' and runtime['probes'][1]['verified']
    feature_config['rag_rules']['probes'][0].pop('expect')
    feature_config['rag_rules']['probes'].pop()
    runtime = runner.collect_evidence('rag', feature_config)['runtime']
    assert runtime['probe_complete'] and runtime['grounded_answer_verified'] and not runtime['validation_complete']


def test_missing_service_and_scope_are_explicit_failures(runner, feature_config, rag_host, monkeypatch):
    feature_config['rag_rules']['required_scope'] = 'unregistered_feature'
    runtime = runner.collect_evidence('rag', feature_config)['runtime']
    assert runtime['available'] and not runtime['required_scope_available'] and not runtime['refresh_verified']
    assert all(probe['state'] == 'skipped' and not probe['attempted'] for probe in runtime['probes'])
    monkeypatch.setenv('RAG_SERVER_URL', 'http://127.0.0.1:1')
    feature_config['rag_timeout_seconds'] = 0.1
    runtime = runner.collect_evidence('rag', feature_config)['runtime']
    assert runtime['attempted'] and not runtime['available'] and runtime['error'] == 'ConnectionError'


def test_catalogue_uses_same_host_probe_contract(runner, rag_host, tmp_path):
    config, _ = runner.load_feature('student-Chufeng')
    path = tmp_path / 'products.db'
    from hashlib import sha256
    import_module('student-Chufeng.database.init_db').initialize_database(path, reset=True)
    app = import_module('student-Chufeng.database.api').create_app(path)
    server = make_server('127.0.0.1', 0, app)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    settings = rag_host['settings']
    rag_host['set_settings'](replace(settings, product_database_api_url=f'http://127.0.0.1:{server.server_port}/api/database/products'))
    before = sha256(path.read_bytes()).hexdigest()
    try:
        runtime = runner.collect_evidence('rag', config)['runtime']
        assert runtime['validation_complete'] and runtime['probe']['expected'] == 'grounded', runtime
        assert all(citation['scope'] == 'chufeng_catalogue' for citation in runtime['probe']['answer']['citations'])
        assert sha256(path.read_bytes()).hexdigest() == before
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_review_claims_do_not_replace_observed_answers_or_negative_checks(runner, feature_config, monkeypatch):
    monkeypatch.setenv('AI_MODE_ENABLED', 'true'); monkeypatch.setenv('RAG_ENABLED', 'true')
    evidence = runner.collect_rag_evidence(feature_config, runtime_probe=lambda config: {'available': True,
        'health': {'available_scopes': [SCOPE], 'operations': sorted(rag_validation.OPERATIONS)}})
    candidate = ' '.join(feature_config['rag_files'][:3]) + ''' The ethan_goldman_support refresh_corpus,
    retrieve_context and answer_question operations succeeded. The grounded answer and citations were verified.
    The unsupported question passed without generation. Therefore these configured source files establish
    complete actual AI validation and fully passing runtime behaviour across every required case.
    '''
    issues = runner._deterministic_issues('rag', evidence, candidate)
    assert any('without collected live answer evidence' in issue for issue in issues)
    assert any('model-free' in issue for issue in issues)


@pytest.mark.skipif(os.getenv('RUN_LIVE_RAG_AI') != '1', reason='Opt-in actual host-model generation')
def test_actual_model_response_matches_runner_answer_and_sources(runner, feature_config, rag_host):
    outputs = []
    model_type = rag_host['ollama_type']
    class ObservedModel(model_type):
        def generate_answer(self, system, user, **kwargs):
            result = super().generate_answer(system, user, **kwargs)
            outputs.append({'system': system, 'user': user, 'answer': result.content, 'model': result.model})
            return result
    rag_host['set_model'](ObservedModel(settings=rag_host['settings']))
    evidence = runner.collect_evidence('rag', feature_config)
    assert evidence['runtime']['validation_complete'], evidence['runtime']
    answer = evidence['runtime']['probes'][0]['answer']['data']['answer']
    assert outputs and outputs[-1]['model'] == 'qwen2.5:3b' and outputs[-1]['answer'].strip() == answer
    assert '5 to 160' in outputs[-1]['user'] and '1 to 2000' in outputs[-1]['user']
    assert all(value in answer for value in ('5', '160', '1', '2000'))
    assert not evidence['runtime']['probes'][1]['answer']['metadata']['model_invoked']
    Path('/tmp/asd-g6-live-rag-validation.json').write_text(json.dumps({'evidence': evidence, 'native_model_outputs': outputs}, indent=2))


def test_review_summary_preserves_outcomes_but_does_not_duplicate_full_passages(runner, feature_config, rag_host):
    evidence = runner.collect_evidence('rag', feature_config)
    summary = runner._runtime_review_summary('rag', evidence['runtime'], excerpts=True)
    assert len(summary['probes']) == len(evidence['runtime']['probes']) == 2
    assert all(item['verified'] for item in summary['probes'])
    assert summary['probes'][0]['citations'] and summary['probes'][1]['generation_skipped']
    assert all(len(item['text']) <= 240 for item in summary['probes'][0]['passage_excerpts'])
    digest = runner._evidence_digest('rag', evidence)
    assert len(digest) < 16000 and 'review_limitations' in digest
    broken = {'probes': [{'state': 'invalid', 'answer': [], 'retrieval': {'data': None}}]}
    assert runner._runtime_review_summary('rag', broken, excerpts=True)['probes'][0]['state'] == 'invalid'


def test_review_model_requires_complete_bounded_named_response(runner, monkeypatch):
    monkeypatch.setenv('AI_MODE_ENABLED', 'true')
    body = {'done': True, 'model': runner.OLLAMA_MODEL, 'done_reason': 'stop', 'message': {'content': 'Observed review text.'}}
    requested = []
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, size):
            return json.dumps(body).encode()[:size]
    def open_response(*args, **kwargs):
        requested.append(args)
        return Response()
    monkeypatch.setattr(runner.request, 'urlopen', open_response)
    assert runner._call_ollama('Review the collected evidence.') == 'Observed review text.'
    for changes in ({'done': False}, {'model': 'invented-model'}, {'done_reason': 'length'}, {'message': {'content': []}}):
        original = copy.deepcopy(body)
        body.update(changes)
        with pytest.raises(runner.OllamaError):
            runner._call_ollama('Review the collected evidence.')
        body.clear(); body.update(original)
    count = len(requested)
    with pytest.raises(runner.OllamaError, match='context budget'):
        runner._call_ollama('x' * 24001)
    assert len(requested) == count
    body['message']['content'] = 'x' * 65537
    with pytest.raises(runner.OllamaError, match='size limit'):
        runner._call_ollama('Review the collected evidence.')


@pytest.mark.skipif(os.getenv('RUN_LIVE_VALIDATION') != '1', reason='Opt-in actual Plan/Act/Observe/Adapt outputs for both modes')
def test_live_agentic_modes_produce_actual_review_outputs(runner, feature_config, rag_host, live_mcp, monkeypatch):
    from hashlib import sha256
    from test_agentic_mcp_validation import session_context, feature_config as make_mcp_config
    # G6 exercises temporary feature configuration; E6 supplies persistent CLI files.
    mcp_config = make_mcp_config.__wrapped__(runner)
    secret = session_context(mcp_config, live_mcp, monkeypatch)
    monkeypatch.setenv('AI_MODE_ENABLED', 'true'); monkeypatch.setenv('RAG_ENABLED', 'true')
    monkeypatch.setenv('MCP_ENABLED', 'true'); monkeypatch.setenv('OLLAMA_URL', 'http://127.0.0.1:11434')
    monkeypatch.setenv('MCP_ASSISTANT_MODEL', 'qwen2.5:3b')
    monkeypatch.setattr(runner, 'OLLAMA_MODEL', 'qwen2.5:3b')
    monkeypatch.setattr(runner, 'OLLAMA_URL', 'http://127.0.0.1:11434')
    rag_host['set_model'](rag_host['ollama_type'](settings=rag_host['settings']))
    prompt = ('Review only Ethan Goldman Customer Support. Keep every review under 170 words. '
              'Cite at least three configured source paths. Name configured tools or scope/operations. '
              'Separate observed runtime outcomes from source markers and evidence limitations. '
              'Never claim CI or test success; neither is collected by this review. '
              'Treat bounded excerpts as excerpts and not missing implementation.')
    prompt_path = Path('/tmp/asd-g6-feature-review-prompt.txt')
    prompt_path.write_text(prompt)
    before = sha256(live_mcp.database_path.read_bytes()).hexdigest()
    save_original = runner.save_evidence_report
    root = runner.PROJECT_ROOT
    def save_local(*args):
        try:
            runner.PROJECT_ROOT = Path('/tmp/asd-g6-agentic-output')
            return save_original(*args)
        finally:
            runner.PROJECT_ROOT = root
    monkeypatch.setattr(runner, 'save_evidence_report', save_local)
    results = []
    for mode, config in (('mcp', mcp_config), ('rag', feature_config)):
        config['prompt_path'] = str(prompt_path)
        config['mode_prompts'] = {}
        monkeypatch.setattr(runner, 'load_feature', lambda directory, config=config: (config, prompt))
        result = runner.run_agentic_loop('student-Ethan Goldman', mode, save=True)
        runtime = result['evidence']['runtime']
        assert runtime['assistant_verified'] if mode == 'mcp' else runtime['validation_complete']
        assert Path(result['output_path']).is_file() and '## Final Review' in Path(result['output_path']).read_text()
        assert secret not in json.dumps(result)
        results.append(result)
    assert sha256(live_mcp.database_path.read_bytes()).hexdigest() == before
    Path('/tmp/asd-g6-live-agentic-modes.json').write_text(json.dumps(results, indent=2))
