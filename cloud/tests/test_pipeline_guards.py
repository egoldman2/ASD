"""Validate deployment trust/dependency boundaries in actual workflow structure."""

import json
from pathlib import Path
import shlex

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
MAPPING = json.loads((ROOT / 'cloud/student-workflows.json').read_text())['workflows']
FLAGS = ('AI_MODE_ENABLED', 'MCP_ENABLED', 'RAG_ENABLED', 'MULTI_AGENT_ENABLED')
OPT_INS = ('RUN_LIVE_AI', 'RUN_LIVE_MCP_AI', 'RUN_LIVE_RAG_AI', 'RUN_LIVE_VALIDATION',
           'RUN_LIVE_RELEASE1_VALIDATION', 'RUN_LIVE_MULTI_AGENT', 'RUN_NGINX_PROXY_CHECK')


def load(path):
    workflow = yaml.safe_load((ROOT / path).read_text())
    # PyYAML's YAML 1.1 parser treats GitHub's `on` key as True.
    workflow['on'] = workflow.pop(True)
    return workflow


@pytest.mark.parametrize('path', [row['path'] for row in MAPPING] + ['.github/workflows/cloud-deployment.yml'])
def test_real_workflows_disable_every_ai_flag_and_live_opt_in(path):
    workflow = load(path)
    assert all(workflow['env'][key] == 'false' for key in FLAGS)
    assert all(workflow['env'][key] == '0' for key in OPT_INS)


@pytest.mark.parametrize('path', [row['path'] for row in MAPPING] + ['.github/workflows/cloud-deployment.yml'])
def test_each_assigned_workflow_can_supply_every_main_sha(path):
    workflow = load(path)
    push = workflow['on']['push']
    assert 'main' in push['branches']
    assert 'paths' not in push and 'paths-ignore' not in push
    assert workflow['permissions'] == {'contents': 'read'}


@pytest.mark.parametrize('path', ['.github/workflows/Ryan.yml', '.github/workflows/student-3.yml'])
def test_existing_docker_test_commands_receive_all_disabled_flags(path):
    commands = [step['run'] for job in load(path)['jobs'].values() for step in job['steps']
                if 'run' in step and step['run'].startswith('docker run')]
    assert commands
    for command in commands:
        args = shlex.split(command)
        passed = {args[index + 1] for index, arg in enumerate(args[:-1]) if arg == '--env'}
        assert set(FLAGS + OPT_INS) <= passed


def test_cloud_deploy_requires_gate_matrix_build_main_and_fresh_candidate():
    workflow = load('.github/workflows/cloud-deployment.yml')
    jobs = workflow['jobs']
    gate = jobs['student_workflows']
    deploy = jobs['deploy']
    assert set(deploy['needs']) == {'validate', 'cloud-build', 'student_workflows'}
    assert "github.ref == 'refs/heads/main'" in deploy['if']
    assert "needs.student_workflows.outputs.current == 'true'" in deploy['if']
    assert gate['permissions'] == {'contents': 'read', 'actions': 'read'}
    assert 'actions' not in workflow['permissions'] and 'actions' not in deploy['permissions']
    assert deploy['permissions']['id-token'] == 'write' and deploy['environment'] == 'aws-cloud'
    assert int(gate['timeout-minutes']) <= 25
    assert ['ai-services/multi_agent_server/tests'] in jobs['validate']['strategy']['matrix']['suite']
    assert 'workflow_run' not in workflow['on']
    assert workflow['on']['pull_request']['branches'] == ['main']
    assert gate['if'] == "github.ref == 'refs/heads/main'"
    assert workflow['concurrency']['cancel-in-progress'] is False
    assert '${{ github.ref }}' in workflow['concurrency']['group']
    steps = deploy['steps']
    candidate = next(step for step in steps if step.get('id') == 'candidate')
    assert '--head-only' in candidate['run'] and 'cloud/check_workflows.py' in candidate['run']
    mutations = [step for step in steps if step.get('uses', '').startswith('aws-actions/')
                 or step.get('name') in {'Require configured deployment role', 'Publish and deploy validated release'}]
    assert len(mutations) == 3
    assert all(step['if'] == "steps.candidate.outputs.current == 'true'" for step in mutations)
    assert steps.index(candidate) < min(steps.index(step) for step in mutations)
    uploads = [step for step in gate['steps'] + steps if step.get('uses', '').startswith('actions/upload-artifact')]
    assert len(uploads) == 2 and all(step['if'] == 'always()' for step in uploads)
    assert all(step['with']['include-hidden-files'] is True for step in uploads)
