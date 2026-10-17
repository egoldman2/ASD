"""Deterministic same-SHA workflow/attempt/job gate and API boundary tests."""

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from cloud import check_workflows as gate

SHA = 'a' * 40


@pytest.fixture
def api():
    mapping = json.loads(gate.MAPPING.read_text())
    state = SimpleNamespace(mapping=mapping, runs=[], jobs={}, calls=[], main=SHA, detail_count={}, snapshots=0)
    for i, expected in enumerate(mapping['workflows']):
        ident = 100 + i
        state.runs.append({**expected, 'id': ident, 'workflow_id': expected['id'], 'head_sha': SHA, 'head_branch': 'main', 'event': 'push',
                           'run_attempt': 1, 'status': 'completed', 'conclusion': 'success', 'created_at': '2026-10-17T00:00:00Z',
                           'html_url': f'https://github.com/egoldman2/ASD/actions/runs/{ident}'})
        state.jobs[ident] = [{'id': ident + 1000, 'name': 'Feature tests', 'run_id': ident, 'run_attempt': 1,
                             'status': 'completed', 'conclusion': 'success',
                             'html_url': f'https://github.com/egoldman2/ASD/actions/runs/{ident}/job/{ident + 1000}'}]
    class API:
        def get(self, route, **params):
            state.calls.append((route, params))
            if route.endswith('/git/ref/heads/main'):
                return {'object': {'sha': state.main}}
            ident = int(route.rsplit('/', 1)[1])
            state.detail_count[ident] = state.detail_count.get(ident, 0) + 1
            return deepcopy(next(row for row in state.runs if row['id'] == ident))
        def pages(self, route, key, **params):
            state.calls.append((route, params))
            if key == 'workflow_runs':
                state.snapshots += 1
                assert params == {'head_sha': SHA, 'branch': 'main', 'event': 'push'}
                return deepcopy(state.runs)
            parts = route.split('/')
            ident = int(parts[parts.index('runs') + 1])
            attempt = int(parts[parts.index('attempts') + 1])
            assert all(row['run_attempt'] == attempt for row in state.jobs[ident])
            return deepcopy(state.jobs[ident])
    state.api = API()
    return state


def test_five_same_sha_main_runs_and_every_job_pass(api):
    report = gate.check(api.api, api.mapping, SHA, timeout=0)
    assert report['status'] == 'passed' and not report['issues'] and len(report['workflows']) == 5
    assert all(row['jobs'][0]['conclusion'] == 'success' for row in report['workflows'])


@pytest.mark.parametrize('field,value', [('head_sha', 'b' * 40), ('head_branch', 'ethan-goldman'), ('event', 'pull_request'), ('path', '.github/workflows/wrong.yml')])
def test_wrong_sha_branch_event_or_path_cannot_substitute_for_main(api, field, value):
    api.runs[0][field] = value
    assert gate.check(api.api, api.mapping, SHA, timeout=0)['status'] == 'failed'


@pytest.mark.parametrize('conclusion', ['failure', 'cancelled', 'skipped', 'neutral', 'timed_out'])
def test_failed_or_skipped_workflow_cannot_pass(api, conclusion):
    api.runs[0]['conclusion'] = conclusion
    assert gate.check(api.api, api.mapping, SHA, timeout=0)['status'] == 'failed'


@pytest.mark.parametrize('fault', ['missing', 'pending', 'no_jobs', 'skipped_job', 'pending_job', 'wrong_job_run'])
def test_missing_pending_or_bad_jobs_are_not_passing_evidence(api, fault):
    if fault == 'missing':
        api.runs.pop(0)
    elif fault == 'pending':
        api.runs[0].update(status='in_progress', conclusion=None)
    elif fault == 'no_jobs':
        api.jobs[100] = []
    elif fault == 'skipped_job':
        api.jobs[100][0]['conclusion'] = 'skipped'
    elif fault == 'pending_job':
        api.jobs[100][0].update(status='queued', conclusion=None)
    else:
        api.jobs[100][0]['run_id'] = 999
    report = gate.check(api.api, api.mapping, SHA, timeout=0)
    assert report['status'] == ('timed_out' if fault in {'missing', 'pending', 'pending_job'} else 'failed')


def test_latest_failed_rerun_cannot_reuse_old_successful_jobs(api):
    api.runs[0].update(run_attempt=2, conclusion='failure')
    report = gate.check(api.api, api.mapping, SHA, timeout=0)
    assert report['status'] == 'failed' and report['workflows'][0]['run_attempt'] == 2
    assert not any('/runs/100/attempts/1/jobs' in route for route, _ in api.calls)


def test_newer_failed_run_cannot_fall_back_to_older_green(api):
    newer = {**api.runs[0], 'id': 999, 'created_at': '2026-10-17T00:01:00Z', 'conclusion': 'failure',
             'html_url': 'https://github.com/egoldman2/ASD/actions/runs/999'}
    api.runs.append(newer)
    report = gate.check(api.api, api.mapping, SHA, timeout=0)
    assert report['status'] == 'failed' and report['workflows'][0]['id'] == 999


def test_attempt_change_during_job_capture_requires_new_observation(api):
    original = api.api.get
    def get(route, **params):
        row = original(route, **params)
        if route.endswith('/actions/runs/100') and api.detail_count[100] == 2:
            row.update(run_attempt=2, status='in_progress', conclusion=None)
        return row
    api.api.get = get
    report = gate.check(api.api, api.mapping, SHA, timeout=0)
    assert report['status'] == 'timed_out' and 'rerun_changed:100' in report['issues']


def test_pending_runs_can_complete_inside_bounded_poll(api):
    original = api.api.get
    def get(route, **params):
        row = original(route, **params)
        if route.endswith('/actions/runs/100') and api.snapshots == 1:
            row.update(status='in_progress', conclusion=None)
        return row
    api.api.get = get
    slept = []
    report = gate.check(api.api, api.mapping, SHA, timeout=30, clock=lambda: 0, sleep=slept.append)
    assert report['status'] == 'passed' and api.snapshots == 2 and slept == [15]


@pytest.mark.parametrize('when', ['before', 'after'])
def test_superseded_main_candidate_never_grants_current_output(api, when):
    if when == 'before':
        api.main = 'b' * 40
    else:
        original = api.api.pages
        def pages(*args, **kwargs):
            result = original(*args, **kwargs)
            api.main = 'b' * 40
            return result
        api.api.pages = pages
    report = gate.check(api.api, api.mapping, SHA, timeout=0)
    assert report['status'] == 'superseded'


def test_api_errors_fail_closed_without_retaining_private_exception_text(api):
    def error(*args, **kwargs):
        raise gate.APIError('private-token-error-text')
    api.api.pages = error
    report = gate.check(api.api, api.mapping, SHA, timeout=0)
    assert report['status'] == 'failed' and 'private-token' not in json.dumps(report)


def test_runs_and_jobs_paginate_and_overflow_fails_closed(monkeypatch):
    monkeypatch.setattr(gate, 'PAGE_SIZE', 2)
    api = gate.GitHub()
    calls = []
    def get(route, **params):
        calls.append(params['page'])
        return {'total_count': 3, 'jobs': [{'id': 1}, {'id': 2}] if params['page'] == 1 else [{'id': 3}]}
    api.get = get
    assert api.pages(gate.PREFIX + '/actions/runs/1/attempts/1/jobs', 'jobs') == [{'id': 1}, {'id': 2}, {'id': 3}]
    assert calls == [1, 2]
    api.get = lambda *a, **k: {'total_count': 1001, 'jobs': []}
    with pytest.raises(gate.APIError):
        api.pages(gate.PREFIX + '/actions/runs', 'jobs')


@pytest.mark.parametrize('rows,total', [([{'id': 1}], 2), ([{'id': 1}, {'id': 1}], 2), ([], -1)])
def test_partial_or_duplicate_job_pages_cannot_hide_failed_jobs(rows, total):
    api = gate.GitHub()
    api.get = lambda *a, **k: {'total_count': total, 'jobs': rows}
    with pytest.raises(gate.APIError):
        api.pages(gate.PREFIX + '/actions/runs/1/attempts/1/jobs', 'jobs')


@pytest.mark.parametrize('fault', ['redirect', 'size', 'invalid_json', 'outside_origin'])
def test_http_api_boundaries_never_follow_redirects_or_save_payloads(fault):
    from urllib.error import HTTPError
    api = gate.GitHub('synthetic-fixture-token')
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def read(self, size):
            return b'x' * size if fault == 'size' else b'not json'
    class Opener:
        def open(self, request, **kwargs):
            assert request.full_url.startswith('https://api.github.com/repos/egoldman2/ASD/')
            assert 0 < kwargs['timeout'] <= 15
            if fault == 'redirect':
                raise HTTPError(request.full_url, 302, 'private-response', {}, None)
            return Response()
    api.opener = Opener()
    route = 'https://outside.example' if fault == 'outside_origin' else gate.PREFIX + '/git/ref/heads/main'
    with pytest.raises(gate.APIError) as error:
        api.get(route)
    assert 'private-response' not in str(error.value) and api.token not in str(error.value)


def test_cli_failure_and_superseded_outputs_are_explicit(api, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(gate, 'GitHub', lambda _: api.api)
    monkeypatch.setenv('GITHUB_REPOSITORY', gate.REPOSITORY)
    output = tmp_path / 'outputs'
    monkeypatch.setenv('GITHUB_OUTPUT', str(output))
    api.main = 'b' * 40
    report = tmp_path / 'gate.json'
    assert gate.main(['--sha', SHA, '--head-only', '--report', str(report)]) == 0
    assert output.read_text() == 'current=false\n'
    assert json.loads(report.read_text())['status'] == 'superseded'
    monkeypatch.setenv('GITHUB_REPOSITORY', 'other/repo')
    assert gate.main(['--sha', SHA, '--report', str(report)]) == 1
    assert 'failed' in capsys.readouterr().out
