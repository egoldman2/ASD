"""Scoped HTTP RAG probes; importing review modes needs no Chroma/model runtime."""

import os
import re
from urllib.parse import urlsplit

from shared.feature_flags import feature_enabled
from mcp_validation import ProbeConfigurationError, bounded_timeout, expectations, local_url, probes_for, public_evidence, read_json

OPERATIONS = {'refresh_corpus', 'retrieve_context', 'answer_question'}
INSUFFICIENT_ANSWER = 'Insufficient context to answer this question.'
CITATION = re.compile(r'\[(\d+)\]')


def configured_probes(rules):
    probes = probes_for(rules, 'probes', 'probe')
    if not probes and rules.get('probe_question'):
        probes = [{'name': 'supported', 'question': rules['probe_question'], 'top_k': rules.get('probe_top_k', 5), 'expected': 'grounded'}]
        if rules.get('unsupported_question'):
            probes.append({'name': 'unsupported', 'question': rules['unsupported_question'], 'top_k': rules.get('probe_top_k', 5), 'expected': 'insufficient'})
    if not probes:
        raise ProbeConfigurationError('Configure a supported and unsupported RAG question.')
    return probes


def envelope(payload, operation, scope):
    return (isinstance(payload, dict) and payload.get('success') is True and payload.get('operation') == operation
            and payload.get('error') is None and isinstance(payload.get('data'), dict)
            and payload['data'].get('scope') == scope and isinstance(payload.get('citations'), list)
            and isinstance(payload.get('metadata'), dict) and type(payload.get('insufficient_context')) is bool)


def valid_retrieval(payload, scope, question, top_k):
    if not envelope(payload, 'retrieve_context', scope):
        return False
    data, citations = payload['data'], payload['citations']
    rows = data.get('results')
    if (data.get('query') != question or not isinstance(rows, list) or len(rows) > top_k
            or type(data.get('result_count')) is not int or data['result_count'] != len(rows)
            or len(citations) != len(rows) or type(payload['metadata'].get('requested_top_k')) is not int
            or payload['metadata']['requested_top_k'] != top_k):
        return False
    if not rows:
        return payload['insufficient_context'] and payload.get('confidence') == 'insufficient'
    if payload['insufficient_context'] or payload.get('confidence') not in {'high', 'medium', 'low'}:
        return False
    document_ids = set()
    for rank, (row, citation) in enumerate(zip(rows, citations), 1):
        if (not isinstance(row, dict) or not isinstance(citation, dict) or citation.get('scope') != scope
                or type(citation.get('rank')) is not int or citation['rank'] != rank
                or type(row.get('rank')) is not int or row['rank'] != rank
                or row.get('citation') != citation or row.get('document_id') != citation.get('document_id')
                or not isinstance(row.get('text'), str) or not 1 <= len(row['text']) <= 10000
                or any(not isinstance(citation.get(key), str) or not 1 <= len(citation[key]) <= 400
                       for key in ('document_id', 'source_id', 'label'))
                or citation['document_id'] in document_ids):
            return False
        document_ids.add(citation['document_id'])
    return True


def answer_state(payload, retrieval, scope, question):
    """Validate answers against independently observed retrieval, not citation counts."""
    if not envelope(payload, 'answer_question', scope):
        return 'invalid'
    data, metadata = payload['data'], payload['metadata']
    answer, invoked, model = data.get('answer'), metadata.get('model_invoked'), data.get('model')
    if (data.get('question') != question or not isinstance(answer, str) or not answer.strip()
            or len(answer) > 2000 or len(answer.split()) > 150 or type(invoked) is not bool
            or metadata.get('grounded') is not True or type(data.get('retrieved_count')) is not int
            or not 0 <= data['retrieved_count'] <= len(retrieval['data']['results'])
            or (invoked and (not isinstance(model, str) or not 1 <= len(model.strip()) <= 160))
            or (not invoked and model is not None)):
        return 'invalid'
    if payload['insufficient_context']:
        return 'insufficient' if (answer == INSUFFICIENT_ANSWER and payload['citations'] == []
                                  and payload.get('confidence') == 'insufficient') else 'invalid'
    if (not invoked or not data['retrieved_count'] or not payload['citations']
            or payload.get('confidence') != retrieval.get('confidence')
            or payload.get('confidence') not in {'high', 'medium', 'low'}):
        return 'invalid'
    observed = {item['rank']: item for item in retrieval['citations']}
    ranks = set()
    for citation in payload['citations']:
        if (not isinstance(citation, dict) or type(citation.get('rank')) is not int
                or citation['rank'] not in observed or citation != observed[citation['rank']]
                or citation['rank'] in ranks or citation['rank'] > data['retrieved_count']):
            return 'invalid'
        ranks.add(citation['rank'])
    if {int(number) for number in CITATION.findall(answer)} != ranks or any(
            not CITATION.search(paragraph) for paragraph in re.split(r'\n\s*\n', answer)):
        return 'invalid'
    return 'grounded'


def probe_runtime(config):
    if not feature_enabled() or not feature_enabled('RAG_ENABLED'):
        raise ProbeConfigurationError('AI or RAG mode disables live validation.')
    rules = config.get('rag_rules', {})
    scope = rules.get('required_scope')
    if not isinstance(scope, str) or not re.fullmatch(r'[a-z][a-z0-9_]{1,80}', scope):
        raise ProbeConfigurationError('Configure a feature knowledge scope.')
    required = rules.get('required_operations', sorted(OPERATIONS))
    if not isinstance(required, list) or not required or any(item not in OPERATIONS for item in required):
        raise ProbeConfigurationError('Unsupported RAG operations.')
    probes = configured_probes(rules)
    url = local_url(os.getenv('RAG_SERVER_URL', config.get('rag_server_url', 'http://127.0.0.1:5003')))
    if urlsplit(url).path not in {'', '/'}:
        raise ProbeConfigurationError('RAG URL must identify the local service root.')
    timeout = bounded_timeout(config.get('rag_timeout_seconds', 95), 120)
    status, health = read_json('GET', url + '/health', timeout=min(timeout, 10))
    if (not isinstance(health, dict) or any(not isinstance(health.get(key), list) or len(health[key]) > 20
            or any(not isinstance(value, str) for value in health[key]) for key in ('available_scopes', 'tools'))):
        raise ValueError('Invalid RAG health response')
    runtime = {'available': status == 200 and health.get('status') == 'healthy' and health.get('enabled') is True,
        'health_status': status, 'health': {'status': health.get('status'), 'service': health.get('service'),
        'enabled': health.get('enabled'), 'available_scopes': health.get('available_scopes', []),
        'operations': health.get('tools', []), 'ollama_model': health.get('ollama_model')}, 'probes': []}
    if not runtime['available']:
        return public_evidence(runtime)
    status, refresh = read_json('POST', url + '/refresh', payload={'scope': scope}, timeout=timeout)
    runtime['refresh'] = refresh
    refresh_ok = (status == 200 and envelope(refresh, 'refresh_corpus', scope)
                  and refresh['metadata'].get('read_only_source') is True
                  and type(refresh['data'].get('document_count')) is int and refresh['data']['document_count'] > 0)
    runtime['refresh_verified'] = refresh_ok
    for index, probe in enumerate(probes):
        question, top_k, expected = probe.get('question'), probe.get('top_k', 5), probe.get('expected', 'grounded')
        observation = {'name': probe.get('name', f'query-{index + 1}'), 'question': question, 'top_k': top_k,
                       'expected': expected, 'attempted': False, 'state': 'skipped', 'verified': False}
        try:
            if (set(probe) - {'name', 'question', 'top_k', 'expected', 'expect'}
                    or not isinstance(question, str) or not 1 <= len(question.strip()) <= 1000
                    or type(top_k) is not int or not 1 <= top_k <= 20 or expected not in {'grounded', 'insufficient'}):
                raise ProbeConfigurationError('Invalid feature RAG probe.')
            if not refresh_ok:
                observation['skip_reason'] = 'The selected corpus could not be refreshed.'
            else:
                question = question.strip()
                observation.update(question=question, attempted=True)
                status, retrieval = read_json('POST', url + '/retrieve', payload={'scope': scope, 'query': question, 'top_k': top_k}, timeout=timeout)
                observation.update(retrieval_status=status, retrieval=retrieval)
                observation['retrieval_verified'] = status == 200 and valid_retrieval(retrieval, scope, question, top_k)
                if not observation['retrieval_verified']:
                    observation['state'] = 'unavailable' if status == 503 else 'invalid'
                else:
                    status, answer = read_json('POST', url + '/answer', payload={'scope': scope, 'question': question, 'top_k': top_k}, timeout=timeout)
                    observation.update(answer_status=status, answer=answer)
                    state = answer_state(answer, retrieval, scope, question) if status == 200 else 'unavailable' if status == 503 else 'invalid'
                    observation['state'] = state
                    observation['checks'] = expectations(answer, probe.get('expect', []))
                    observation['generation_skipped'] = state == 'insufficient' and answer['metadata']['model_invoked'] is False
                    observation['verified'] = (state == expected and (expected != 'insufficient' or observation['generation_skipped'])
                                               and all(check['passed'] for check in observation['checks']))
        except Exception as exc:
            observation.update(state='error', error=type(exc).__name__)
        runtime['probes'].append(observation)
    if runtime['probes']:
        runtime['probe'] = runtime['probes'][0]  # Existing single-question consumers.
    return public_evidence(runtime)
