"""Staff fragments exercise real support/auth/database/MCP transport."""

from hashlib import sha256
from importlib import import_module
import json
import os
from pathlib import Path
import sqlite3

import pytest
import requests

assistant = import_module('student-Ethan Goldman.support_backend.mcp_assistant')
adapter = import_module('student-Ethan Goldman.support_backend.mcp_client')
from test_goldman_mcp_assistant import ScriptedModel, call, final


@pytest.fixture(autouse=True)
def enable_ui_flags(monkeypatch):
    monkeypatch.setenv('AI_MODE_ENABLED', 'true')
    monkeypatch.setenv('MCP_ENABLED', 'true')


def post(stack, session, suffix, data):
    return session.post(stack.backend.url + '/api/support/ui/admin/mcp/' + suffix,
                        data=data, headers=stack.htmx_headers, timeout=95)


def test_all_direct_ui_actions_and_pagination_use_real_mcp(live_mcp):
    stack, admin = live_mcp, live_mcp.admin()
    before = sha256(stack.database_path.read_bytes()).hexdigest()
    for action, data, expected in (
        ('search', {'category': 'delivery', 'assigned_to': 'unassigned'}, 'Matching tickets'),
        ('context', {'ticket_id': '2002', 'message_limit': '1'}, 'Ticket #2002'),
        ('summary', {}, 'Unresolved and unassigned'),
        ('attention', {'inactive_hours': '48', 'limit': '1'}, 'Inactivity threshold: 48 hours'),
    ):
        response = post(stack, admin, 'tools/' + action, data)
        assert response.status_code == 200, response.text
        assert expected in response.text
        if action == 'context':
            assert 'Only the latest 1 messages were read' in response.text
        if action == 'attention':
            assert 'More results are available' in response.text and 'Unassigned' in response.text
    page = post(stack, admin, 'tools/search', {'limit': '1'})
    assert '1 of 12 tickets displayed' in page.text and 'offset 1 for the next page' in page.text
    assert 'staff-ticket.html?ticket=' in page.text
    empty = post(stack, admin, 'tools/search', {'search': 'does-not-match-any-seeded-ticket'})
    assert empty.status_code == 200 and 'No matching tickets' in empty.text
    assert sha256(stack.database_path.read_bytes()).hexdigest() == before


def test_mcp_ui_access_validation_escaping_and_disabled_transport(live_mcp, monkeypatch):
    stack, admin = live_mcp, live_mcp.admin()
    assert post(stack, requests.Session(), 'tools/summary', {}).status_code == 401
    assert post(stack, stack.customer(), 'tools/summary', {}).status_code == 403
    for action, data in (('search', {'ethan_session': 'forged'}), ('search', {'ethan_session': ''}), ('context', {'ticket_id': '-1'}),
                         ('search', {'limit': '1.5'}), ('search', {'limit': '51'}), ('unknown', {})):
        assert post(stack, admin, 'tools/' + action, data).status_code in (400, 403)
    assert post(stack, admin, 'tools/search', [('limit', '1'), ('limit', '2')]).status_code == 400
    assert post(stack, admin, 'tools/search', {'search': 'x' * 5000}).status_code == 413
    with sqlite3.connect(stack.database_path) as db:
        db.execute('UPDATE support_tickets SET subject=? WHERE id=2002', ('<script>alert(1)</script>',))
    escaped = post(stack, admin, 'tools/context', {'ticket_id': '2002'})
    assert escaped.status_code == 200 and '&lt;script&gt;' in escaped.text and '<script>' not in escaped.text
    monkeypatch.setenv('MCP_ENABLED', 'false')
    stack.backend.server.app.extensions.pop('support_mcp_client', None)
    disabled = post(stack, admin, 'tools/summary', {})
    assert disabled.status_code == 503 and 'disabled' in disabled.text.lower()
    assert admin.get(stack.backend.url + '/api/support/ui/admin/tickets', timeout=10).status_code == 200


def test_assistant_ui_answer_evidence_and_safe_failure_states(live_mcp, monkeypatch):
    stack, admin = live_mcp, live_mcp.admin()
    model = ScriptedModel([call(adapter.GET_QUEUE_SUMMARY), final(answer='<img src=x onerror=alert(1)> There are 12 tickets.')])
    stack.backend.server.app.extensions['support_mcp_model'] = model
    response = post(stack, admin, 'assistant', {'question': 'Queue workload?'})
    assert response.status_code == 200 and 'Assistant answer' in response.text
    assert '&lt;img' in response.text and '<img' not in response.text
    assert 'Data used: Summary' in response.text and 'Verified fact references' in response.text
    assert 'Total tickets' in response.text and 'ethan_session' not in response.text
    for data in ({'question': ''}, {'question': 'Queue?', 'scope': 'other'}, {'question': 'Queue?', 'scope': ''}, {'question': 'Queue?', 'ticket_id': '0'}):
        assert post(stack, admin, 'assistant', data).status_code == 400
    assert post(stack, admin, 'assistant', {'question': 'x' * 5000}).status_code == 413
    broken = ScriptedModel([call(adapter.GET_QUEUE_SUMMARY), final(value=999), final(value=998)])
    stack.backend.server.app.extensions['support_mcp_model'] = broken
    partial = post(stack, admin, 'assistant', {'question': 'Queue?'})
    assert partial.status_code == 502 and 'Partial' in partial.text and 'Data used: Summary' in partial.text
    assert 'Assistant answer' not in partial.text and 'could not be verified' in partial.text
    clarification = ScriptedModel([{'content': json.dumps({'answer': 'Which ticket should I read?',
        'ticket_ids': [], 'facts': [], 'needs_clarification': True})}])
    stack.backend.server.app.extensions['support_mcp_model'] = clarification
    response = post(stack, admin, 'assistant', {'question': 'What is its state?'})
    assert response.status_code == 200 and 'More information needed' in response.text
    monkeypatch.setenv('AI_MODE_ENABLED', 'false')
    disabled = post(stack, admin, 'assistant', {'question': 'Queue?'})
    assert disabled.status_code == 503 and 'must both be enabled' in disabled.text


@pytest.mark.skipif(os.getenv('RUN_LIVE_MCP_AI') != '1', reason='Opt-in actual model with all four staff fragment questions')
def test_live_staff_questions_use_each_actual_model_selected_tool(live_mcp, monkeypatch):
    monkeypatch.setenv('OLLAMA_URL', 'http://127.0.0.1:11434')
    monkeypatch.setenv('MCP_ASSISTANT_MODEL', os.getenv('MCP_ASSISTANT_MODEL', 'qwen2.5:3b'))
    stack, admin = live_mcp, live_mcp.admin()
    traces = []
    class ObservedModel(assistant.OllamaToolModel):
        async def chat(self, messages, tools, *, final=False):
            result = await super().chat(messages, tools, final=final)
            traces[-1]['model_outputs'].append(result)
            return result
    stack.backend.server.app.extensions['support_mcp_model'] = ObservedModel()
    before = sha256(stack.database_path.read_bytes()).hexdigest()
    for question, name, data in (
        ('Find unassigned delivery tickets.', adapter.SEARCH_TICKETS, {}),
        ('Summarise the conversation and current state of ticket 2002.', adapter.GET_TICKET_CONTEXT, {'ticket_id': '2002'}),
        ('How does our support workload look?', adapter.GET_QUEUE_SUMMARY, {}),
        ('Which tickets need attention, and why?', adapter.GET_TICKETS_NEEDING_ATTENTION, {}),
    ):
        traces.append({'question': question, 'expected_tool': name, 'model_outputs': []})
        response = post(stack, admin, 'assistant', {'question': question, **data})
        traces[-1].update(status=response.status_code, fragment=response.text)
        Path('/tmp/asd-support-mcp-ui-live.json').write_text(json.dumps(traces, indent=2))
        assert response.status_code == 200 and 'Assistant answer' in response.text, response.text
        names = [c['function']['name'] for output in traces[-1]['model_outputs'] for c in output.get('tool_calls', [])]
        assert name in names and 'Data used:' in response.text and 'Verified fact references' in response.text
        if name == adapter.GET_TICKETS_NEEDING_ATTENTION:
            assert '9 of 9 tickets displayed' in response.text and 'Applied filters:' not in response.text
    assert sha256(stack.database_path.read_bytes()).hexdigest() == before
