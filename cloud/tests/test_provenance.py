"""Release identity, runtime and failure evidence checks without AWS mutation."""

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from cloud import deploy, provenance

SHA = 'a' * 40
DIGEST = 'b' * 64
INSTANCE = 'i-' + 'c' * 17
COMMAND = '12345678-1234-1234-1234-123456789abc'


@pytest.fixture
def release(tmp_path):
    directory = tmp_path / 'release'
    directory.mkdir()
    identity = {'source_sha': SHA, 'source_sha256': DIGEST, 'release_id': SHA + '-1',
                'target_instance': INSTANCE, 'region': 'ap-southeast-2', 'public_url': 'https://fixture.cloudfront.net'}
    (directory / 'source-metadata.json').write_text(json.dumps(identity))
    current = tmp_path / 'current'
    current.symlink_to(directory, target_is_directory=True)
    for name, url in [('local-smoke.json', 'http://127.0.0.1'), ('public-smoke.json', identity['public_url'])]:
        (directory / name).write_text(json.dumps({**identity, 'base_url': url, 'status': 'passed',
            'cleanup_status': 'passed', 'checks': [{'passed': True}]}))
    (directory / 'runtime.json').write_text(json.dumps({**identity, 'current_release': str(directory)}))
    return directory, current, identity


def test_acceptance_requires_both_checks_and_current_release_and_exports_only_references(release):
    directory, current, _ = release
    result = provenance.finish(directory, True, 'acceptance', current)
    assert result['acceptance'] == 'passed'
    payload = json.loads(provenance.export(directory))
    assert set(payload) == {'result'} and len(payload['result']['artifact_refs']) == 3
    assert 'cloud.env' not in json.dumps(payload)
    for name, ref in result['artifact_refs'].items():
        assert ref['sha256'] == hashlib.sha256((directory / name).read_bytes()).hexdigest()
    (directory / 'public-smoke.json').write_text('{}')
    with pytest.raises(ValueError, match='changed'):
        provenance.export(directory)


@pytest.mark.parametrize('fault', ['public_missing', 'cleanup', 'stale_sha', 'failed_check', 'runtime_missing', 'current_previous', 'not_passed'])
def test_missing_failed_stale_or_unaccepted_release_cannot_pass(release, fault):
    directory, current, _ = release
    path = directory / 'public-smoke.json'
    smoke = json.loads(path.read_text())
    if fault == 'public_missing':
        path.unlink()
    elif fault == 'runtime_missing':
        (directory / 'runtime.json').unlink()
    elif fault == 'current_previous':
        current.unlink()
        current.symlink_to(directory.parent / 'previous')
    elif fault == 'cleanup':
        smoke['cleanup_status'] = 'failed'
        path.write_text(json.dumps(smoke))
    elif fault == 'stale_sha':
        smoke['source_sha'] = 'd' * 40
        path.write_text(json.dumps(smoke))
    elif fault == 'failed_check':
        smoke['checks'][0]['passed'] = False
        path.write_text(json.dumps(smoke))
    result = provenance.finish(directory, fault != 'not_passed', 'acceptance', current)
    assert result['acceptance'] == 'failed'


def test_private_config_and_symlink_artifacts_cannot_be_exported(release):
    directory, current, _ = release
    path = directory / 'public-smoke.json'
    path.unlink()
    path.symlink_to(directory / 'source-metadata.json')
    with pytest.raises(ValueError, match='artifact'):
        provenance.finish(directory, False, 'public_smoke', current)


@pytest.mark.parametrize('fault', [None, 'enabled', 'missing_flags', 'unhealthy', 'missing', 'ai_service', 'outside_ai', 'ai_port'])
def test_runtime_inspects_actual_containers_and_host_listeners(release, monkeypatch, fault):
    directory, current, _ = release
    services = ['shared-backend', 'product-database']
    if fault == 'ai_service':
        services[1] = 'rag-server'
    def command(*args):
        if args[-2:] == ('config', '--services'):
            return '\n'.join(services)
        if args[-2:] == ('ps', '-q'):
            return 'd' * 64 + ('\n' + 'e' * 64 if fault != 'missing' else '')
        if args[:2] == ('docker', 'ps'):
            return '\n'.join(services + (['leftover-rag-server'] if fault == 'outside_ai' else []))
        service = services[0 if args[-1] == 'd' * 64 else 1]
        return json.dumps([{'State': {'Status': 'running', 'Health': {'Status': 'unhealthy' if fault == 'unhealthy' else 'healthy'}},
            'Config': {'Labels': {'com.docker.compose.service': service},
            'Env': ([key + '=' + ('true' if fault == 'enabled' else 'false') for key in provenance.FLAGS] if fault != 'missing_flags' else []) + ['PRIVATE_VALUE=must-not-be-exported']}}])
    original = Path.read_text
    def read_text(path, *args, **kwargs):
        if str(path).startswith('/proc/net/tcp'):
            port = 11434 if fault == 'ai_port' else 80
            return 'header\n0: 00000000:%04X 00000000:0000 0A\n' % port
        return original(path, *args, **kwargs)
    monkeypatch.setattr(provenance, 'command', command)
    monkeypatch.setattr(Path, 'read_text', read_text)
    if fault:
        with pytest.raises(ValueError):
            provenance.runtime(directory, current)
    else:
        result = provenance.runtime(directory, current)
        assert result['service_names'] == sorted(services) and result['listening_ports'] == [80]
        assert 'PRIVATE_VALUE' not in json.dumps(result) and 'must-not-be-exported' not in json.dumps(result)


@pytest.fixture
def deployment(monkeypatch, tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'app.py').write_text('pass\n')
    state = {'status': 'Success', 'payload_fault': None, 'calls': []}
    monkeypatch.setattr(deploy, 'source_identity', lambda: {'source_sha': SHA, 'trigger': 'github_actions', 'run_id': 123, 'run_attempt': 1})
    monkeypatch.setattr(deploy, 'main_sha', lambda _: SHA)
    monkeypatch.setattr(deploy, 'prepare', lambda _: source)
    monkeypatch.setattr(deploy.subprocess, 'run', lambda *a, **k: None)
    monkeypatch.setattr(deploy.time, 'sleep', lambda _: None)
    def aws(*args):
        state['calls'].append(args)
        if args[:2] == ('cloudformation', 'describe-stacks'):
            values = {'InstanceId': INSTANCE, 'PublicUrl': 'https://fixture.cloudfront.net', 'ReleaseBucket': 'fixture-bucket',
                      'OriginSecretArn': 'fixture-origin-arn', 'DemoPasswordArn': 'fixture-password-arn'}  # pragma: allowlist secret - Synthetic ARN labels; no actual credential or AWS request.
            return {'Stacks': [{'Outputs': [{'OutputKey': k, 'OutputValue': v} for k, v in values.items()]}]}
        if args[:2] == ('ssm', 'send-command'):
            commands = json.loads(args[args.index('--parameters') + 1])['commands'][0]
            state['commands'] = commands
            return {'Command': {'CommandId': COMMAND}}
        # The checked digest is read from the actual generated SSM identity input.
        import shlex
        commands = shlex.split(state['commands'])[-1].splitlines()
        identity_line = next(line for line in commands if line.startswith("printf '%s"))
        identity = json.loads(shlex.split(identity_line)[2])
        remote = f"/srv/asd/releases/{identity['release_id']}-{identity['source_sha256'][:12]}"
        result = {**identity, 'acceptance': 'passed', 'phase': 'acceptance', 'captured_at': '2026-10-17T00:00:00+00:00',
                  'current_release': remote, 'artifact_refs': {name: {'path': remote + '/' + name, 'sha256': 'f' * 64} for name in provenance.ARTIFACTS},
                  'private_extra': 'must-not-be-exported'}
        if state['payload_fault'] == 'stale':
            result['source_sha'] = 'd' * 40
        if state['payload_fault'] == 'no_public':
            del result['artifact_refs']['public-smoke.json']
        if state['payload_fault'] == 'wrong_current':
            result['current_release'] = '/srv/asd/releases/previous'
        stdout = 'raw-private-output' if state['payload_fault'] == 'raw' else json.dumps({'result': result})
        return {'Status': state['status'], 'StandardOutputContent': stdout, 'StandardErrorContent': 'raw-private-stderr'}
    monkeypatch.setattr(deploy, 'aws', aws)
    return state


def test_deploy_records_exact_bundle_actions_target_and_check_references(deployment):
    report = deploy.deploy('fixture-stack', SHA + '-1')
    assert report['source_sha'] == SHA and report['status'] == 'Success' and report['acceptance'] == 'passed'
    assert report['command_id'] == COMMAND and report['target_instance'] == INSTANCE
    assert len(report['host_evidence']['artifact_refs']) == 3
    assert 'private_extra' not in json.dumps(report) and 'must-not-be-exported' not in json.dumps(report)
    assert 'deployment.log' in deployment['commands'] and 'cloud/provenance.py' in deployment['commands']


@pytest.mark.parametrize('fault', ['raw', 'stale', 'no_public', 'wrong_current', 'failed_status'])
def test_bad_or_failed_ssm_evidence_is_a_safe_failure_artifact(deployment, tmp_path, capsys, fault):
    if fault == 'failed_status':
        deployment['status'] = 'Failed'
    else:
        deployment['payload_fault'] = fault
    output = tmp_path / 'deployment-report.json'
    assert deploy.main(['--release', SHA + '-1', '--report', str(output)]) == 1
    report = json.loads(output.read_text())
    assert report['acceptance'] == 'failed'
    assert 'raw-private' not in output.read_text() + capsys.readouterr().out


def test_source_mismatch_is_rejected_before_aws(deployment):
    with pytest.raises(deploy.DeploymentFailure):
        deploy.deploy('fixture-stack', 'wrong-source-1')
    assert not deployment['calls']


def test_aws_exception_stderr_is_not_printed_or_saved(deployment, monkeypatch, tmp_path, capsys):
    def failed(*args):
        raise subprocess.CalledProcessError(1, ['aws'], stderr='private-environment-and-secrets')
    monkeypatch.setattr(deploy, 'aws', failed)
    output = tmp_path / 'failure.json'
    assert deploy.main(['--release', SHA + '-1', '--report', str(output)]) == 1
    assert 'private-environment' not in output.read_text() + capsys.readouterr().out


@pytest.mark.parametrize('fault', [None, 'branch', 'dirty', 'wrong_sha', 'wrong_ref', 'wrong_repo'])
def test_source_identity_requires_clean_exact_main_checkout(monkeypatch, fault):
    for key, value in {'GITHUB_ACTIONS': 'true', 'GITHUB_SHA': SHA, 'GITHUB_REF': 'refs/heads/main',
                       'GITHUB_REPOSITORY': 'egoldman2/ASD', 'GITHUB_EVENT_NAME': 'push',
                       'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '1'}.items():
        monkeypatch.setenv(key, value)
    if fault == 'branch':
        monkeypatch.delenv('GITHUB_ACTIONS')
    for problem, key, value in [('wrong_sha', 'GITHUB_SHA', 'd' * 40), ('wrong_ref', 'GITHUB_REF', 'refs/heads/ethan-goldman'),
                                ('wrong_repo', 'GITHUB_REPOSITORY', 'other/ASD')]:
        if fault == problem:
            monkeypatch.setenv(key, value)
    def git(args, **kwargs):
        if args[1:] == ['rev-parse', 'HEAD']:
            return SHA + '\n'
        if args[1] == 'status':
            assert '--untracked-files=all' in args
            return '?? cloud/uncommitted.py\n' if fault == 'dirty' else ''
        return 'ethan-goldman\n'
    monkeypatch.setattr(deploy.subprocess, 'check_output', git)
    if fault:
        with pytest.raises(ValueError):
            deploy.source_identity()
    else:
        assert deploy.source_identity() == {'source_sha': SHA, 'trigger': 'github_actions', 'run_id': 123, 'run_attempt': 1}


@pytest.mark.parametrize('fault', [None, 'build', 'public_smoke', 'candidate', 'candidate_late'])
def test_install_checks_before_acceptance_and_attempts_rollback(tmp_path, fault):
    import os
    import sys
    root = tmp_path / 'host'
    directory = root / 'releases/candidate'
    cloud = directory / 'cloud'
    cloud.mkdir(parents=True)
    previous = root / 'releases/previous'
    previous.mkdir()
    (previous / 'cloud.env').write_text('fixture-only\n')
    (root / 'current').symlink_to(previous, target_is_directory=True)
    (root / 'bootstrap-ready').touch()
    (root / 'session-secret').write_text('a' * 64)
    (directory / 'source-metadata.json').write_text(json.dumps({'source_sha': SHA}))
    binaries = tmp_path / 'bin'
    binaries.mkdir()
    log = tmp_path / 'calls.jsonl'
    # Controlled executables exercise the real Bash ordering/trap without AWS/Docker.
    script = '''#!INTERPRETER
import json,os,pathlib,sys
args=sys.argv[1:]
with open(os.environ['FIXTURE_CALLS'],'a') as stream:stream.write(json.dumps([pathlib.Path(sys.argv[0]).name,*args])+'\\n')
if pathlib.Path(sys.argv[0]).name=='aws':print('x'*32)
if pathlib.Path(sys.argv[0]).name=='readlink':
 try:print(pathlib.Path(args[-1]).resolve(strict=True))
 except FileNotFoundError:raise SystemExit(1)
if pathlib.Path(sys.argv[0]).name=='docker' and os.environ.get('FIXTURE_FAULT')=='build' and '--build' in args:raise SystemExit(1)
if pathlib.Path(sys.argv[0]).name=='flock':pass
'''.replace('INTERPRETER', sys.executable)
    for name in ('aws', 'docker', 'flock', 'readlink'):
        path = binaries / name
        path.write_text(script)
        path.chmod(0o700)
    # BSD mv has no -T; this fixture emulates Linux's symlink replacement only.
    path = binaries / 'mv'
    path.write_text('#!' + sys.executable + '\nimport os,sys\nos.replace(sys.argv[-2],sys.argv[-1])\n')
    path.chmod(0o700)
    helper = '''import json,os,sys
with open(os.environ['FIXTURE_CALLS'],'a') as stream:stream.write(json.dumps([__file__,*sys.argv[1:]])+'\\n')
if __file__.endswith('smoke.py') and sys.argv[1].startswith('https') and os.environ.get('FIXTURE_FAULT')=='public_smoke':raise SystemExit(1)
'''
    (cloud / 'smoke.py').write_text(helper)
    (cloud / 'provenance.py').write_text(helper)
    (cloud / 'check_workflows.py').write_text('''import os
from pathlib import Path
class GitHub: pass
def main_sha(_):
 path=Path(__file__).with_name('candidate-count')
 count=int(path.read_text())+1 if path.exists() else 1
 path.write_text(str(count))
 fault=os.environ.get('FIXTURE_FAULT')
 return ('b' if fault=='candidate' or (fault=='candidate_late' and count>1) else 'a')*40
''')
    source = Path(__file__).resolve().parents[1] / 'install.sh'
    install = cloud / 'install.sh'
    install.write_text(source.read_text().replace('/srv/asd', str(root)))
    env = {**os.environ, 'PATH': str(binaries) + os.pathsep + os.environ['PATH'],
           'FIXTURE_CALLS': str(log), 'FIXTURE_FAULT': fault or ''}
    run = subprocess.run(['bash', str(install), SHA + '-1', 'https://fixture.cloudfront.net', 'fixture-origin-arn', 'fixture-password-arn', 'ap-southeast-2'], env=env, capture_output=True, text=True, check=False)  # noqa: S603,S607 - Fixed Bash fixture; all paths/arguments are test-owned, no external commands or shell expansion.
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert (root / 'session-secret').read_text() == 'a' * 64
    assert (directory / 'cloud.env').stat().st_mode & 0o777 == 0o600
    assert 'a' * 64 not in run.stdout and 'x' * 32 not in run.stdout
    if fault:
        assert run.returncode == 1
        assert (root / 'current').resolve() == previous
        assert any(str(previous / 'cloud.env') in row for row in calls if row[0] == 'docker')
        assert not any('--passed' in row for row in calls)
        phase = 'candidate' if fault.startswith('candidate') else fault
        assert any('--phase' in row and phase in row for row in calls if row[0].endswith('provenance.py'))
    else:
        assert run.returncode == 0, run.stderr
        assert (root / 'current').resolve() == directory
        assert [row[1] for row in calls if row[0].endswith('smoke.py')] == ['http://127.0.0.1', 'https://fixture.cloudfront.net']
        assert any('--passed' in row and 'acceptance' in row for row in calls)


@pytest.mark.parametrize('when', ['before_upload', 'before_ssm'])
def test_superseded_candidate_is_skipped_without_sending_ssm(deployment, monkeypatch, when):
    values = iter(['b' * 40] if when == 'before_upload' else [SHA, 'b' * 40])
    monkeypatch.setattr(deploy, 'main_sha', lambda _: next(values))
    report = deploy.deploy('fixture-stack', SHA + '-1')
    assert report['status'] == 'Superseded' and report['acceptance'] == 'skipped'
    assert not any(call[:2] == ('ssm', 'send-command') for call in deployment['calls'])
