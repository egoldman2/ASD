"""Fail closed on five exact main-push workflow results for one deployment SHA."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

REPOSITORY = 'egoldman2/ASD'
PREFIX = '/repos/' + REPOSITORY
MAPPING = Path(__file__).with_name('student-workflows.json')
PAGE_SIZE = 100


class APIError(RuntimeError):
    def __init__(self, code):
        allowed = {'invalid_api_route', 'api_response_size_limit', 'api_unavailable_or_invalid_json',
                   'invalid_api_document', 'invalid_or_oversized_api_collection', 'api_pagination_limit',
                   'invalid_main_sha', 'run_identity_mismatch', 'missing_or_excessive_jobs', 'job_identity_mismatch'}
        self.code = code if code in allowed or re.fullmatch(r'api_http_[1-5][0-9]{2}', code) else 'api_validation_failed'
        super().__init__(self.code)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_):
        return None


class GitHub:
    def __init__(self, token=''):
        self.token = token
        self.deadline = None
        self.opener = build_opener(NoRedirect())

    def get(self, route, **params):
        if not re.fullmatch(re.escape(PREFIX) + r'/[A-Za-z0-9_./-]+', route):
            raise APIError('invalid_api_route')
        remaining = 15 if self.deadline is None else min(15, self.deadline - time.monotonic())
        if remaining <= 0:
            raise TimeoutError('api_deadline')
        headers = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2026-03-10'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        url = 'https://api.github.com' + route + ('?' + urlencode(params) if params else '')
        try:
            with self.opener.open(Request(url, headers=headers), timeout=remaining) as response:  # noqa: S310 - Fixed HTTPS GitHub origin, validated relative routes and redirects prohibited.
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise APIError('api_response_size_limit')
                data = json.loads(raw)
        except HTTPError as error:
            raise APIError('api_http_' + str(error.code)) from None
        except (URLError, ValueError, OSError, RecursionError):
            raise APIError('api_unavailable_or_invalid_json') from None
        if not isinstance(data, dict):
            raise APIError('invalid_api_document')
        return data

    def pages(self, route, key, **params):
        rows = []
        for page in range(1, 11):
            data = self.get(route, **params, per_page=PAGE_SIZE, page=page)
            batch = data.get(key)
            total = data.get('total_count')
            if (not isinstance(batch, list) or type(total) is not int or not 0 <= total <= 1000
                    or any(not isinstance(row, dict) or type(row.get('id')) is not int for row in batch)):
                raise APIError('invalid_or_oversized_api_collection')
            rows.extend(batch)
            if len({row['id'] for row in rows}) != len(rows) or len(rows) > total:
                raise APIError('invalid_or_oversized_api_collection')
            if len(rows) == total:
                return rows
            if len(batch) < PAGE_SIZE:
                raise APIError('invalid_or_oversized_api_collection')
        raise APIError('api_pagination_limit')


def main_sha(api):
    sha = api.get(PREFIX + '/git/ref/heads/main')['object']['sha']
    if not isinstance(sha, str) or not re.fullmatch(r'[a-f0-9]{40}', sha):
        raise APIError('invalid_main_sha')
    return sha


def valid_mapping(mapping):
    rows = mapping['workflows']
    if (mapping['repository'] != REPOSITORY or not isinstance(rows, list) or len(rows) != 5
            or len({row['id'] for row in rows}) != 5 or len({row['path'] for row in rows}) != 5
            or len({row['feature'] for row in rows}) != 5 or len({row['owner'] for row in rows}) != 5):
        raise ValueError('Expected five distinct assigned workflows.')
    for row in rows:
        if (type(row['id']) is not int or row['id'] < 1 or not isinstance(row['owner'], str) or not row['owner']
                or not re.fullmatch(r'\.github/workflows/[A-Za-z0-9_-]+\.ya?ml', row['path'])
                or row['path'] == '.github/workflows/cloud-deployment.yml'):
            raise ValueError('Invalid workflow assignment.')
    return rows


def run_summary(run, expected, sha):
    if (run.get('workflow_id') != expected['id'] or run.get('path') != expected['path']
            or run.get('head_sha') != sha or run.get('head_branch') != 'main' or run.get('event') != 'push'
            or type(run.get('id')) is not int or run['id'] < 1
            or type(run.get('run_attempt')) is not int or run['run_attempt'] < 1
            or run.get('html_url') != f"https://github.com/{REPOSITORY}/actions/runs/{run['id']}"):
        raise APIError('run_identity_mismatch')
    return {**expected, **{key: run.get(key) for key in ('id', 'workflow_id', 'path', 'head_sha', 'head_branch', 'event',
                                                     'run_attempt', 'status', 'conclusion', 'html_url')}}


def snapshot(api, rows, sha):
    runs = api.pages(PREFIX + '/actions/runs', 'workflow_runs', head_sha=sha, branch='main', event='push')
    summaries, pending, failed = [], [], []
    for expected in rows:
        candidates = [run for run in runs if run.get('workflow_id') == expected['id']]
        if not candidates:
            pending.append('missing_workflow:' + str(expected['id']))
            continue
        # A latest failed rerun must never fall back to an earlier successful attempt.
        selected = max(candidates, key=lambda run: (run.get('created_at', ''), run.get('id', 0)))
        summary = run_summary(selected, expected, sha)
        detail = api.get(PREFIX + '/actions/runs/' + str(summary['id']))
        if detail.get('id') != summary['id'] or detail.get('run_attempt', 0) < summary['run_attempt']:
            raise APIError('run_identity_mismatch')
        summary = run_summary(detail, expected, sha)
        summaries.append(summary)
        if summary['status'] != 'completed':
            pending.append('pending_workflow:' + str(expected['id']))
            continue
        if summary['conclusion'] != 'success':
            failed.append('failed_workflow:' + str(expected['id']))
            continue
        jobs = api.pages(PREFIX + f"/actions/runs/{summary['id']}/attempts/{summary['run_attempt']}/jobs", 'jobs')
        if not jobs or len(jobs) > 30:
            raise APIError('missing_or_excessive_jobs')
        summary['jobs'] = []
        for job in jobs:
            if (type(job.get('id')) is not int or job['id'] < 1 or not isinstance(job.get('name'), str)
                    or len(job['name']) > 160 or job.get('run_id', summary['id']) != summary['id']
                    or job.get('run_attempt', summary['run_attempt']) != summary['run_attempt']
                    or job.get('html_url') != f"https://github.com/{REPOSITORY}/actions/runs/{summary['id']}/job/{job['id']}"):
                raise APIError('job_identity_mismatch')
            summary['jobs'].append({key: job.get(key) for key in ('id', 'name', 'status', 'conclusion', 'html_url')})
            if job.get('status') != 'completed':
                pending.append('pending_job:' + str(job['id']))
            elif job.get('conclusion') != 'success':
                failed.append('failed_job:' + str(job['id']))
        after = run_summary(api.get(PREFIX + '/actions/runs/' + str(summary['id'])), expected, sha)
        if after['id'] != summary['id']:
            raise APIError('run_identity_mismatch')
        if after['run_attempt'] != summary['run_attempt'] or after['status'] != 'completed':
            pending.append('rerun_changed:' + str(summary['id']))
        elif after['conclusion'] != 'success':
            failed.append('rerun_failed:' + str(summary['id']))
    return summaries, pending, failed


def check(api, mapping, sha, timeout=1200, *, clock=time.monotonic, sleep=time.sleep):
    if not isinstance(sha, str) or not re.fullmatch(r'[a-f0-9]{40}', sha) or not 0 <= timeout <= 1200:
        raise ValueError('Expected an exact SHA and a timeout between 0 and 1200 seconds.')
    rows = valid_mapping(mapping)
    report = {'source_sha': sha, 'owner': 'Ethan Goldman', 'command': 'python3 cloud/check_workflows.py',
              'status': 'failed', 'workflows': [], 'issues': []}
    expires = clock() + timeout
    # --timeout 0 takes one bounded snapshot; positive timeouts bound every API call.
    api.deadline = time.monotonic() + (timeout if timeout else 60)
    try:
        while True:
            report['main_sha'] = main_sha(api)
            if report['main_sha'] != sha:
                report['status'] = 'superseded'
                break
            report['workflows'], pending, failed = snapshot(api, rows, sha)
            report['issues'] = failed + pending
            if main_sha(api) != sha:
                report['status'] = 'superseded'
                break
            if failed:
                break
            if not pending:
                report['status'] = 'passed'
                break
            if clock() >= expires:
                report['status'] = 'timed_out'
                break
            sleep(min(15, max(0, expires - clock())))
    except TimeoutError:
        report['status'] = 'timed_out'
        report['issues'].append('api_deadline')
    except APIError as error:
        report['issues'].append(error.code)
        report['status'] = 'failed'
    except (KeyError, TypeError, ValueError, AttributeError, RecursionError):
        report['issues'].append('api_or_capture_validation_failed')
        report['status'] = 'failed'
    report['captured_at'] = datetime.now(timezone.utc).isoformat()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sha', default=os.environ.get('GITHUB_SHA'))
    parser.add_argument('--timeout', type=int, default=1200)
    parser.add_argument('--head-only', action='store_true')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if os.environ.get('GITHUB_REPOSITORY', REPOSITORY) != REPOSITORY:
            raise ValueError('Wrong repository.')
        if not args.sha or not re.fullmatch(r'[a-f0-9]{40}', args.sha):
            raise ValueError('Missing source SHA.')
        api = GitHub(os.environ.get('GITHUB_TOKEN', ''))
        if args.head_only:
            actual = main_sha(api)
            report = {'source_sha': args.sha, 'main_sha': actual, 'status': 'current' if actual == args.sha else 'superseded',
                      'captured_at': datetime.now(timezone.utc).isoformat()}
        else:
            report = check(api, json.loads(MAPPING.read_text()), args.sha, args.timeout)
    except APIError as error:
        report = {'source_sha': args.sha, 'status': 'failed', 'issues': [error.code]}
    except (KeyError, TypeError, ValueError, OSError, RecursionError):
        report = {'source_sha': args.sha, 'status': 'failed', 'issues': ['gate_configuration_or_api_failed']}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    current = report['status'] in {'passed', 'current'}
    if os.environ.get('GITHUB_OUTPUT'):
        with Path(os.environ['GITHUB_OUTPUT']).open('a') as stream:
            stream.write('current=' + str(current).lower() + '\n')
    print(json.dumps(report, indent=2))
    return 0 if current or report['status'] == 'superseded' else 1


if __name__ == '__main__':
    raise SystemExit(main())
