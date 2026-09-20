
"""Flask routes exposing Chufeng's RAG integration to its frontend."""

from flask import Blueprint, jsonify, request

from ..controllers import rag_controller


rag_blueprint = Blueprint(
    "chufeng_rag",
    __name__,
    url_prefix="/api/chufeng/rag",
)


@rag_blueprint.get("/status")
def get_rag_status():
    payload, status_code = rag_controller.get_rag_status()
    return jsonify(payload), status_code


@rag_blueprint.post("/refresh")
def refresh_rag_corpus():
    payload, status_code = rag_controller.refresh_rag_corpus()
    return jsonify(payload), status_code


@rag_blueprint.post("/retrieve")
def retrieve_rag_context():
    payload, status_code = rag_controller.retrieve_rag_context(
        request.get_json(silent=True)
    )
    return jsonify(payload), status_code


@rag_blueprint.post("/answer")
def answer_rag_question():
    payload, status_code = rag_controller.answer_rag_question(
        request.get_json(silent=True)
    )
    return jsonify(payload), status_code
