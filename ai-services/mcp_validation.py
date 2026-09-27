"""Bounded read-only protocol and application probes for a configured feature."""

import hashlib
import json
import math
import os
import re
from urllib.parse import urlsplit

import requests
from shared.feature_flags import feature_enabled


MAX_PROBES = 10
PRIVATE_KEYS = {'cookie', 'authorization', 'password', 'password_hash', 'secret', 'token', 'ethan_session',
                'customer_user_id', 'customer_name_snapshot', 'customer_email_snapshot', 'customer_phone_snapshot',
                'author_name', 'subject',
                'message', 'content'}
LOCAL_HOSTS = {'localhost', '127.0.0.1', '::1', 'host.docker.internal'}


class ProbeConfigurationError(ValueError):
    pass


def local_url(value):
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {'http', 'https'} or parsed.hostname not in LOCAL_HOSTS
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError()
        parsed.port
    except (ValueError, TypeError, AttributeError):
        raise ProbeConfigurationError('Probe URLs must identify a local service without credentials or query parameters.') from None
    return value.rstrip('/')


def bounded_timeout(value, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= maximum:
        raise ProbeConfigurationError('Probe timeout is outside its permitted range.')
    return value


def request_context(rules):
    context = rules.get('request_context', {})
    if not isinstance(context, dict) or set(context) - {'cookie_env', 'cookie_name'}:
        raise ProbeConfigurationError('Unsupported probe request context.')
    if not context:
        return {}, []
    name, variable = context.get('cookie_name'), context.get('cookie_env')
    if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,60}', name)
            or not isinstance(variable, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,79}', variable)):
        raise ProbeConfigurationError('Cookie context must name an environment variable and cookie.')
    value = os.getenv(variable, '')
    if not value or len(value) > 4096 or any(char in value for char in '\r\n;'):
        raise ProbeConfigurationError('The configured staff session environment variable is missing or invalid.')
    return {'Cookie': name + '=' + value}, [value]


def public_evidence(value, secrets=(), depth=0):
    """Keep bounded audit data; credentials and private conversation fields stay out."""
    if depth > 9:
        return '<bounded>'
    if isinstance(value, dict):
        if isinstance(value.get('path'), str) and value['path'].split('.')[-1].casefold() in PRIVATE_KEYS:
            value = {**value, 'value': '<redacted>', 'observed': '<redacted>', 'expected': '<redacted>'}
        return {str(key): '<redacted>' if str(key).casefold() in PRIVATE_KEYS else public_evidence(item, secrets, depth + 1)
                for key, item in list(value.items())[:60]}
    if isinstance(value, list):
        return [public_evidence(item, secrets, depth + 1) for item in value[:50]]
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, '<redacted>')
        value = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '<email>', value)
        value = re.sub(r'(?<!\w)\+?\d[\d ()-]{7,}\d(?!\w)', '<phone>', value)
        return value[:2000]
    return value


def lookup(data, path):
    if not isinstance(path, str) or not 1 <= len(path) <= 200:
        raise ValueError('Invalid evidence path')
    for component in path.split('.'):
        if isinstance(data, dict):
            data = data[component]
        elif isinstance(data, list) and re.fullmatch(r'[0-9]{1,4}', component):
            data = data[int(component)]
        else:
            raise ValueError('Invalid evidence path')
    return data


def expectations(payload, configured):
    if not isinstance(configured, list) or len(configured) > 30:
        raise ProbeConfigurationError('Expected values must be a bounded list.')
    results = []
    for check in configured:
        if not isinstance(check, dict) or set(check) != {'path', 'value'}:
            raise ProbeConfigurationError('Expected values require a path and value.')
        try:
            actual = lookup(payload, check['path'])
            passed = type(actual) is type(check['value']) and actual == check['value']
        except (ValueError, KeyError, IndexError, TypeError):
            actual, passed = '<missing>', False
        results.append({'path': check['path'], 'expected': check['value'], 'observed': actual, 'passed': passed})
    return results


def probes_for(rules, key, singular):
    probes = rules.get(key)
    if probes is None:
        probes = [rules[singular]] if singular in rules else []
    if not isinstance(probes, list) or len(probes) > MAX_PROBES:
        raise ProbeConfigurationError('Too many configured probes.')
    if any(not isinstance(probe, dict) for probe in probes):
        raise ProbeConfigurationError('Each configured probe must be an object.')
    return probes


def read_json(method, url, *, payload=None, headers=None, timeout=5):
    """Send only bounded local requests; redirects cannot carry credentials elsewhere."""
    url = local_url(url)
    if method not in {'GET', 'POST'}:
        raise ProbeConfigurationError('Unsupported probe HTTP method.')
    if payload is not None and len(json.dumps(payload)) > 4096:
        raise ProbeConfigurationError('Probe request exceeds its size limit.')
    with requests.request(method, url, json=payload, headers=headers or {}, timeout=timeout,
                          stream=True, allow_redirects=False) as response:
        raw = bytearray()
        for chunk in response.iter_content(4096):
            raw.extend(chunk)
            if len(raw) > 256 * 1024:
                raise ValueError('Probe response exceeds its size limit')
        return response.status_code, json.loads(raw)


def assistant_trace(payload, required_tools, expected_tools):
    """Verify returned model/tool observations and exact scalar fact references."""
    if not isinstance(payload, dict) or payload.get('status') != 'answered':
        return False
    observations, facts = payload.get('observations'), payload.get('facts')
    if (not isinstance(payload.get('model'), str) or not 1 <= len(payload['model']) <= 160
            or not isinstance(payload.get('answer'), str) or not 1 <= len(payload['answer']) <= 2000
            or type(payload.get('model_requests')) is not int or not 2 <= payload['model_requests'] <= 4
            or type(payload.get('tool_calls')) is not int or not 1 <= payload['tool_calls'] <= 3
            or not isinstance(observations, list) or len(observations) != payload['tool_calls']
            or not isinstance(facts, list) or not 1 <= len(facts) <= 12
            or not isinstance(expected_tools, list) or not expected_tools
            or any(not isinstance(name, str) for name in expected_tools)
            or not set(expected_tools).issubset(required_tools)):
        return False
    names = set()
    for index, observation in enumerate(observations):
        if (not isinstance(observation, dict) or type(observation.get('call_index')) is not int
                or observation['call_index'] != index or not isinstance(observation.get('tool'), str)
                or observation.get('tool') not in required_tools or not isinstance(observation.get('arguments'), dict)
                or not isinstance(observation.get('result'), dict)):
            return False
        names.add(observation['tool'])
    if not set(expected_tools).issubset(names):
        return False
    for fact in facts:
        try:
            if not isinstance(fact, dict) or set(fact) != {'call_index', 'path', 'value'}:
                return False
            index = fact['call_index']
            if type(index) is not int or not 0 <= index < len(observations):
                return False
            actual = lookup(observations[index]['result'], fact['path'])
            if isinstance(actual, (dict, list)) or type(actual) is not type(fact['value']) or actual != fact['value']:
                return False
        except (KeyError, IndexError, ValueError, TypeError):
            return False
    return True


def probe_runtime(config):
    if not feature_enabled('MCP_ENABLED'):
        raise ProbeConfigurationError('MCP_ENABLED disables live validation.')
    # Database/source review modes can run without installing the host MCP SDK.
    from shared.mcp_client import MCPClient, MCPClientSettings
    rules = config.get('mcp_rules', {})
    required = rules.get('required_tools', [])
    if (not isinstance(required, list) or not 1 <= len(required) <= 20
            or any(not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]{1,100}', name) for name in required)
            or len(set(required)) != len(required)):
        raise ProbeConfigurationError('Configure a nonempty feature tool allowlist.')
    url = local_url(os.getenv('MCP_SERVER_URL', config.get('mcp_server_url', 'http://127.0.0.1:8765/mcp')))
    headers, secrets = request_context(rules)
    settings = MCPClientSettings(enabled=True, server_url=url,
                                 timeout_seconds=bounded_timeout(rules.get('timeout_seconds', 5), 30))
    client = MCPClient(settings=settings, allowed_tools=frozenset(required))
    tools = client.list_tools(request_headers=headers)
    by_name = {tool['name']: tool for tool in tools}
    runtime = {'available': True, 'tools': tools, 'tool_names': sorted(by_name), 'probes': [], 'assistant_probes': []}
    legacy = {'tool': rules['probe_tool'], 'arguments': rules.get('probe_arguments', {})} if rules.get('probe_tool') else None
    probes = probes_for(rules, 'probes', 'probe')
    if not probes and legacy:
        probes = [legacy]
    for index, probe in enumerate(probes):
        tool = probe.get('tool')
        arguments = probe.get('arguments', {})
        observation = {'name': probe.get('name', f'read-{index + 1}'), 'tool': tool, 'arguments': arguments,
                       'success': False, 'read_only': False, 'checks_passed': False}
        try:
            if (set(probe) - {'name', 'tool', 'arguments', 'expect'} or tool not in required
                    or not isinstance(arguments, dict) or len(json.dumps(arguments)) > 4096
                    or any(key.casefold() in PRIVATE_KEYS - {'subject', 'message', 'content'} for key in arguments)):
                raise ProbeConfigurationError('Invalid read-only probe arguments.')
            annotations = by_name.get(tool, {}).get('annotations') or {}
            if annotations.get('readOnlyHint') is not True or annotations.get('destructiveHint') is not False:
                raise ProbeConfigurationError('Probe tool lacks read-only, non-destructive discovery annotations.')
            observation['read_only'] = True
            payload = client.call_tool(tool, arguments, request_headers=headers)
            observation.update(response_tool=payload.get('tool'),
                success=(payload.get('success') is True and payload.get('tool') == tool
                         and payload.get('metadata', {}).get('read_only') is True and isinstance(payload.get('result'), dict)))
            observation['checks'] = expectations(payload, probe.get('expect', []))
            observation['checks_passed'] = all(check['passed'] for check in observation['checks'])
            observation['response_digest'] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            if not observation['success']:
                error = payload.get('error')
                observation['error_code'] = error.get('code', 'INVALID_TOOL_RESPONSE') if isinstance(error, dict) else 'INVALID_TOOL_RESPONSE'
        except Exception as exc:
            observation['error'] = type(exc).__name__
        runtime['probes'].append(observation)
    if legacy and runtime['probes']:
        runtime['probe'] = runtime['probes'][0]
    for index, probe in enumerate(probes_for(rules, 'assistant_probes', 'assistant_probe')):
        observation = {'name': probe.get('name', f'assistant-{index + 1}'), 'attempted': False, 'verified': False}
        try:
            if set(probe) - {'name', 'url', 'origin', 'payload', 'expected_tools', 'expect', 'timeout_seconds'}:
                raise ProbeConfigurationError('Unsupported assistant probe fields.')
            if not feature_enabled():
                observation['skip_reason'] = 'AI_MODE_ENABLED disables application assistant validation.'
            else:
                target, origin = local_url(probe['url']), local_url(probe['origin'])
                body = probe.get('payload')
                if (not urlsplit(target).path.endswith('/mcp/assistant') or urlsplit(origin).path not in {'', '/'}
                        or not isinstance(body, dict) or set(body) - {'question', 'ticket_id'}
                        or not isinstance(body.get('question'), str) or not 1 <= len(body['question'].strip()) <= 1000
                        or ('ticket_id' in body and (type(body['ticket_id']) is not int or not 1 <= body['ticket_id'] <= 2**63 - 1))):
                    raise ProbeConfigurationError('Assistant probes require a local read-only MCP question endpoint.')
                observation['attempted'] = True
                status, payload = read_json('POST', target, payload=body,
                    headers={**headers, 'Origin': origin}, timeout=bounded_timeout(probe.get('timeout_seconds', 95), 95))
                observation.update(http_status=status, response=payload)
                observation['checks'] = expectations(payload, probe.get('expect', []))
                observation['verified'] = (status == 200 and assistant_trace(payload, set(required), probe.get('expected_tools', []))
                                           and all(check['passed'] for check in observation['checks']))
        except Exception as exc:
            observation['error'] = type(exc).__name__
        runtime['assistant_probes'].append(observation)
    return public_evidence(runtime, secrets)
