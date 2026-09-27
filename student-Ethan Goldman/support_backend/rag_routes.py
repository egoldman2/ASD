"""Staff-only fixed-scope knowledge query and approved source access."""

from flask import Blueprint, current_app, jsonify, request, send_file

try:
    from .rag_client import RAGClientError, SupportRAGClient, knowledge_file, validate_question
    from .validation import ValidationError
except ImportError:
    from rag_client import RAGClientError, SupportRAGClient, knowledge_file, validate_question
    from validation import ValidationError


def support_rag_client():
    client = current_app.extensions.get('support_rag_client')
    if client is None:
        client = SupportRAGClient()
        current_app.extensions['support_rag_client'] = client
    return client


def create_rag_blueprint(*, principal):
    blueprint = Blueprint('support_rag', __name__, url_prefix='/api/support/admin/rag')

    @blueprint.post('/answer')
    def answer():
        _, error = principal('admin')
        if error is not None:
            return error
        try:
            if len(request.get_data()) > 4096:
                return jsonify({'error': 'Knowledge query is too large.'}), 413
            question, top_k = validate_question(request.get_json(silent=True) if request.is_json else None)
            return jsonify(support_rag_client().answer_question(question, top_k))
        except ValidationError as exc:
            return jsonify({'error': str(exc)}), 400
        except RAGClientError as exc:
            return jsonify(exc.to_dict()), exc.status_code

    @blueprint.get('/sources/<filename>')
    def source(filename):
        _, error = principal('admin')
        if error is not None:
            return error
        path = knowledge_file(filename)
        if path is None:
            return jsonify({'error': 'Knowledge source not found.'}), 404
        response = send_file(path, mimetype='text/plain', as_attachment=False, conditional=True)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Cache-Control'] = 'no-store'
        return response

    return blueprint
