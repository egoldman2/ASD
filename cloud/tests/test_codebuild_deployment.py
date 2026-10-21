"""Protect the AWS boundary before any deployment code can run."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


def resources():
    source = Path(__file__).resolve().parents[1] / 'codebuild-deployment.yml'
    return yaml.load(source.read_text(), Loader=yaml.BaseLoader)['Resources']  # noqa: S506 - CFN tags become plain strings, lists and mappings only.


def test_runner_uses_api_build_credentials_and_fixed_bootstrap_without_a_webhook():
    project = resources()['RunnerProject']['Properties']
    assert project['Triggers'] == {'Webhook': 'false'}
    assert project['SourceVersion'] == 'main'
    assert project['Source']['Location'] == 'https://github.com/egoldman2/ASD'
    assert project['Source']['Auth'] == {'Type': 'CODECONNECTIONS', 'Resource': 'ConnectionArn'}
    buildspec = yaml.safe_load(project['Source']['BuildSpec'])
    assert buildspec['env'] == {'git-credential-helper': True}
    assert buildspec['phases'] == {'install': {'runtime-versions': {'python': 3.11}},
                                 'build': {'commands': ['python3 cloud/codebuild_runner.py run']}}
    assert project['Environment']['PrivilegedMode'] == 'false'
    assert 'EnvironmentVariables' not in project['Environment']
    assert project['ConcurrentBuildLimit'] == '1'
    assert project['TimeoutInMinutes'] == '90'
    assert project['Artifacts'] == {'Type': 'NO_ARTIFACTS'}
    logs = resources()['RunnerLogs']['Properties']
    assert logs['RetentionInDays'] == '7'
    assert project['LogsConfig'] == {'CloudWatchLogs': {'Status': 'ENABLED', 'GroupName': 'RunnerLogs'}}


def test_main_webhook_is_confined_to_a_fixed_relay_without_deployment_permissions():
    project = resources()['PushProject']['Properties']
    assert project['Triggers'] == {'Webhook': 'true', 'FilterGroups': [[
        {'Type': 'EVENT', 'Pattern': 'PUSH'},
        {'Type': 'HEAD_REF', 'Pattern': '^refs/heads/main$'}]]}
    assert project['SourceVersion'] == 'main'
    assert project['Environment']['PrivilegedMode'] == 'false'
    assert 'EnvironmentVariables' not in project['Environment']
    assert project['TimeoutInMinutes'] == project['QueuedTimeoutInMinutes'] == '5'
    assert 'env' not in yaml.safe_load(project['Source']['BuildSpec'])
    role = resources()['PushRole']['Properties']
    trust, = role['AssumeRolePolicyDocument']['Statement']
    assert trust['Principal'] == {'Service': 'codebuild.amazonaws.com'}
    assert trust['Condition'] == {
        'StringEquals': {'aws:SourceAccount': 'AWS::AccountId'},
        'ArnEquals': {'aws:SourceArn': 'arn:${AWS::Partition}:codebuild:${AWS::Region}:${AWS::AccountId}:project/${AWS::StackName}-push'}}
    policy, = role['Policies']
    grants = policy['PolicyDocument']['Statement']
    assert grants == [
        {'Effect': 'Allow', 'Action': ['codeconnections:GetConnection', 'codeconnections:GetConnectionToken'], 'Resource': 'ConnectionArn'},
        {'Effect': 'Allow', 'Action': ['logs:CreateLogStream', 'logs:PutLogEvents'], 'Resource': 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/codebuild/${AWS::StackName}:*'},
        {'Effect': 'Allow', 'Action': 'codebuild:StartBuild', 'Resource': 'RunnerProject.Arn'}]


@pytest.mark.parametrize('source,head,event,sha,checkout,remote,passed', [
    ('main', 'refs/heads/main', 'PUSH', 'a'*40, 'a'*40, 'a'*40, True),
    ('a'*40, None, None, 'a'*40, 'a'*40, 'a'*40, True),
    ('ethan-goldman', None, None, 'a'*40, 'a'*40, 'a'*40, False),
    ('main', 'refs/heads/ethan-goldman', 'PUSH', 'a'*40, 'a'*40, 'a'*40, False),
    ('main', 'refs/heads/main', 'PULL_REQUEST_CREATED', 'a'*40, 'a'*40, 'a'*40, False),
    ('main', None, None, 'invalid', 'a'*40, 'a'*40, False),
    ('main', None, None, 'a'*40, 'b'*40, 'a'*40, False),
    ('main', None, None, 'a'*40, 'a'*40, 'b'*40, False),
    ('main', None, None, 'a'*40, 'a'*40, '', False),
])
def test_relay_validates_context_and_current_main_before_starting_only_the_exact_sha(
        tmp_path, source, head, event, sha, checkout, remote, passed):
    buildspec = yaml.safe_load(resources()['PushProject']['Properties']['Source']['BuildSpec'])
    command, = buildspec['phases']['build']['commands']
    script = command.split("python3 - <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
    script = script.replace('${AWS::StackName}', 'asd-release2-actions')
    git = tmp_path / 'git'
    git.write_text('#!' + sys.executable + '\nimport os,sys\n'
                   "if sys.argv[1:] == ['rev-parse','HEAD']: print(os.environ['FIXTURE_CHECKOUT'])\n"
                   "elif sys.argv[1:] == ['ls-remote','https://github.com/egoldman2/ASD.git','refs/heads/main']: print(os.environ['FIXTURE_REMOTE'])\n"
                   "else: raise SystemExit(2)\n")
    git.chmod(0o700)
    aws = tmp_path / 'aws'
    aws.write_text('#!' + sys.executable + '\nimport json,os,pathlib,sys\n'
                   "pathlib.Path(os.environ['FIXTURE_CALL']).write_text(json.dumps(sys.argv[1:]))\n"
                   "print(json.dumps({'build':{'id':'asd-release2-actions-deploy:fixture'}}))\n")
    aws.chmod(0o700)
    call = tmp_path / 'call.json'
    environment = {**os.environ, 'PATH': str(tmp_path)+os.pathsep+os.environ['PATH'],
                   'CODEBUILD_SOURCE_VERSION': source, 'CODEBUILD_RESOLVED_SOURCE_VERSION': sha,
                   'FIXTURE_CHECKOUT': checkout, 'FIXTURE_REMOTE': remote, 'FIXTURE_CALL': str(call)}
    for key, value in {'CODEBUILD_WEBHOOK_HEAD_REF': head, 'CODEBUILD_WEBHOOK_EVENT': event}.items():
        environment.pop(key, None)
        if value is not None:
            environment[key] = value
    result = subprocess.run([sys.executable, '-c', script], env=environment, capture_output=True, text=True, timeout=5)  # noqa: S603 - Owned inline buildspec runs only local Git/AWS fixtures.
    assert (result.returncode == 0) is passed
    assert call.exists() is passed
    if passed:
        assert json.loads(call.read_text()) == [
            'codebuild', 'start-build', '--project-name', 'asd-release2-actions-deploy',
            '--source-version', sha, '--region', 'ap-southeast-2', '--output', 'json']


def test_role_has_one_project_trust_and_only_release_host_permissions():
    role = resources()['RunnerRole']['Properties']
    trust, = role['AssumeRolePolicyDocument']['Statement']
    assert trust['Principal'] == {'Service': 'codebuild.amazonaws.com'}
    assert trust['Condition'] == {
        'StringEquals': {'aws:SourceAccount': 'AWS::AccountId'},
        'ArnEquals': {'aws:SourceArn': 'arn:${AWS::Partition}:codebuild:${AWS::Region}:${AWS::AccountId}:project/${AWS::StackName}-deploy'}}
    policy, = role['Policies']
    actions = {}
    for grant in policy['PolicyDocument']['Statement']:
        assert grant['Effect'] == 'Allow'
        for action in grant['Action'] if isinstance(grant['Action'], list) else [grant['Action']]:
            assert action not in actions
            actions[action] = grant['Resource']
    assert actions == {
        'codeconnections:GetConnection': 'ConnectionArn',
        'codeconnections:GetConnectionToken': 'ConnectionArn',
        'logs:CreateLogStream': 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/codebuild/${AWS::StackName}:*',
        'logs:PutLogEvents': 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/codebuild/${AWS::StackName}:*',
        's3:PutObject': '${ReleaseBucketArn}/releases/*',
        'ssm:SendCommand': ['arn:${AWS::Partition}:ssm:${AWS::Region}::document/AWS-RunShellScript',
                            'arn:${AWS::Partition}:ec2:${AWS::Region}:${AWS::AccountId}:instance/${InstanceId}'],
        'ssm:GetCommandInvocation': '*',
        'cloudformation:DescribeStacks': 'arn:${AWS::Partition}:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/${ApplicationStack}/*'}
