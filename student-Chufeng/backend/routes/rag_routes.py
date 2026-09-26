
"""Flask routes exposing Chufeng's RAG integration to its frontend."""

from flask import Blueprint, jsonify, request

from ..controllers import rag_controller


rag_blueprint = Blueprint(
    "chufeng_rag",
    __name__,
    url_prefix="/api/chufeng/rag",
)

RAG_MODE_HEADER = "X-RAG-Mode"
RAG_MODE_ON_VALUES = {"1", "true", "yes", "on"}


def _request_rag_mode_enabled():
    value = request.headers.get(RAG_MODE_HEADER, "on")
    return value.strip().lower() in RAG_MODE_ON_VALUES


def _rag_mode_disabled_response():
    return jsonify(
        {
            "error": {
                "code": "RAG_DISABLED",
                "message": "RAG mode is disabled for this request.",
            }
        }
    ), 403


@rag_blueprint.get("/status")
def get_rag_status():
    payload, status_code = rag_controller.get_rag_status()
    return jsonify(payload), status_code


@rag_blueprint.post("/refresh")
def refresh_rag_corpus():
    if not _request_rag_mode_enabled():
        return _rag_mode_disabled_response()

    payload, status_code = rag_controller.refresh_rag_corpus()
    return jsonify(payload), status_code


@rag_blueprint.post("/retrieve")
def retrieve_rag_context():
    if not _request_rag_mode_enabled():
        return _rag_mode_disabled_response()

    payload, status_code = rag_controller.retrieve_rag_context(
        request.get_json(silent=True)
    )
    return jsonify(payload), status_code


@rag_blueprint.post("/answer")
def answer_rag_question():
    if not _request_rag_mode_enabled():
        return _rag_mode_disabled_response()

    payload, status_code = rag_controller.answer_rag_question(
        request.get_json(silent=True)
    )
    return jsonify(payload), status_code
