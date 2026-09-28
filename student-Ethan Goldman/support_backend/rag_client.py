"""Thin fixed-scope HTTP adapter; retrieval and inference remain host services."""

import json
import math
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

import requests
from shared.feature_flags import feature_enabled

try:
    from .validation import ValidationError
except ImportError:
    from validation import ValidationError


SUPPORT_SCOPE = 'ethan_goldman_support'
KNOWLEDGE_DIRECTORY = Path(__file__).resolve().parents[2] / 'ai-services' / 'rag_server' / 'knowledge' / 'ethan_goldman'
if not KNOWLEDGE_DIRECTORY.is_dir():
    KNOWLEDGE_DIRECTORY = Path(__file__).resolve().parent / 'knowledge'
INSUFFICIENT_ANSWER = 'Insufficient context to answer this question.'
CITATION_NUMBER = re.compile(r'\[(\d+)]')
SAFE_ERRORS = {
    'RAG_DISABLED': ('AI or RAG mode is disabled.', 503),
    'OLLAMA_UNAVAILABLE': ('The local knowledge model is unavailable. Try again later.', 503),
    'SOURCE_UNAVAILABLE': ('Support knowledge is unavailable. Try again later.', 503),
    'INDEX_UNAVAILABLE': ('The knowledge index is unavailable. Try again later.', 503),
    'UPSTREAM_ERROR': ('The knowledge service could not produce a validated answer.', 502),
}


class RAGClientError(Exception):
    def __init__(self, message, *, code='RAG_INVALID_RESPONSE', status_code=502):
        super().__init__(message)
        self.code, self.status_code = code, status_code

    def to_dict(self):
        return {'success': False, 'operation': 'answer_question', 'data': None, 'citations': [],
                'confidence': None, 'insufficient_context': False,
                'error': {'code': self.code, 'message': str(self)}}


def validate_question(payload):
    if not isinstance(payload, dict) or set(payload) - {'question', 'top_k'}:
        raise ValidationError('Provide only a question and optional top_k.')
    question = payload.get('question')
    if not isinstance(question, str) or not question.strip() or len(question.strip()) > 1000:
        raise ValidationError('question must contain 1 to 1000 characters.', 'question')
    top_k = payload.get('top_k', 5)
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 20:
        raise ValidationError('top_k must be an integer between 1 and 20.', 'top_k')
    return question.strip(), top_k


def knowledge_file(filename):
    # Resolve only approved direct files, never arbitrary paths or symlinks.
    if not isinstance(filename, str) or not re.fullmatch(r'[a-z][a-z0-9_]*\.md', filename):
        return None
    path = KNOWLEDGE_DIRECTORY / filename
    return path if path.is_file() and not path.is_symlink() else None


def _invalid():
    raise RAGClientError('The knowledge service returned an invalid response.')


def validate_answer(result, question):
    if (not isinstance(result, dict) or result.get('operation') != 'answer_question'
            or not isinstance(result.get('success'), bool) or not isinstance(result.get('insufficient_context'), bool)
            or not isinstance(result.get('citations'), list) or len(result['citations']) > 20):
        _invalid()
    if not result['success']:
        error = result.get('error')
        if not isinstance(error, dict) or not isinstance(error.get('code'), str):
            _invalid()
        message, status = SAFE_ERRORS.get(error['code'], ('The knowledge service is unavailable.', 503))
        raise RAGClientError(message, code=error['code'] if error['code'] in SAFE_ERRORS else 'RAG_UNAVAILABLE', status_code=status)
    data, metadata = result.get('data'), result.get('metadata')
    if (result.get('error') is not None or not isinstance(data, dict) or not isinstance(metadata, dict)
            or data.get('scope') != SUPPORT_SCOPE or data.get('question') != question
            or not isinstance(data.get('answer'), str) or not data['answer'].strip()
            or len(data['answer']) > 2000 or len(data['answer'].split()) > 150
            or not isinstance(metadata.get('model_invoked'), bool)):
        _invalid()
    if result['insufficient_context']:
        if result.get('confidence') != 'insufficient' or result['citations'] or data['answer'] != INSUFFICIENT_ANSWER:
            _invalid()
        if metadata['model_invoked'] and (not isinstance(data.get('model'), str) or not data['model'].strip()):
            _invalid()
        if not metadata['model_invoked'] and data.get('model') is not None:
            _invalid()
        return result
    if (result.get('confidence') not in {'high', 'medium', 'low'} or not metadata['model_invoked']
            or not isinstance(data.get('model'), str) or not 1 <= len(data['model'].strip()) <= 160
            or isinstance(data.get('retrieved_count'), bool) or not isinstance(data.get('retrieved_count'), int)
            or not 1 <= data['retrieved_count'] <= 20 or not result['citations']):
        _invalid()
    ranks = set()
    for citation in result['citations']:
        if not isinstance(citation, dict) or citation.get('scope') != SUPPORT_SCOPE:
            _invalid()
        source_id, document_id, rank = citation.get('source_id'), citation.get('document_id'), citation.get('rank')
        if not isinstance(source_id, str) or not source_id.startswith(SUPPORT_SCOPE + '/'):
            _invalid()
        filename = source_id[len(SUPPORT_SCOPE) + 1:]
        if (knowledge_file(filename) is None or not isinstance(document_id, str)
                or not re.fullmatch(re.escape(SUPPORT_SCOPE + ':' + filename + ':') + r'[0-9]{1,3}', document_id)
                or int(document_id.rsplit(':', 1)[1]) >= 200
                or not isinstance(citation.get('label'), str) or not 1 <= len(citation['label']) <= 330
                or isinstance(rank, bool) or not isinstance(rank, int) or not 1 <= rank <= data['retrieved_count']
                or rank in ranks):
            _invalid()
        ranks.add(rank)
    used = {int(number) for number in CITATION_NUMBER.findall(data['answer'])}
    if not used or used != ranks or any(not CITATION_NUMBER.search(part) for part in re.split(r'\n\s*\n', data['answer'])):
        _invalid()
    return result


class SupportRAGClient:
    def answer_question(self, question, top_k=5):
        question, top_k = validate_question({'question': question, 'top_k': top_k})
        if not feature_enabled() or not feature_enabled('RAG_ENABLED'):
            raise RAGClientError('AI or RAG mode is disabled.', code='RAG_DISABLED', status_code=503)
        url = os.getenv('RAG_SERVER_URL', 'http://127.0.0.1:5003').rstrip('/')
        try:
            parsed = urlsplit(url)
            timeout = float(os.getenv('RAG_CLIENT_TIMEOUT_SECONDS', '60'))
            if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password
                    or parsed.query or parsed.fragment or not math.isfinite(timeout) or not 0 < timeout <= 120):
                raise ValueError()
        except ValueError:
            raise RAGClientError('Knowledge service configuration is invalid.', code='RAG_CONFIGURATION_ERROR', status_code=503) from None
        try:
            with requests.post(url + '/answer', json={'scope': SUPPORT_SCOPE, 'question': question, 'top_k': top_k},
                               timeout=timeout, stream=True, allow_redirects=False) as response:
                if not 200 <= response.status_code < 600 or 300 <= response.status_code < 400:
                    _invalid()
                raw = bytearray()
                for chunk in response.iter_content(4096):
                    raw.extend(chunk)
                    if len(raw) > 65536:
                        _invalid()
                result = json.loads(raw)
                if response.status_code != 200 and isinstance(result, dict) and result.get('success') is True:
                    _invalid()
        except requests.RequestException:
            raise RAGClientError('The knowledge service is unavailable. Try again later.', code='RAG_UNAVAILABLE', status_code=503) from None
        except (ValueError, UnicodeError):
            _invalid()
        return validate_answer(result, question)
