#!/usr/bin/env bash
# Invoked through Systems Manager on the provisioned EC2 host.
set -euo pipefail
umask 077
release_dir=$(cd "$(dirname "$0")/.." && pwd)
exec 9>/srv/asd/deploy.lock
flock -n 9 || { echo 'Another deployment is running.' >&2; exit 1; }
test -f /srv/asd/bootstrap-ready
test "$release_dir" != /srv/asd
mkdir -p /srv/asd/data/{accounts,products,orders,support}
python3 - "$release_dir" "$@" <<'PY'
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
from urllib.parse import urlsplit

directory, release_id, public_url, origin_arn, password_arn, region = sys.argv[1:]
url = urlsplit(public_url)
if url.scheme != 'https' or not url.hostname or url.path or url.query or url.fragment or url.username:
    raise ValueError('Expected an HTTPS public origin.')
if region != 'ap-southeast-2' or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}', release_id):
    raise ValueError('Invalid release or Region.')

def secret(arn):
    value = subprocess.check_output([
        'aws', 'secretsmanager', 'get-secret-value', '--secret-id', arn,
        '--region', region, '--query', 'SecretString', '--output', 'text',
    ], text=True).strip()
    if not re.fullmatch(r'[a-zA-Z0-9]{24,128}', value):
        raise ValueError('Secret must be a generated alphanumeric value.')
    return value

session_path = Path('/srv/asd/session-secret')
if not session_path.exists():
    session_path.write_text(secrets.token_hex(32))
session_path.chmod(0o600)
values = {
    'RELEASE_ID': release_id, 'PUBLIC_ORIGIN': public_url,
    'DATA_ROOT': '/srv/asd/data', 'SESSION_SECRET': session_path.read_text().strip(),
    'ORIGIN_TOKEN': secret(origin_arn), 'SEED_PASSWORD': secret(password_arn),
    'GATEWAY_BIND': '0.0.0.0', 'GATEWAY_PORT': '80',
}
env_path = Path(directory) / 'cloud.env'
env_path.write_text(''.join(f'{key}={value}\n' for key, value in values.items()))
env_path.chmod(0o600)
PY
previous=$(readlink -f /srv/asd/current 2>/dev/null || true)
compose=(docker compose --project-name asd-cloud --env-file "$release_dir/cloud.env" --file "$release_dir/cloud/compose.yml")
if ! "${compose[@]}" up -d --build --wait --wait-timeout 240; then
  echo 'Deployment failed; attempting to restore the previous release.' >&2
  if [ -n "$previous" ] && [ -f "$previous/cloud.env" ]; then
    docker compose --project-name asd-cloud --env-file "$previous/cloud.env" --file "$previous/cloud/compose.yml" up -d --wait --wait-timeout 240
  fi
  exit 1
fi
# Test the actual gateway, authentication, CRUD, and disabled services before accepting a release.
if ! python3 "$release_dir/cloud/smoke.py" http://127.0.0.1 --env-file "$release_dir/cloud.env"; then
  echo 'Release checks failed; attempting to restore the previous release.' >&2
  if [ -n "$previous" ] && [ -f "$previous/cloud.env" ]; then
    docker compose --project-name asd-cloud --env-file "$previous/cloud.env" --file "$previous/cloud/compose.yml" up -d --wait --wait-timeout 240
  fi
  exit 1
fi
ln -s "$release_dir" /srv/asd/current.next
mv -Tf /srv/asd/current.next /srv/asd/current
echo "Release $1 accepted. Database directories preserved."
