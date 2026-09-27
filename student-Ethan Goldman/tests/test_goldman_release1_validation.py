"""Persistent Release 1 configuration, genuine services and actual CLI acceptance."""

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

from test_goldman_agentic_review import load_agentic_loop
from test_goldman_mcp_assistant import ScriptedModel, call, final, assistant, adapter
from test_agentic_rag_validation import rag_host

ROOT = Path(__file__).parents[2]


def configured_runtime(stack, monkeypatch):
    secret = stack.admin().cookies.get('ethan_session')
    monkeypatch.setenv('SUPPORT_VALIDATION_SESSION', secret)
    monkeypatch.setenv('SUPPORT_VALIDATION_ASSISTANT_URL', stack.backend.url + '/api/support/admin/mcp/assistant')
    monkeypatch.setenv('AI_MODE_ENABLED', 'true'); monkeypatch.setenv('MCP_ENABLED', 'true')
    return secret


def test_persistent_registration_has_named_tools_examples_and_safe_context(monkeypatch):
    for flag in ('AI_MODE_ENABLED', 'MCP_ENABLED', 'RAG_ENABLED'):
        monkeypatch.setenv(flag, 'false')
    runner = load_agentic_loop('goldman_release1_registration')
    config, _ = runner.load_feature('student-Ethan Goldman')
    rules = config['mcp_rules']
    assert set(rules['required_tools']) == adapter.GOLDMAN_ALLOWED_TOOLS
    assert {probe['tool'] for probe in rules['probes']} == adapter.GOLDMAN_ALLOWED_TOOLS
    assert {probe['expected_tools'][0] for probe in rules['assistant_probes']} == adapter.GOLDMAN_ALLOWED_TOOLS
    assert len(rules['assistant_probes']) == 4 and rules['request_context']['cookie_env'] == 'SUPPORT_VALIDATION_SESSION'
    assert rules['assistant_url_env'] == 'SUPPORT_VALIDATION_ASSISTANT_URL'
    assert {probe['expected'] for probe in config['rag_rules']['probes']} == {'grounded', 'insufficient'}
    for mode in ('mcp', 'rag'):
        evidence = runner.collect_evidence(mode, config)
        assert not evidence['runtime']['attempted'] and all(evidence['verified_checks']['source_checks'].values())
        assert evidence['verified_checks']['present_files'] == evidence['verified_checks']['configured_files']
    assert 'CI must not start host AI' in config['mode_prompts']['devops']
    assert 'real Qwen/Ollama execution' not in config['mode_prompts']['devops']


def test_persistent_probes_execute_genuine_reads_and_validate_all_examples(live_mcp, rag_host, monkeypatch):
    runner = load_agentic_loop('goldman_release1_real_services')
    config, _ = runner.load_feature('student-Ethan Goldman')
    secret = configured_runtime(live_mcp, monkeypatch)
    model = ScriptedModel([
        call(adapter.SEARCH_TICKETS, {'category': 'delivery', 'assigned_to': 'unassigned'}),
        final(answer='There are 0 unassigned delivery tickets.', path='total', value=0),
        call(adapter.GET_TICKET_CONTEXT, {'ticket_id': 2002}),
        final(answer='Ticket 2002 is recorded.', ticket_ids=[2002], path='id', value=2002),
        call(adapter.GET_QUEUE_SUMMARY), final(),
        call(adapter.GET_TICKETS_NEEDING_ATTENTION), final(answer='There are 9 tickets needing attention.', value=9),
    ])
    live_mcp.backend.server.app.extensions['support_mcp_model'] = model
    before = sha256(live_mcp.database_path.read_bytes()).hexdigest()
    mcp_evidence = runner.collect_evidence('mcp', config)
    mcp = mcp_evidence['runtime']
    assert mcp['probe_complete'] and mcp['all_required_tools_probed'] and mcp['assistant_verified'], mcp
    assert len(mcp['assistant_probes']) == 4 and len(model.requests) == 8
    compact = runner._runtime_review_summary('mcp', mcp)
    assert len(compact['assistant_probes']) == 4
    assert all(probe['verified'] for probe in compact['assistant_probes'])
    assert all(probe['response']['facts'] for probe in compact['assistant_probes'])
    assert all(probe['response']['facts'] for probe in mcp['assistant_probes'])
    assert len(runner._grounding_summary('mcp', mcp_evidence)) < 700
    assert 'assistant_probes' in runner._evidence_digest('mcp', mcp_evidence)
    rag = runner.collect_evidence('rag', config)['runtime']
    assert rag['validation_complete'], rag
    assert secret not in json.dumps({'mcp': mcp, 'rag': rag})
    assert sha256(live_mcp.database_path.read_bytes()).hexdigest() == before


def test_assistant_url_override_is_local_and_never_changes_model_arguments(live_mcp, monkeypatch):
    runner = load_agentic_loop('goldman_release1_override')
    config, _ = runner.load_feature('student-Ethan Goldman')
    configured_runtime(live_mcp, monkeypatch)
    monkeypatch.setenv('SUPPORT_VALIDATION_ASSISTANT_URL', 'https://example.com/api/support/admin/mcp/assistant')
    model = ScriptedModel([])
    live_mcp.backend.server.app.extensions['support_mcp_model'] = model
    runtime = runner.collect_evidence('mcp', config)['runtime']
    assert runtime['probe_complete'] and not runtime['assistant_verified']
    assert all(probe['error'] == 'ProbeConfigurationError' and not probe['attempted'] for probe in runtime['assistant_probes'])
    assert model.requests == []


@pytest.mark.skipif(os.getenv('RUN_LIVE_RELEASE1_VALIDATION') != '1', reason='Opt-in actual CLI/model/protocol acceptance')
def test_actual_cli_modes_record_four_native_mcp_examples_and_grounded_rag(live_mcp, rag_host, monkeypatch):
    runner = load_agentic_loop('goldman_release1_live_cli')
    config, _ = runner.load_feature('student-Ethan Goldman')
    secret = configured_runtime(live_mcp, monkeypatch)
    monkeypatch.setenv('RAG_ENABLED', 'true'); monkeypatch.setenv('OLLAMA_MODEL', 'qwen2.5:3b')
    monkeypatch.setenv('OLLAMA_URL', 'http://127.0.0.1:11434'); monkeypatch.setenv('MCP_ASSISTANT_MODEL', 'qwen2.5:3b')
    native_mcp, native_rag = [], []
    class ObservedSupportModel(assistant.OllamaToolModel):
        async def chat(self, messages, tools, *, final=False):
            result = await super().chat(messages, tools, final=final)
            event = {'question': messages[1]['content'], 'final': final, 'tool_calls': result.get('tool_calls', [])}
            if result.get('content'):
                try:
                    event['generated'] = json.loads(result['content'])
                except ValueError:
                    event['draft'] = result['content']
            native_mcp.append(event)
            return result
    live_mcp.backend.server.app.extensions['support_mcp_model'] = ObservedSupportModel()
    model_type = rag_host['ollama_type']
    class ObservedKnowledgeModel(model_type):
        def generate_answer(self, system, user, **kwargs):
            result = super().generate_answer(system, user, **kwargs)
            native_rag.append({'system': system, 'user': user, 'answer': result.content, 'model': result.model})
            return result
    rag_host['set_model'](ObservedKnowledgeModel(settings=rag_host['settings']))
    before = sha256(live_mcp.database_path.read_bytes()).hexdigest()
    paths, evidence = {}, {}
    for mode in ('mcp', 'rag'):
        result = subprocess.run([sys.executable, str(ROOT / 'ai-services/agentic_loop.py'),
            '--feature', 'student-Ethan Goldman', '--mode', mode], cwd=ROOT, capture_output=True, text=True, timeout=420)
        Path(f'/tmp/asd-e6-{mode}-cli.txt').write_text(result.stdout + '\n' + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
        match = re.search(r'Evidence saved to (.+)', result.stdout)
        assert match, result.stdout
        path = Path(match.group(1).strip()); paths[mode] = str(path)
        text = path.read_text()
        assert secret not in text and all(f'[{stage}]' in result.stdout for stage in ('PLAN', 'ACT', 'OBSERVE', 'ADAPT', 'DONE'))
        payload = json.loads(re.search(r'```json\n(.*?)\n```', text, re.S).group(1))
        evidence[mode] = payload
        runtime = payload['runtime']
        assert runtime['assistant_verified'] if mode == 'mcp' else runtime['validation_complete'], runtime
    mcp_probes = evidence['mcp']['runtime']['assistant_probes']
    assert len(mcp_probes) == 4
    for configured, observed in zip(config['mcp_rules']['assistant_probes'], mcp_probes):
        question = configured['payload']['question']
        events = [event for event in native_mcp if event['question'].startswith(question)]
        called = {call['function']['name'] for event in events for call in event['tool_calls']}
        assert set(configured['expected_tools']).issubset(called)
        final_output = events[-1]['generated']
        assert final_output['answer'] == observed['response']['answer']
    assert native_rag and native_rag[-1]['model'] == 'qwen2.5:3b'
    assert native_rag[-1]['answer'].strip() == evidence['rag']['runtime']['probes'][0]['answer']['data']['answer']
    assert not evidence['rag']['runtime']['probes'][1]['answer']['metadata']['model_invoked']
    assert sha256(live_mcp.database_path.read_bytes()).hexdigest() == before
    assert secret not in json.dumps(native_mcp) + json.dumps(native_rag)
    Path('/tmp/asd-e6-live-cli-traces.json').write_text(json.dumps({'paths': paths, 'mcp': native_mcp, 'rag': native_rag}, indent=2))
