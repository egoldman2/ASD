"""Protect the AWS boundary before any deployment code can run."""

from pathlib import Path

import yaml


def resources():
    source = Path(__file__).resolve().parents[1] / 'codebuild-deployment.yml'
    return yaml.load(source.read_text(), Loader=yaml.BaseLoader)['Resources']  # noqa: S506 - CFN tags become plain strings, lists and mappings only.


def test_runner_is_started_only_by_main_push_with_fixed_bootstrap():
    project = resources()['RunnerProject']['Properties']
    assert project['Triggers'] == {'Webhook': 'true', 'FilterGroups': [[
        {'Type': 'EVENT', 'Pattern': 'PUSH'},
        {'Type': 'HEAD_REF', 'Pattern': '^refs/heads/main$'}]]}
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
