"""Verify the actual template trust and provisioning argv without AWS access."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = 'egoldman2@200193881/ASD@1326270780'


def template():
    return yaml.load((ROOT / 'cloud/infrastructure.yml').read_text(), Loader=yaml.BaseLoader)  # noqa: S506 - BaseLoader ignores CFN tags and constructs only strings/lists/maps, never Python objects.


def test_default_role_trust_matches_verified_immutable_repository_and_environment():
    config = template()
    repository = config['Parameters']['GitHubRepository']
    assert repository['Default'] == IDENTITY
    assert re.fullmatch(repository['AllowedPattern'], IDENTITY)
    assert config['Parameters']['EnableGitHubOidc']['Default'] == 'false'
    role = config['Resources']['DeployRole']
    assert role['Condition'] == 'GitHubOidcEnabled'
    statements = role['Properties']['AssumeRolePolicyDocument']['Statement']
    assert len(statements) == 1
    assert statements[0]['Action'] == 'sts:AssumeRoleWithWebIdentity'
    condition = statements[0]['Condition']
    assert set(condition) == {'StringEquals'}
    assert condition['StringEquals'] == {
        'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com',
        'token.actions.githubusercontent.com:sub': 'repo:${GitHubRepository}:environment:aws-cloud',
    }


@pytest.mark.parametrize('identity', [
    'egoldman2/ASD', 'egoldman2@200193881/ASD', 'egoldman2/ASD@1326270780',
    'egoldman2@*/ASD@*', 'egoldman2@0/ASD@1326270780',
    IDENTITY + ':environment:other', IDENTITY + ':ref:refs/heads/main',
])
def test_template_rejects_legacy_wildcard_missing_or_additional_identity_context(identity):
    assert re.fullmatch(template()['Parameters']['GitHubRepository']['AllowedPattern'], identity) is None


@pytest.fixture
def provision(tmp_path):
    calls = tmp_path / 'calls.jsonl'
    aws = tmp_path / 'aws'
    aws.write_text('#!' + sys.executable + '\n' + '''import json,os,sys
args=sys.argv[1:]
with open(os.environ['AWS_FIXTURE_CALLS'],'a') as stream:stream.write(json.dumps(args)+'\\n')
if args[:2]==['freetier','get-account-plan-state']:print('FREE')
elif args[:2]==['ec2','describe-instance-types']:print('True')
elif args[:2]==['ec2','describe-managed-prefix-lists']:print('pl-12345678')
elif args[:2]==['cloudformation','describe-stacks']:print('[]')
''')
    aws.chmod(0o700)

    def run(**values):
        environment = {key: value for key, value in os.environ.items()
                       if key not in {'AWS_PROFILE', 'GITHUB_OIDC_REPOSITORY_IDENTITY', 'ENABLE_GITHUB_OIDC'}}
        environment.update(PATH=str(tmp_path) + os.pathsep + os.environ['PATH'],
                           AWS_FIXTURE_CALLS=str(calls), **values)
        result = subprocess.run(['/bin/bash', str(ROOT / 'cloud/provision.sh')],  # noqa: S603 - Fixed Bash/project script; AWS is replaced by an owned local fixture.
                                env=environment, capture_output=True, text=True, timeout=15)
        recorded = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
        return result, recorded
    return run


@pytest.mark.parametrize('identity', ['egoldman2/ASD', 'owner@*/repo@*', IDENTITY + ':environment:other'])
def test_invalid_identity_stops_before_any_aws_request(provision, identity):
    result, calls = provision(GITHUB_OIDC_REPOSITORY_IDENTITY=identity)
    assert result.returncode != 0
    assert calls == []
    assert 'GITHUB_OIDC_REPOSITORY_IDENTITY' in result.stderr


@pytest.mark.parametrize('overrides,identity,profile', [
    ({}, IDENTITY, 'aws-toolkit'),
    ({'GITHUB_OIDC_REPOSITORY_IDENTITY': 'other-owner@123/repo@456',
      'AWS_PROFILE': 'teammate-fixture', 'ENABLE_GITHUB_OIDC': 'true'},
     'other-owner@123/repo@456', 'teammate-fixture'),
])
def test_explicit_identity_profile_and_region_reach_every_provisioning_call(provision, overrides, identity, profile):
    result, calls = provision(**overrides)
    assert result.returncode == 0, result.stderr
    assert len(calls) == 6
    assert all(row[row.index('--profile') + 1] == profile for row in calls)
    assert all(row[row.index('--region') + 1] == 'ap-southeast-2' for row in calls)
    deploy = next(row for row in calls if row[:2] == ['cloudformation', 'deploy'])
    assert 'GitHubRepository=' + identity in deploy
    assert ('EnableGitHubOidc=' + overrides.get('ENABLE_GITHUB_OIDC', 'false')) in deploy
