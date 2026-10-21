"""Keep the connection probe isolated from deployment credentials and PR jobs."""

import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

TEMPLATE = Path(__file__).resolve().parents[1] / 'codebuild-source.yml'


def template():
    return yaml.load(TEMPLATE.read_text(), Loader=yaml.BaseLoader)  # noqa: S506 - CFN tags become plain strings, lists and mappings only.


def test_source_probe_has_only_connection_access_and_no_runner_webhook():
    resources = template()['Resources']
    role = resources['SourceRole']['Properties']
    trust, = role['AssumeRolePolicyDocument']['Statement']
    assert trust['Principal'] == {'Service': 'codebuild.amazonaws.com'}
    assert trust['Condition']['StringEquals'] == {'aws:SourceAccount': 'AWS::AccountId'}
    assert trust['Condition']['ArnEquals']['aws:SourceArn'].endswith('project/${AWS::StackName}-source')
    policy, = role['Policies']
    grant, = policy['PolicyDocument']['Statement']
    assert grant == {'Effect': 'Allow', 'Action': ['codeconnections:GetConnection', 'codeconnections:GetConnectionToken'], 'Resource': 'ConnectionArn'}
    project = resources['SourceProject']['Properties']
    assert project['SourceVersion'] == 'main'
    assert project['Source']['Location'] == 'https://github.com/egoldman2/ASD'
    assert project['Source']['Auth'] == {'Type': 'CODECONNECTIONS', 'Resource': 'ConnectionArn'}
    assert project['Environment']['PrivilegedMode'] == 'false'
    assert project['ConcurrentBuildLimit'] == '1'
    assert project['TimeoutInMinutes'] == project['QueuedTimeoutInMinutes'] == '5'
    assert 'Triggers' not in project
    assert project['Artifacts'] == {'Type': 'NO_ARTIFACTS'}


@pytest.mark.parametrize('branch,head,resolved,passed', [
    ('main', 'a' * 40, 'a' * 40, True),
    ('ethan-goldman', 'a' * 40, 'a' * 40, False),
    ('main', 'b' * 40, 'a' * 40, False),
    ('main', 'a' * 40, 'b' * 40, False),
])
def test_probe_rejects_an_unexpected_branch_or_commit(tmp_path, branch, head, resolved, passed):
    buildspec = yaml.safe_load(template()['Resources']['SourceProject']['Properties']['Source']['BuildSpec'])
    command, = buildspec['phases']['build']['commands']
    script = command.split("python3 - <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
    git = tmp_path / 'git'
    git.write_text('#!' + sys.executable + '\nprint(' + repr(head) + ')\n')
    git.chmod(0o700)
    environment = {**os.environ, 'PATH': str(tmp_path) + os.pathsep + os.environ['PATH'],
                   'EXPECTED_MAIN_SHA': 'a' * 40, 'CODEBUILD_SOURCE_VERSION': branch,
                   'CODEBUILD_RESOLVED_SOURCE_VERSION': resolved}
    result = subprocess.run([sys.executable, '-c', script], env=environment, capture_output=True, text=True, timeout=5)  # noqa: S603 - Fixed interpreter executes the owned template probe with an owned Git fixture.
    assert (result.returncode == 0) is passed
    assert ('Verified main source:' in result.stdout) is passed
