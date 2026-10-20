"""Exercise runner admission against native identities, not workflow-supplied labels."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cloud import codebuild_runner as runner

SHA = 'a' * 40


@pytest.fixture
def admission():
    expected = {'source_sha': SHA, 'run_id': 42, 'run_attempt': 2, 'job_id': 99,
                'event': 'push', 'runner_id': 17, 'runner_name': 'asd-deploy-fixture'}
    run = {'head_sha': SHA, 'head_branch': 'main', 'path': runner.WORKFLOW,
           'event': 'push', 'id': 42, 'run_attempt': 2}
    job = {'id': 99, 'run_id': 42, 'run_attempt': 2, 'name': 'deploy',
           'status': 'in_progress', 'runner_id': 17, 'runner_name': 'asd-deploy-fixture'}
    environment = {'GITHUB_REPOSITORY': runner.REPOSITORY, 'GITHUB_REF': 'refs/heads/main',
                   'GITHUB_SHA': SHA, 'GITHUB_RUN_ID': '42', 'GITHUB_RUN_ATTEMPT': '2',
                   'GITHUB_JOB': 'deploy', 'GITHUB_EVENT_NAME': 'push'}
    head = {'object': {'sha': SHA}}
    documents = {runner.PREFIX + '/actions/runs/42': run,
                 runner.PREFIX + '/actions/jobs/99': job,
                 runner.PREFIX + '/git/ref/heads/main': head}
    api = SimpleNamespace(get=documents.__getitem__)
    return SimpleNamespace(expected=expected, run=run, job=job, head=head,
                           environment=environment, api=api)


def test_exact_main_job_is_admitted(admission):
    runner.authorize_job(admission.api, admission.expected, admission.environment)


@pytest.mark.parametrize('field,value', [
    ('GITHUB_REPOSITORY', 'outsider/fork'), ('GITHUB_REF', 'refs/heads/ethan-goldman'),
    ('GITHUB_SHA', 'b' * 40), ('GITHUB_RUN_ID', '43'), ('GITHUB_RUN_ATTEMPT', '1'),
    ('GITHUB_JOB', 'test'), ('GITHUB_EVENT_NAME', 'pull_request'),
])
def test_nonmain_context_is_refused_before_any_api_call(admission, field, value):
    admission.environment[field] = value
    admission.api.get = lambda *_: pytest.fail('A rejected context contacted GitHub')
    with pytest.raises(RuntimeError, match='unexpected workflow context'):
        runner.authorize_job(admission.api, admission.expected, admission.environment)


@pytest.mark.parametrize('target,field,value', [
    ('run', 'head_sha', 'b' * 40), ('run', 'head_branch', 'ethan-goldman'),
    ('run', 'path', '.github/workflows/untrusted.yml'), ('run', 'event', 'pull_request'),
    ('run', 'run_attempt', 3), ('job', 'id', 100), ('job', 'run_id', 43),
    ('job', 'run_attempt', 1), ('job', 'name', 'test'), ('job', 'status', 'queued'),
    ('job', 'runner_id', 18), ('job', 'runner_name', 'different-runner'),
])
def test_spoofed_context_cannot_bypass_native_assignment(admission, target, field, value):
    getattr(admission, target)[field] = value
    with pytest.raises(RuntimeError, match='not assigned'):
        runner.authorize_job(admission.api, admission.expected, admission.environment)


def test_superseded_main_is_refused(admission):
    admission.head['object']['sha'] = 'b' * 40
    with pytest.raises(RuntimeError, match='not assigned'):
        runner.authorize_job(admission.api, admission.expected, admission.environment)


@pytest.fixture
def candidate(admission, monkeypatch):
    admission.job.update(status='queued', labels=['asd-main-42-2'])
    others = [{'id': number, 'name': f'validate ({number})', 'status': 'completed',
               'conclusion': 'success'} for number in range(1, 10)]
    admission.jobs = [*others, admission.job]
    admission.run.update(status='in_progress', created_at='2026-10-20T00:00:00Z')

    def pages(_route, key, **_params):
        return [admission.run] if key == 'workflow_runs' else admission.jobs

    admission.api.pages = pages
    monkeypatch.setattr(runner, 'check', lambda *_args, **_kwargs: {'status': 'passed'})
    return admission


def test_registration_waits_for_all_prerequisites_and_the_unique_label(candidate):
    expected = runner.wait_for_job(candidate.api, SHA, timeout=5)
    assert expected == {'source_sha': SHA, 'run_id': 42, 'run_attempt': 2,
                        'job_id': 99, 'event': 'push', 'label': 'asd-main-42-2'}


def test_failed_prerequisite_never_registers_a_runner(candidate):
    candidate.jobs[0]['conclusion'] = 'failure'
    with pytest.raises(RuntimeError, match='prerequisites failed'):
        runner.wait_for_job(candidate.api, SHA, timeout=5)


def test_latest_failed_student_gate_is_not_ignored(candidate, monkeypatch):
    monkeypatch.setattr(runner, 'check', lambda *_args, **_kwargs: {'status': 'failed'})
    with pytest.raises(RuntimeError, match='exact-main student'):
        runner.wait_for_job(candidate.api, SHA, timeout=5)


def test_superseded_queued_job_can_be_rejected_without_stalling_new_main(candidate, monkeypatch):
    monkeypatch.setattr(runner, 'check', lambda *_args, **_kwargs: {'status': 'superseded'})
    candidate.head['object']['sha'] = 'b' * 40
    expected = runner.wait_for_job(candidate.api, SHA, timeout=5)
    assert expected['job_id'] == candidate.expected['job_id']
    with pytest.raises(RuntimeError, match='not assigned'):
        runner.authorize_job(candidate.api, candidate.expected, candidate.environment)


def test_other_labels_cannot_request_a_privileged_runner(candidate, monkeypatch):
    candidate.job['labels'] = ['self-hosted']
    candidate.run['status'] = 'completed'
    monkeypatch.setattr(runner, 'check', lambda *_args, **_kwargs: pytest.fail('Unexpected label reached the gate'))
    with pytest.raises(RuntimeError, match='finished before requesting'):
        runner.wait_for_job(candidate.api, SHA, timeout=5)


def test_source_credential_failure_does_not_print_the_token(monkeypatch, capsys):
    monkeypatch.setattr(runner.subprocess, 'run', lambda *_args, **_kwargs: SimpleNamespace(
        returncode=1, stdout='password=fixture-private-token\n', stderr='fixture-private-token'))
    with pytest.raises(RuntimeError) as error:
        runner.source_token()
    assert 'fixture-private-token' not in str(error.value) + capsys.readouterr().out


def test_hook_uses_isolated_python_and_fixed_admission_code():
    script = (Path(runner.__file__).with_name('codebuild_runner_hook.sh')).read_text()
    assert 'exec /usr/bin/python3 -I "$script_dir/codebuild_runner.py" guard' in script


def test_guard_removes_its_private_credential_before_steps(admission, monkeypatch, tmp_path):
    path = tmp_path / 'runner-expected.json'
    path.write_text(json.dumps({**admission.expected, 'token': 'fixture-private-token'}))
    monkeypatch.setattr(runner, 'EXPECTED', path)
    monkeypatch.setattr(runner, 'GitHub', lambda _token: admission.api)
    monkeypatch.setattr(runner.sys, 'argv', ['runner', 'guard'])
    for key, value in admission.environment.items():
        monkeypatch.setenv(key, value)
    runner.main()
    assert not path.exists()


def test_bad_runner_archive_is_never_extracted(monkeypatch, tmp_path):
    from io import BytesIO
    monkeypatch.setattr(runner, 'urlopen', lambda *_args, **_kwargs: BytesIO(b'invalid runner archive'))
    with pytest.raises(RuntimeError, match='digest mismatch'):
        runner.download_runner(tmp_path)
    assert list(tmp_path.iterdir()) == [tmp_path / 'runner.tar.gz']


@pytest.mark.parametrize('values', [
    {},
    {'CODEBUILD_RESOLVED_SOURCE_VERSION': 'not-a-sha'},
    {'CODEBUILD_RESOLVED_SOURCE_VERSION': SHA, 'CODEBUILD_SOURCE_VERSION': 'ethan-goldman'},
    {'CODEBUILD_RESOLVED_SOURCE_VERSION': SHA, 'CODEBUILD_SOURCE_VERSION': 'main',
     'CODEBUILD_BUILD_ID': 'fixture:build', 'CODEBUILD_WEBHOOK_HEAD_REF': 'refs/heads/ethan-goldman'},
    {'CODEBUILD_RESOLVED_SOURCE_VERSION': SHA, 'CODEBUILD_SOURCE_VERSION': SHA,
     'CODEBUILD_BUILD_ID': 'fixture:build', 'CODEBUILD_WEBHOOK_HEAD_REF': 'refs/heads/main',
     'CODEBUILD_WEBHOOK_EVENT': 'PULL_REQUEST_CREATED'},
])
def test_nonmain_build_cannot_obtain_a_source_credential(monkeypatch, values):
    for key in ('CODEBUILD_RESOLVED_SOURCE_VERSION', 'CODEBUILD_SOURCE_VERSION', 'CODEBUILD_BUILD_ID',
                'CODEBUILD_WEBHOOK_HEAD_REF', 'CODEBUILD_WEBHOOK_EVENT'):
        monkeypatch.delenv(key, raising=False)
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(runner, 'source_token', lambda: pytest.fail('Untrusted source obtained credentials'))
    with pytest.raises(RuntimeError, match='main CodeBuild source'):
        runner.run()


@pytest.mark.parametrize('job_conclusion', ['success', 'failure'])
def test_ephemeral_runner_uses_private_admission_and_always_cleans_up(monkeypatch, tmp_path, job_conclusion):
    private = tmp_path / 'private/expected.json'
    monkeypatch.setattr(runner, 'EXPECTED', private)
    for key, value in {'CODEBUILD_RESOLVED_SOURCE_VERSION': SHA, 'CODEBUILD_SOURCE_VERSION': 'main',
                       'CODEBUILD_BUILD_ID': 'fixture:unique-build'}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv('CODEBUILD_WEBHOOK_HEAD_REF', raising=False)
    monkeypatch.setattr(runner.subprocess, 'check_output', lambda *_args, **_kwargs: SHA)
    monkeypatch.setattr(runner, 'source_token', lambda: 'fixture-private-token')
    monkeypatch.setattr(runner, 'wait_for_job', lambda *_: {
        'source_sha': SHA, 'run_id': 42, 'run_attempt': 2, 'job_id': 99,
        'event': 'push', 'label': 'asd-main-42-2'})
    monkeypatch.setattr(runner, 'GitHub', lambda token: SimpleNamespace(token=token, get=lambda _: {
        'status': 'completed', 'conclusion': job_conclusion, 'runner_id': 17}))
    monkeypatch.setattr(runner, 'download_runner', lambda _: None)
    operations = []

    def api(_api, method, suffix):
        operations.append((method, suffix))
        return {'token': 'fixture-registration-token'}

    def execute(command, *, cwd, env, **_kwargs):
        if command[0].endswith('/config.sh'):
            assert '--ephemeral' in command and '--disableupdate' in command and '--no-default-labels' in command
            assert command[-1] == 'asd-main-42-2'
            (cwd / '.runner').write_text(json.dumps({'agentId': 17}))
        else:
            assert command == [str(cwd / 'run.sh')]
            assert private.stat().st_mode & 0o777 == 0o600
            assert json.loads(private.read_text())['runner_id'] == 17
            assert env['ACTIONS_RUNNER_HOOK_JOB_STARTED'] == str(runner.ROOT / 'cloud/codebuild_runner_hook.sh')
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner, 'runner_api', api)
    monkeypatch.setattr(runner.subprocess, 'run', execute)
    if job_conclusion == 'success':
        runner.run()
    else:
        with pytest.raises(RuntimeError, match='did not succeed'):
            runner.run()
    assert not private.exists()
    assert operations == [('POST', 'registration-token'), ('DELETE', '17')]
