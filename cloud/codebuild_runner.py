"""Admit one validated main deployment job to an ephemeral CodeBuild runner."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cloud.check_workflows import GitHub, PREFIX, REPOSITORY, check, main_sha

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / '.aws-deployment/runner-expected.json'
WORKFLOW = '.github/workflows/cloud-deployment.yml'
# shortcut: pin the reviewed runner for Release 2; review its hook isolation before upgrading.
RUNNER_URL = 'https://github.com/actions/runner/releases/download/v2.337.0/actions-runner-linux-x64-2.337.0.tar.gz'
RUNNER_SHA256 = '70920811a4f8ad4328818682bca5c6469c1c942fab52448868071d0063816613'  # pragma: allowlist secret - Public SHA-256 of the pinned official runner release.


def source_token():
    result = subprocess.run(  # noqa: S603 - Fixed Git credential-helper request; output remains private.
        ['git', 'credential', 'fill'], cwd=ROOT,  # noqa: S607 - Git is supplied by the controlled CodeBuild image.
        input='protocol=https\nhost=github.com\npath=egoldman2/ASD.git\n\n',
        capture_output=True, text=True, timeout=20,
        env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'},
    )
    values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    token = values.get('password', '')
    if result.returncode or not token or len(token) > 8192:
        raise RuntimeError('Source connection did not supply a temporary GitHub credential.')
    return token


def runner_api(api, method, suffix):
    allowed = (method == 'POST' and suffix == 'registration-token'
               or method == 'DELETE' and re.fullmatch(r'[1-9][0-9]*', suffix))
    if not allowed:
        raise ValueError('Invalid runner API operation.')
    request = Request(
        'https://api.github.com' + PREFIX + '/actions/runners/' + suffix,
        data=b'{}' if method == 'POST' else None,
        method=method, headers={'Authorization': 'Bearer ' + api.token,
                                'Accept': 'application/vnd.github+json',
                                'X-GitHub-Api-Version': '2026-03-10'},
    )
    try:
        with api.opener.open(request, timeout=15) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('Oversized runner response.')
        value = json.loads(raw) if raw else {}
        if not isinstance(value, dict):
            raise ValueError('Invalid runner response.')
        return value
    except HTTPError as error:
        if method == 'DELETE' and error.code == 404:
            return {}
        raise RuntimeError('Runner API rejected the operation: ' + str(error.code)) from None
    except (URLError, ValueError, OSError):
        raise RuntimeError('Runner API unavailable or invalid.') from None


def valid_run(run, sha, run_id=None, attempt=None):
    return (run.get('head_sha') == sha and run.get('head_branch') == 'main'
            and run.get('path') == WORKFLOW and run.get('event') in {'push', 'workflow_dispatch'}
            and type(run.get('id')) is int and run['id'] > 0
            and type(run.get('run_attempt')) is int and run['run_attempt'] > 0
            and (run_id is None or run['id'] == run_id)
            and (attempt is None or run['run_attempt'] == attempt))


def wait_for_job(api, sha, timeout=1500):
    expires = time.monotonic() + timeout
    api.deadline = expires
    while time.monotonic() < expires:
        runs = api.pages(PREFIX + '/actions/workflows/cloud-deployment.yml/runs',
                         'workflow_runs', head_sha=sha, branch='main')
        candidates = [run for run in runs if valid_run(run, sha)]
        if candidates:
            active = [run for run in candidates if run.get('status') == 'in_progress']
            run = max(active or candidates, key=lambda row: (row.get('created_at', ''), row['id']))
            jobs = api.pages(PREFIX + f"/actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs", 'jobs')
            deploy = [job for job in jobs if job.get('name') == 'deploy']
            others = [job for job in jobs if job.get('name') != 'deploy']
            if any(job.get('status') == 'completed' and job.get('conclusion') != 'success' for job in others):
                raise RuntimeError('Main deployment prerequisites failed.')
            label = f"asd-main-{run['id']}-{run['run_attempt']}"
            if (len(deploy) == 1 and deploy[0].get('status') == 'queued'
                    and deploy[0].get('labels') == [label] and len(others) == 9
                    and all(job.get('status') == 'completed' and job.get('conclusion') == 'success' for job in others)):
                gate = check(api, json.loads((ROOT / 'cloud/student-workflows.json').read_text()), sha, timeout=0)
                # A superseded queued job must reach its rejecting hook to release workflow concurrency.
                if gate['status'] not in {'passed', 'superseded'}:
                    raise RuntimeError('Five exact-main student workflows did not pass.')
                api.deadline = None
                return {'source_sha': sha, 'run_id': run['id'], 'run_attempt': run['run_attempt'],
                        'job_id': deploy[0]['id'], 'event': run['event'], 'label': label}
            if run.get('status') == 'completed':
                if run.get('conclusion') == 'success' or main_sha(api) != sha:
                    return None
                raise RuntimeError('Main workflow finished before requesting this runner.')
        time.sleep(15)
    raise TimeoutError('No validated main deployment job became ready.')


def authorize_job(api, expected, environment):
    values = {'GITHUB_REPOSITORY': REPOSITORY, 'GITHUB_REF': 'refs/heads/main',
              'GITHUB_SHA': expected['source_sha'], 'GITHUB_RUN_ID': str(expected['run_id']),
              'GITHUB_RUN_ATTEMPT': str(expected['run_attempt']), 'GITHUB_JOB': 'deploy',
              'GITHUB_EVENT_NAME': expected['event']}
    if any(environment.get(key) != value for key, value in values.items()):
        raise RuntimeError('Runner refused an unexpected workflow context.')
    run = api.get(PREFIX + '/actions/runs/' + str(expected['run_id']))
    job = api.get(PREFIX + '/actions/jobs/' + str(expected['job_id']))
    if (not valid_run(run, expected['source_sha'], expected['run_id'], expected['run_attempt'])
            or main_sha(api) != expected['source_sha']
            or job.get('id') != expected['job_id'] or job.get('run_id') != expected['run_id']
            or job.get('run_attempt') != expected['run_attempt'] or job.get('name') != 'deploy'
            or job.get('status') != 'in_progress' or job.get('runner_id') != expected['runner_id']
            or job.get('runner_name') != expected['runner_name']):
        raise RuntimeError('Runner refused a job not assigned to the approved main deployment.')


def download_runner(directory):
    archive = directory / 'runner.tar.gz'
    digest, size = hashlib.sha256(), 0
    with urlopen(RUNNER_URL, timeout=30) as response, archive.open('xb') as output:  # noqa: S310 - Fixed official HTTPS release; content must match the reviewed digest.
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > 300 * 1024 * 1024:
                raise RuntimeError('Runner archive exceeds its size limit.')
            digest.update(chunk)
            output.write(chunk)
    if digest.hexdigest() != RUNNER_SHA256:
        raise RuntimeError('Runner archive digest mismatch.')
    with tarfile.open(archive) as package:
        package.extractall(directory, filter='data')


def run():
    sha = os.environ.get('CODEBUILD_RESOLVED_SOURCE_VERSION', '')
    source = os.environ.get('CODEBUILD_SOURCE_VERSION')
    head = os.environ.get('CODEBUILD_WEBHOOK_HEAD_REF')
    if (not re.fullmatch(r'[a-f0-9]{40}', sha) or source not in {'main', sha}
            or head not in {None, 'refs/heads/main'}
            or (head is not None and os.environ.get('CODEBUILD_WEBHOOK_EVENT') != 'PUSH')
            or not os.environ.get('CODEBUILD_BUILD_ID')):
        raise RuntimeError('Runner requires a main CodeBuild source build.')
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, timeout=15).strip()  # noqa: S603,S607 - Fixed read-only Git command.
    if actual != sha:
        raise RuntimeError('Runner source checkout does not match its build.')
    api = GitHub(source_token())
    expected = wait_for_job(api, sha)
    if expected is None:
        print('Main candidate superseded; no runner registered.')
        return
    runner_name = 'asd-deploy-' + os.environ['CODEBUILD_BUILD_ID'].rsplit(':', 1)[-1]
    runner_id = None
    try:
        with tempfile.TemporaryDirectory(prefix='asd-actions-runner-') as temporary:
            directory = Path(temporary)
            download_runner(directory)
            registration = runner_api(api, 'POST', 'registration-token')
            environment = {**os.environ, 'RUNNER_ALLOW_RUNASROOT': '1',
                           'ACTIONS_RUNNER_HOOK_JOB_STARTED': str(ROOT / 'cloud/codebuild_runner_hook.sh')}
            configured = subprocess.run(  # noqa: S603 - Digest-verified vendor executable; credentials captured privately and never logged.
                [str(directory / 'config.sh'), '--url', 'https://github.com/' + REPOSITORY,
                 '--token', registration['token'], '--unattended', '--ephemeral', '--disableupdate',
                 '--no-default-labels', '--name', runner_name, '--labels', expected['label']],
                cwd=directory, env=environment, capture_output=True, text=True, timeout=90,
            )
            if configured.returncode:
                raise RuntimeError('Ephemeral runner registration failed.')
            runner_id = json.loads((directory / '.runner').read_text(encoding='utf-8-sig'))['agentId']
            if type(runner_id) is not int or runner_id < 1:
                raise RuntimeError('Invalid registered runner identity.')
            EXPECTED.parent.mkdir(exist_ok=True, mode=0o700)
            descriptor = os.open(EXPECTED, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w') as stream:
                json.dump({**expected, 'runner_id': runner_id, 'runner_name': runner_name, 'token': api.token}, stream)
            print(f"Runner reserved for main run {expected['run_id']}, attempt {expected['run_attempt']}, job {expected['job_id']}.", flush=True)
            process = subprocess.run([str(directory / 'run.sh')], cwd=directory, env=environment, timeout=3900)  # noqa: S603 - Same digest-verified vendor distribution; one ephemeral job only.
            if process.returncode:
                raise RuntimeError('Ephemeral runner failed.')
            api = GitHub(source_token())
            for _ in range(15):
                job = api.get(PREFIX + '/actions/jobs/' + str(expected['job_id']))
                if job.get('status') == 'completed':
                    if job.get('conclusion') != 'success' or job.get('runner_id') != runner_id:
                        raise RuntimeError('The approved deployment job did not succeed on this runner.')
                    return
                time.sleep(2)
            raise RuntimeError('The approved deployment job did not complete.')
    finally:
        EXPECTED.unlink(missing_ok=True)
        if runner_id is not None:
            runner_api(GitHub(source_token()), 'DELETE', str(runner_id))


def main():
    if sys.argv[1:] == ['guard']:
        expected = json.loads(EXPECTED.read_text())
        authorize_job(GitHub(expected['token']), expected, os.environ)
        EXPECTED.unlink()
        print('Approved main deployment job admitted.')
    elif sys.argv[1:] == ['run']:
        run()
    else:
        raise ValueError('Use run or guard.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Subprocess exceptions can contain credential-bearing command arguments.
        detail = str(error) if type(error) in {RuntimeError, TimeoutError} else type(error).__name__
        print('Deployment runner failed: ' + detail, file=sys.stderr)
        raise SystemExit(1) from None
