"""Deploy a main checkout through SSM and retain safe release/check provenance."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tarfile
import tempfile
import time
from urllib.parse import urlsplit

if __package__:
    from .prepare import prepare
    from .check_workflows import GitHub, main_sha
else:
    from prepare import prepare
    from check_workflows import GitHub, main_sha

REGION = 'ap-southeast-2'
ROOT = Path(__file__).resolve().parents[1]


class DeploymentFailure(RuntimeError):
    def __init__(self, report):
        super().__init__('Deployment failed; inspect the sanitized report and private SSM host logs.')
        self.report = report


class SupersededRelease(RuntimeError):
    pass


def ensure_current(sha):
    if main_sha(GitHub(os.environ.get('GITHUB_TOKEN', ''))) != sha:
        raise SupersededRelease('Candidate superseded by current main.')


def aws(*arguments):
    result = subprocess.run(['aws', *arguments, '--region', REGION, '--output', 'json'], check=True, capture_output=True, text=True)  # noqa: S603,S607 - Fixed CLI, argument arrays only; identifiers are validated before remote shell construction.
    return json.loads(result.stdout) if result.stdout.strip() else None


def outputs(stack):
    result = aws('cloudformation', 'describe-stacks', '--stack-name', stack)
    return {entry['OutputKey']: entry['OutputValue'] for entry in result['Stacks'][0]['Outputs']}


def source_identity():
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()  # noqa: S603,S607 - Fixed read-only Git commands, no shell or user arguments.
    sha = git('rev-parse', 'HEAD')
    if not re.fullmatch(r'[a-f0-9]{40}', sha) or git('status', '--porcelain', '--untracked-files=all'):
        raise ValueError('Deploy only a clean committed main checkout.')
    actions = os.environ.get('GITHUB_ACTIONS') == 'true'
    if actions:
        if (os.environ.get('GITHUB_REF') != 'refs/heads/main' or os.environ.get('GITHUB_SHA') != sha
                or os.environ.get('GITHUB_REPOSITORY') != 'egoldman2/ASD'
                or os.environ.get('GITHUB_EVENT_NAME') not in {'push', 'workflow_dispatch'}):
            raise ValueError('Actions deployment requires this repository main SHA.')
        run_id, attempt = int(os.environ['GITHUB_RUN_ID']), int(os.environ['GITHUB_RUN_ATTEMPT'])
        if min(run_id, attempt) < 1:
            raise ValueError('Invalid Actions identity.')
        return {'source_sha': sha, 'trigger': 'github_actions', 'run_id': run_id, 'run_attempt': attempt}
    if git('branch', '--show-current') != 'main':
        raise ValueError('Manual deployment also requires main.')
    return {'source_sha': sha, 'trigger': 'manual'}


def safe_host_evidence(payload, identity, remote):
    result = payload['result']
    if any(result.get(key) != value for key, value in identity.items()):
        raise ValueError('SSM release identity mismatch.')
    if result.get('acceptance') not in {'passed', 'failed'}:
        raise ValueError('Invalid acceptance.')
    current = result.get('current_release')
    if (not isinstance(current, str) or not re.fullmatch(r'/srv/asd/(?:current|releases/[A-Za-z0-9._-]+)', current)
            or (result['acceptance'] == 'passed' and current != remote)):
        raise ValueError('Invalid current release.')
    phase = result.get('phase')
    if phase not in {'configuration', 'candidate', 'build', 'local_smoke', 'public_smoke', 'runtime', 'acceptance'}:
        raise ValueError('Invalid deployment phase.')
    captured = result['captured_at']
    if datetime.fromisoformat(captured.replace('Z', '+00:00')).tzinfo is None:
        raise ValueError('Invalid capture time.')
    refs = {}
    for name, ref in result.get('artifact_refs', {}).items():
        if name not in {'local-smoke.json', 'public-smoke.json', 'runtime.json'}:
            continue
        if ref['path'] != remote + '/' + name or not re.fullmatch(r'[a-f0-9]{64}', ref['sha256']):
            raise ValueError('Invalid artifact reference.')
        refs[name] = {'path': ref['path'], 'sha256': ref['sha256']}
    if result['acceptance'] == 'passed' and len(refs) != 3:
        raise ValueError('Acceptance requires local, public and runtime captures.')
    # Keep full check files on the host; export only validated identities/references.
    return {**identity, 'acceptance': result['acceptance'], 'phase': phase,
            'captured_at': captured, 'current_release': current, 'artifact_refs': refs}


def deploy(stack, release_id):
    report = {'release_id': release_id, 'environment': 'aws-cloud', 'region': REGION,
              'owner': 'Ethan Goldman', 'captured_at': datetime.now(timezone.utc).isoformat(),
              'command': 'python3 cloud/deploy.py', 'status': 'NotStarted', 'acceptance': 'failed'}
    try:
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}', release_id):
            raise ValueError('Invalid release ID.')
        report.update(source_identity())
        if report['trigger'] == 'github_actions' and release_id != f"{report['source_sha']}-{report['run_attempt']}":
            raise ValueError('Release ID must match the checked out Actions SHA and attempt.')
        ensure_current(report['source_sha'])
        resources = outputs(stack)
        url = urlsplit(resources['PublicUrl'])
        if (url.scheme != 'https' or not url.hostname or url.port not in {None, 443}
                or url.path not in {'', '/'} or url.query or url.fragment or url.username or url.password):
            raise ValueError('Invalid public target.')
        report.update(target_instance=resources['InstanceId'], public_url=resources['PublicUrl'])
        if not re.fullmatch(r'i-(?:[a-f0-9]{8}|[a-f0-9]{17})', report['target_instance']):
            raise ValueError('Invalid target instance.')
        with tempfile.TemporaryDirectory(prefix='asd-cloud-release-') as temporary:
            directory = Path(temporary)
            context = prepare(directory / 'source')
            bundle = directory / 'source.tar.gz'
            with tarfile.open(bundle, 'w:gz') as archive:
                for path in sorted(context.rglob('*')):
                    if path.is_file():
                        archive.add(path, arcname=path.relative_to(context), recursive=False)
            digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
            report['source_sha256'] = digest
            key = f'releases/{release_id}-{digest[:12]}.tar.gz'
            subprocess.run(['aws', 's3', 'cp', str(bundle), f"s3://{resources['ReleaseBucket']}/{key}", '--region', REGION, '--sse', 'AES256', '--only-show-errors'], check=True, capture_output=True, text=True)  # noqa: S603,S607 - Fixed AWS CLI and argument array; no shell.
        remote = f'/srv/asd/releases/{release_id}-{digest[:12]}'
        identity = {key: report[key] for key in ('source_sha', 'source_sha256', 'release_id', 'target_instance', 'public_url', 'region')}
        installer = 'bash ' + shlex.quote(remote + '/cloud/install.sh') + ' ' + ' '.join(shlex.quote(value) for value in (
            release_id, resources['PublicUrl'], resources['OriginSecretArn'], resources['DemoPasswordArn'], REGION,
        ))
        commands = [
            'set -euo pipefail',
            'for attempt in $(seq 1 120); do test -f /srv/asd/bootstrap-ready && break; sleep 2; done',
            'test -f /srv/asd/bootstrap-ready',
            f'test ! -e {shlex.quote(remote)}', f'mkdir {shlex.quote(remote)}',
            'aws s3 cp ' + shlex.quote(f"s3://{resources['ReleaseBucket']}/{key}") + ' ' + shlex.quote(remote + '/source.tar.gz') + f' --region {REGION} --only-show-errors',
            f"echo '{digest}  {remote}/source.tar.gz' | sha256sum --check > /dev/null",
            f'tar --extract --gzip --file {shlex.quote(remote + "/source.tar.gz")} --directory {shlex.quote(remote)} --no-same-owner',
            "printf '%s\\n' " + shlex.quote(json.dumps(identity)) + ' > ' + shlex.quote(remote + '/source-metadata.json'),
            'result=0', installer + ' > ' + shlex.quote(remote + '/deployment.log') + ' 2>&1 || result=$?',
            'python3 ' + shlex.quote(remote + '/cloud/provenance.py') + ' export ' + shlex.quote(remote),
            'exit "$result"',
        ]
        ensure_current(report['source_sha'])
        response = aws('ssm', 'send-command', '--document-name', 'AWS-RunShellScript', '--instance-ids', resources['InstanceId'],
                       '--parameters', json.dumps({'commands': ['bash -lc ' + shlex.quote('\n'.join(commands))], 'executionTimeout': ['3600']}), '--comment', f'ASD release {release_id}')
        report['command_id'] = response['Command']['CommandId']
        if not re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', report['command_id']):
            raise ValueError('Invalid SSM command identity.')
        report['status'] = 'Pending'
        print(f"Deployment command: {report['command_id']}", flush=True)
        for attempt in range(360):
            time.sleep(10)
            try:
                result = aws('ssm', 'get-command-invocation', '--command-id', report['command_id'], '--instance-id', resources['InstanceId'])
            except subprocess.CalledProcessError as error:
                if 'InvocationDoesNotExist' in (error.stderr or ''):
                    continue
                raise
            report['status'] = result['Status']
            if result['Status'] not in {'Success', 'Failed', 'Cancelled', 'TimedOut', 'Cancelling'}:
                continue
            # Never print raw SSM stdout/stderr: build and application logs remain private.
            raw = result.get('StandardOutputContent', '')
            if len(raw.encode()) <= 22000:
                try:
                    payload = json.loads(raw)
                    accepted = safe_host_evidence(payload, identity, remote)
                    report.update(acceptance=accepted['acceptance'], current_release=accepted['current_release'],
                                  host_evidence=accepted)
                except (ValueError, TypeError, KeyError, AttributeError):
                    report['evidence_error'] = 'missing_or_invalid_ssm_evidence'
            else:
                report['evidence_error'] = 'ssm_evidence_size_limit'
            report['captured_at'] = datetime.now(timezone.utc).isoformat()
            if result['Status'] == 'Success' and report['acceptance'] == 'passed' and 'evidence_error' not in report:
                return report
            raise RuntimeError('SSM deployment or acceptance failed.')
        raise TimeoutError('SSM deployment exceeded its observation timeout.')
    except SupersededRelease:
        report.update(status='Superseded', acceptance='skipped',
                      captured_at=datetime.now(timezone.utc).isoformat())
        return report
    except Exception as error:
        report['acceptance'] = 'failed'
        report['failure_type'] = type(error).__name__
        report['captured_at'] = datetime.now(timezone.utc).isoformat()
        raise DeploymentFailure(report) from error


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stack', default='asd-release2')
    parser.add_argument('--release', default=datetime.now(timezone.utc).strftime('manual-%Y%m%d-%H%M%S'))
    parser.add_argument('--report', type=Path)
    args = parser.parse_args(argv)
    try:
        report = deploy(args.stack, args.release)
    except DeploymentFailure as error:
        report = error.report
    host = report.pop('host_evidence', None)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        evidence = args.report.parent / 'deployment-evidence'
        path = evidence / 'deployment-result.json'
        if path.exists():
            path.unlink()
        if host:
            evidence.mkdir(exist_ok=True)
            path.write_text(json.dumps(host, indent=2) + '\n')
            report['evidence_files'] = {path.name: {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}}
        args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'Superseded' or (report['status'] == 'Success' and report['acceptance'] == 'passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
