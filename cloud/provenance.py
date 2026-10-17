"""Capture bounded release evidence on the host without exporting private config."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

FLAGS = ('AI_MODE_ENABLED', 'MCP_ENABLED', 'RAG_ENABLED', 'MULTI_AGENT_ENABLED')
ARTIFACTS = ('local-smoke.json', 'public-smoke.json', 'runtime.json')
PHASES = ('configuration', 'candidate', 'build', 'local_smoke', 'public_smoke', 'runtime', 'acceptance')
API_SERVICES = {'shared-backend', 'ethan-backend', 'inventory-backend', 'customer-support-backend'}
AI_SERVICE_PATTERN = r'ollama|multi[-_]?agent|(?:mcp|rag)[-_]?server|(?:^|[-_])(?:mcp|rag)(?:$|[-_])'


def stamp():
    return datetime.now(timezone.utc).isoformat()


def metadata(directory):
    value = json.loads((directory / 'source-metadata.json').read_text())
    if not (re.fullmatch(r'[a-f0-9]{40}', value['source_sha'])
            and re.fullmatch(r'[a-f0-9]{64}', value['source_sha256'])
            and re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}', value['release_id'])
            and re.fullmatch(r'i-(?:[a-f0-9]{8}|[a-f0-9]{17})', value['target_instance'])
            and value['region'] == 'ap-southeast-2'):
        raise ValueError('Invalid release identity.')
    url = urlsplit(value['public_url'])
    if (url.scheme != 'https' or not url.hostname or url.port not in {None, 443}
            or url.path not in {'', '/'} or url.query or url.fragment or url.username or url.password):
        raise ValueError('Invalid public origin.')
    return {key: value[key] for key in ('source_sha', 'source_sha256', 'release_id', 'public_url', 'target_instance', 'region')}


def command(*args):
    return subprocess.check_output(args, text=True, timeout=30)  # noqa: S603 - Only fixed Docker subcommands and inspected container IDs supplied below; no shell.


def runtime(directory, current=Path('/srv/asd/current')):
    identity = metadata(directory)
    compose = ('docker', 'compose', '--project-name', 'asd-cloud', '--env-file', str(directory / 'cloud.env'), '--file', str(directory / 'cloud/compose.yml'))
    expected = set(command(*compose, 'config', '--services').split())
    ids = command(*compose, 'ps', '-q').split()
    services, observed_flags = [], []
    for identifier in ids:
        if not re.fullmatch(r'[a-f0-9]{12,64}', identifier):
            raise ValueError('Invalid container identifier.')
        row, = json.loads(command('docker', 'inspect', identifier))
        if row['State']['Status'] != 'running' or row['State'].get('Health', {}).get('Status', 'healthy') != 'healthy':
            raise ValueError('A release container is unhealthy.')
        service = row['Config']['Labels']['com.docker.compose.service']
        services.append(service)
        env = dict(item.split('=', 1) for item in row['Config']['Env'] if '=' in item)
        if service in API_SERVICES or set(FLAGS) & env.keys():
            observed_flags.append({key: env.get(key) for key in FLAGS})
    all_names = command('docker', 'ps', '--format', '{{.Names}}').splitlines()
    ports = set()
    for path in (Path('/proc/net/tcp'), Path('/proc/net/tcp6')):
        for line in path.read_text().splitlines()[1:]:
            fields = line.split()
            if fields[3] == '0A':
                ports.add(int(fields[1].rsplit(':', 1)[1], 16))
    if (not expected or len(services) != len(expected) or set(services) != expected
            or not observed_flags or not all(all(row[key] == 'false' for key in FLAGS) for row in observed_flags)
            or not all_names or any(re.search(AI_SERVICE_PATTERN, name, re.I) for name in [*services, *all_names])
            or not ports or {11434, 8765, 5003, 5004} & ports):
        raise ValueError('Running release does not establish the disabled baseline.')
    report = {**identity, 'owner': 'Ethan Goldman', 'captured_at': stamp(),
              'command': 'SSM: Docker inspect and host /proc/net/tcp{,6}',
              'origin': 'ssm-runtime', 'current_release': str(current.resolve()),
              'ai_flags': {key: 'false' for key in FLAGS},
              'service_names': sorted(services), 'listening_ports': sorted(ports),
              'checked_running_container_count': len(all_names)}
    (directory / 'runtime.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def finish(directory, passed, phase, current=Path('/srv/asd/current')):
    identity = metadata(directory)
    refs, captures = {}, {}
    for name in ARTIFACTS:
        path = directory / name
        if not path.exists():
            continue
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise ValueError('Invalid evidence artifact.')
        data = path.read_bytes()
        refs[name] = {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest()}
        captures[name] = json.loads(data)
    accepted = passed and phase == 'acceptance' and current.resolve() == directory.resolve()
    for name, base in (('local-smoke.json', 'http://127.0.0.1'), ('public-smoke.json', identity['public_url'])):
        smoke = captures.get(name, {})
        accepted &= (smoke.get('source_sha') == identity['source_sha'] and smoke.get('release_id') == identity['release_id']
                     and smoke.get('base_url') == base and smoke.get('status') == smoke.get('cleanup_status') == 'passed'
                     and bool(smoke.get('checks')) and all(row.get('passed') is True for row in smoke['checks']))
    live = captures.get('runtime.json', {})
    accepted &= (live.get('source_sha') == identity['source_sha'] and live.get('source_sha256') == identity['source_sha256']
                 and live.get('release_id') == identity['release_id'] and live.get('current_release') == str(directory.resolve()))
    report = {**identity, 'owner': 'Ethan Goldman', 'captured_at': stamp(),
              'command': 'SSM: cloud/install.sh; local and public cloud/smoke.py; cloud/provenance.py',
              'acceptance': 'passed' if accepted else 'failed', 'phase': phase,
              'current_release': str(current.resolve()), 'artifact_refs': refs,
              'rollback_limit': 'Code rollback preserves database changes; it does not restore a database snapshot.'}
    (directory / 'deployment-result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def export(directory):
    report = json.loads((directory / 'deployment-result.json').read_text())
    # Native checks stay on the host; S16 retrieves the hash-checked files via SSM.
    for name, ref in report['artifact_refs'].items():
        if name not in ARTIFACTS:
            raise ValueError('Invalid artifact name.')
        path = directory / name
        if path.is_symlink() or path.stat().st_size > 1024 * 1024 or hashlib.sha256(path.read_bytes()).hexdigest() != ref['sha256']:
            raise ValueError('Evidence changed after finalization.')
    payload = json.dumps({'result': report}, separators=(',', ':'))
    if len(payload.encode()) > 22000:
        raise ValueError('Evidence exceeds safe SSM output limit.')
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('runtime', 'finish', 'export'))
    parser.add_argument('directory', type=Path)
    parser.add_argument('--passed', action='store_true')
    parser.add_argument('--phase', choices=PHASES, default='configuration')
    args = parser.parse_args()
    if args.mode == 'runtime':
        runtime(args.directory)
    elif args.mode == 'finish':
        result = finish(args.directory, args.passed, args.phase)
        return 0 if not args.passed or result['acceptance'] == 'passed' else 1
    else:
        print(export(args.directory))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
