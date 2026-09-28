"""Feature-scoped runner evidence from real MCP and authenticated application reads."""

import copy
from hashlib import sha256
from importlib import import_module
import json
import os
from pathlib import Path
import sys
from threading import Thread

import pytest

from werkzeug.serving import make_server
from test_goldman_agentic_review import load_agentic_loop
from test_goldman_mcp_assistant import ScriptedModel, call, final, assistant, adapter

sys.path.insert(0, str(Path(__file__).parents[2] / 'ai-services'))
import mcp_validation


@pytest.fixture
def runner():
    return load_agentic_loop('feature_mcp_validation')


@pytest.fixture
def feature_config(runner):
    """Exercise shared G5 configuration without prematurely changing E6 registration."""
    config, _ = runner.load_feature('student-Ethan Goldman')
    base = 'student-Ethan Goldman/support_backend/'
    roles = {'server': 'ai-services/mcp_server/server.py',
             'tools': 'ai-services/mcp_server/tools/ethan_goldman_support.py',
             'client': base + 'mcp_client.py', 'frontend': base + 'templates/support_ui/admin/mcp_panel.html',
             'routes': base + 'ui.py', 'controller': base + 'mcp_routes.py', 'compose': 'docker-compose.yml'}
    config['mcp_files'] = list(roles.values()) + ['shared/mcp_client.py']
    config['mcp_rules'] = {'required_tools': sorted(adapter.GOLDMAN_ALLOWED_TOOLS), 'source_files': roles,
        'frontend_route_prefix': '/api/support/ui/admin/mcp/', 'backend_client_marker': 'SupportMCPClient',
        'request_context': {'cookie_name': 'ethan_session', 'cookie_env': 'SUPPORT_VALIDATION_SESSION'},
        'probes': [
            {'tool': adapter.SEARCH_TICKETS, 'arguments': {'limit': 1}, 'expect': [{'path': 'result.total', 'value': 12}]},
            {'tool': adapter.GET_TICKET_CONTEXT, 'arguments': {'ticket_id': 2002, 'message_limit': 1},
             'expect': [{'path': 'result.id', 'value': 2002}]},
            {'tool': adapter.GET_QUEUE_SUMMARY, 'arguments': {}, 'expect': [{'path': 'result.unresolved', 'value': 9}]},
            {'tool': adapter.GET_TICKETS_NEEDING_ATTENTION, 'arguments': {'limit': 1},
             'expect': [{'path': 'result.total', 'value': 9}]},
            {'name': 'no-match', 'tool': adapter.SEARCH_TICKETS, 'arguments': {'search': 'unique-nonexistent-case'},
             'expect': [{'path': 'result.total', 'value': 0}]},
        ]}
    return config


def session_context(config, stack, monkeypatch, *, customer=False):
    session = stack.customer() if customer else stack.admin()
    secret = session.cookies.get('ethan_session')
    monkeypatch.setenv('SUPPORT_VALIDATION_SESSION', secret)
    config['mcp_rules']['assistant_probes'] = [{
        'url': stack.backend.url + '/api/support/admin/mcp/assistant', 'origin': stack.origin_headers['Origin'],
        'payload': {'question': 'How does our support workload look?'}, 'expected_tools': [adapter.GET_QUEUE_SUMMARY],
        'expect': [{'path': 'observations.0.result.total', 'value': 12}],
    }]
    return secret


def test_feature_sources_and_disabled_execution_remain_distinct(runner, feature_config, monkeypatch):
    monkeypatch.setenv('MCP_ENABLED', 'false')
    monkeypatch.setattr(import_module("shared.mcp_client").MCPClient, 'list_tools', lambda *a, **k: pytest.fail('No disabled transport'))
    evidence = runner.collect_mcp_evidence(feature_config)
    checks = evidence['verified_checks']
    assert all(checks[name] for name in ('all_required_tools_registered', 'all_required_tools_allowlisted',
        'read_only_annotations_present', 'frontend_uses_backend_mcp_routes', 'mcp_server_not_in_compose'))
    assert evidence['runtime']['attempted'] is False and evidence['runtime']['probe_complete'] is False
    assert evidence['runtime']['assistant_verified'] is False
    assert 'chufeng_search_products' in checks['definition_tool_names']  # Shared factory, scoped allowlist.
    assert 'runtime' in runner._grounding_summary('mcp', evidence)


def test_all_four_protocol_reads_and_failed_checks_have_individual_outcomes(runner, feature_config, live_mcp, monkeypatch):
    secret = session_context(feature_config, live_mcp, monkeypatch)
    monkeypatch.setenv('AI_MODE_ENABLED', 'false')
    before = sha256(live_mcp.database_path.read_bytes()).hexdigest()
    evidence = runner.collect_mcp_evidence(feature_config)
    runtime = evidence['runtime']
    assert runtime['required_tools_discovered'] and runtime['probe_complete'] and runtime['all_required_tools_probed'], runtime
    assert len(runtime['probes']) == 5 and all(probe['checks_passed'] for probe in runtime['probes'])
    assert runtime['assistant_probes'][0]['attempted'] is False and runtime['assistant_verified'] is False
    assert secret not in json.dumps(evidence)
    assert sha256(live_mcp.database_path.read_bytes()).hexdigest() == before
    changed = copy.deepcopy(feature_config)
    changed['mcp_rules']['probes'][0]['expect'][0]['value'] = 999
    failed = runner.collect_mcp_evidence(changed)['runtime']
    assert failed['available'] and failed['required_tools_discovered'] and not failed['probe_complete']
    assert failed['probes'][0]['success'] and not failed['probes'][0]['checks_passed']
    assert all(probe['success'] for probe in failed['probes'][1:])
    review = runner._grounded_fallback('mcp', {'verified_checks': evidence['verified_checks'], 'runtime': failed}, [])
    assert 'missing or failed' in review and 'review prose does not prove AI integration' in review


def test_customer_and_missing_auth_never_pass_private_tool_probes(runner, feature_config, live_mcp, monkeypatch):
    secret = session_context(feature_config, live_mcp, monkeypatch, customer=True)
    feature_config['mcp_rules'].pop('assistant_probes')
    runtime = runner.collect_mcp_evidence(feature_config)['runtime']
    assert runtime['available'] and not runtime['probe_complete'] and not runtime['all_required_tools_probed']
    assert len(runtime['probes']) == 5 and all(probe['error_code'] == 'TOOL_NOT_ALLOWED' for probe in runtime['probes'])
    assert secret not in json.dumps(runtime)
    feature_config['mcp_rules'].pop('request_context')
    runtime = runner.collect_mcp_evidence(feature_config)['runtime']
    assert all(probe['error_code'] == 'AUTHENTICATION_REQUIRED' for probe in runtime['probes'])
    feature_config['mcp_rules']['request_context'] = {'cookie_name': 'ethan_session', 'cookie_env': 'MISSING_PROBE_SESSION'}
    monkeypatch.delenv('MISSING_PROBE_SESSION', raising=False)
    runtime = runner.collect_mcp_evidence(feature_config)['runtime']
    assert not runtime['available'] and runtime['error'] == 'ProbeConfigurationError'


def test_assistant_requires_tool_observations_and_exact_facts(runner, feature_config, live_mcp, monkeypatch):
    monkeypatch.setenv("AI_MODE_ENABLED", "true")
    session_context(feature_config, live_mcp, monkeypatch)
    live_mcp.backend.server.app.extensions['support_mcp_model'] = ScriptedModel([call(adapter.GET_QUEUE_SUMMARY), final()])
    result = runner.collect_mcp_evidence(feature_config)['runtime']
    assert result['assistant_verified'] and result['assistant_probes'][0]['response']['model_requests'] == 2
    response = result['assistant_probes'][0]['response']
    for replacement in ({'facts': [{'call_index': 0, 'path': 'total', 'value': 999}]}, {'observations': []},
                        {'tool_calls': 0}, {'model_requests': True}, {'model': None}):
        assert not mcp_validation.assistant_trace({**response, **replacement}, adapter.GOLDMAN_ALLOWED_TOOLS, [adapter.GET_QUEUE_SUMMARY])
    assert not mcp_validation.assistant_trace(response, adapter.GOLDMAN_ALLOWED_TOOLS, [adapter.GET_TICKET_CONTEXT])


def test_catalogue_legacy_probe_uses_same_shared_transport(runner, live_mcp, tmp_path, monkeypatch):
    config, _ = runner.load_feature('student-Chufeng')
    path = tmp_path / 'products.db'
    import_module('student-Chufeng.database.init_db').initialize_database(path, reset=True)
    server = make_server('127.0.0.1', 0, import_module('student-Chufeng.database.api').create_app(path))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    before = sha256(path.read_bytes()).hexdigest()
    try:
        monkeypatch.setenv('PRODUCT_DATABASE_API_URL', f'http://127.0.0.1:{server.server_port}/api/database')
        runtime = runner.collect_mcp_evidence(config)['runtime']
        assert runtime['available'] and runtime['required_tools_discovered'] and runtime['probe_complete'], runtime
        assert runtime['probe']['response_tool'] == 'chufeng_search_products'
        assert not runtime['all_required_tools_probed'] and not runtime['assistant_verified']
        assert sha256(path.read_bytes()).hexdigest() == before
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.parametrize('value', ['https://example.com/private', 'http://localhost:8005/?token=x',
    'http://user:secret@localhost:8005', 'http://127.0.0.1:bad/mcp', None])
def test_credentials_never_go_to_nonlocal_or_redirectable_targets(value):
    with pytest.raises(mcp_validation.ProbeConfigurationError):
        mcp_validation.local_url(value)


def test_evidence_redacts_credentials_private_fields_and_fact_values():
    evidence = {'Cookie': 'session=private-session', 'message': 'private conversation',
        'other': 'private-session person@example.com +61 412 345 678',
        'facts': [{'path': 'messages.0.message', 'value': 'private conversation'}]}
    result = json.dumps(mcp_validation.public_evidence(evidence, ['private-session']))
    assert all(value not in result for value in ('private-session', 'private conversation', 'person@example.com', '412 345'))


def test_discovery_cannot_verify_missing_probes_or_invented_application_ai(runner, feature_config, monkeypatch):
    monkeypatch.setenv('MCP_ENABLED', 'true')
    evidence = runner.collect_mcp_evidence(feature_config, runtime_probe=lambda config: {
        'available': True, 'tool_names': sorted(adapter.GOLDMAN_ALLOWED_TOOLS)})
    assert evidence['runtime']['required_tools_discovered'] and not evidence['runtime']['probe_complete']
    candidate = ' '.join(feature_config['mcp_rules']['required_tools']) + ' ' + ' '.join(feature_config['mcp_files'][:3]) + '''
    All configured MCP probes passed and all four tools executed successfully.
    The AI assistant succeeded with a model-generated answer, confirming application integration and proving
    that discovery supplied a complete demonstration. These claims use live results from the configured feature.
    '''
    issues = runner._deterministic_issues('mcp', evidence, candidate)
    assert any('probe_complete' in issue for issue in issues) and any('assistant_verified' in issue for issue in issues)


@pytest.mark.skipif(os.getenv('RUN_LIVE_MCP_AI') != '1', reason='Opt-in genuine host-model application evidence')
def test_runner_observes_real_model_selection_execution_and_answer(runner, feature_config, live_mcp, monkeypatch):
    monkeypatch.setenv("AI_MODE_ENABLED", "true")
    monkeypatch.setenv('OLLAMA_URL', 'http://127.0.0.1:11434')
    monkeypatch.setenv('MCP_ASSISTANT_MODEL', 'qwen2.5:3b')
    secret = session_context(feature_config, live_mcp, monkeypatch)
    outputs = []
    class ObservedModel(assistant.OllamaToolModel):
        async def chat(self, messages, tools, *, final=False):
            response = await super().chat(messages, tools, final=final)
            outputs.append({'final': final, 'message': response})
            return response
    live_mcp.backend.server.app.extensions['support_mcp_model'] = ObservedModel()
    before = sha256(live_mcp.database_path.read_bytes()).hexdigest()
    evidence = runner.collect_evidence('mcp', feature_config)
    runtime = evidence['runtime']
    assert runtime['probe_complete'] and runtime['all_required_tools_probed'] and runtime['assistant_verified'], runtime
    native_call = outputs[0]['message']['tool_calls'][0]['function']
    assert native_call['name'] == adapter.GET_QUEUE_SUMMARY
    response = runtime['assistant_probes'][0]['response']
    assert response['model'] == 'qwen2.5:3b' and len(outputs) == response['model_requests']
    native_answer = json.loads(outputs[-1]['message']['content'])
    assert outputs[-1]['final'] and native_answer['answer'] == response['answer']
    assert native_answer['facts'] == response['facts']
    assert secret not in json.dumps(evidence) + json.dumps(outputs)
    assert sha256(live_mcp.database_path.read_bytes()).hexdigest() == before
    Path('/tmp/asd-g5-live-mcp-validation.json').write_text(json.dumps({'evidence': evidence, 'native_model_outputs': outputs}, indent=2))


def test_runner_safely_reports_unavailable_service(runner, feature_config, monkeypatch):
    monkeypatch.setenv('MCP_ENABLED', 'true')
    monkeypatch.setenv('MCP_SERVER_URL', 'http://127.0.0.1:1/mcp')
    monkeypatch.setenv('SUPPORT_VALIDATION_SESSION', 'local-secret-value')
    feature_config['mcp_rules']['timeout_seconds'] = 0.1
    evidence = runner.collect_mcp_evidence(feature_config)
    assert evidence['runtime']['attempted'] and not evidence['runtime']['available']
    assert evidence['runtime']['error'] == 'MCPClientError'
    assert 'local-secret-value' not in runner._evidence_digest('mcp', evidence)


def test_http_probe_bounds_redirects_and_invalid_assistant_paths(runner, feature_config, monkeypatch):
    requested = []
    class Response:
        status_code = 302
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def iter_content(self, size):
            yield b'{"redirect": "http://example.com"}'
    def request(*args, **kwargs):
        requested.append(kwargs)
        return Response()
    monkeypatch.setattr(mcp_validation.requests, 'request', request)
    assert mcp_validation.read_json('POST', 'http://localhost:8005/api/support/admin/mcp/assistant',
        payload={'question': 'Queue?'}, headers={'Cookie': 'test-session'})[0] == 302
    assert requested[0]['allow_redirects'] is False and requested[0]['stream'] is True
    with pytest.raises(mcp_validation.ProbeConfigurationError):
        mcp_validation.read_json('POST', 'http://localhost:8005', payload={'text': 'x' * 4096})
    monkeypatch.setenv('AI_MODE_ENABLED', 'true')
    monkeypatch.setenv('MCP_ENABLED', 'true')
    monkeypatch.setenv('SUPPORT_VALIDATION_SESSION', 'test-session')
    monkeypatch.setattr(import_module('shared.mcp_client').MCPClient, 'list_tools', lambda *a, **k: [])
    feature_config['mcp_rules']['probes'] = []
    feature_config['mcp_rules']['assistant_probes'] = [{'url': 'http://localhost:8005/api/support/admin/tickets',
        'origin': 'http://localhost:8005', 'payload': {'question': 'Queue?'}}]
    runtime = runner.collect_mcp_evidence(feature_config)['runtime']
    assert not runtime['assistant_verified'] and not runtime['assistant_probes'][0]['attempted']
    assert len(requested) == 1  # No POST to a ticket mutation route.
    monkeypatch.setattr(Response, 'iter_content', lambda *args: iter([b'x' * (256 * 1024 + 1)]))
    with pytest.raises(ValueError, match='size limit'):
        mcp_validation.read_json('GET', 'http://localhost:8005/health')
