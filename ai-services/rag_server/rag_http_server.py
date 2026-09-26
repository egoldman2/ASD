
"""Small local HTTP adapter around the shared RAG pipeline.

This process runs on the host, not in Docker.  Dockerised student backends can
reach it at ``http://host.docker.internal:5003`` while host-side checks use
``http://localhost:5003``.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, cast

from flask import Flask, jsonify, request

from rag_server.config import RAGSettings, get_settings
from rag_server.rag_pipeline import RAGPipeline
from rag_server.response import RAGErrorCode, error_response
from rag_server.rag_server import AVAILABLE_TOOLS, DEFAULT_SCOPE


SERVICE_NAME = "asd-marketplace-rag"
MAX_REQUEST_BODY_BYTES = 64 * 1024
PipelineFactory = Callable[[], RAGPipeline]

ERROR_STATUS_CODES = {
    RAGErrorCode.INVALID_ARGUMENT.value: 400,
    RAGErrorCode.SCOPE_NOT_FOUND.value: 404,
    RAGErrorCode.SOURCE_DATA_INVALID.value: 502,
    RAGErrorCode.UPSTREAM_ERROR.value: 502,
    RAGErrorCode.SOURCE_UNAVAILABLE.value: 503,
    RAGErrorCode.INDEX_UNAVAILABLE.value: 503,
    RAGErrorCode.OLLAMA_UNAVAILABLE.value: 503,
    RAGErrorCode.RAG_DISABLED.value: 503,
    RAGErrorCode.INTERNAL_ERROR.value: 500,
}


def _execute(
    pipeline_factory: PipelineFactory,
    method_name: str,
    *args: Any,
) -> dict[str, Any]:
    pipeline = pipeline_factory()
    try:
        method = getattr(pipeline, method_name)
        return cast(dict[str, Any], method(*args))
    finally:
        close = getattr(pipeline, "close", None)
        if callable(close):
            close()


def _status_for(payload: dict[str, Any]) -> int:
    if payload.get("success"):
        return 200
    error = payload.get("error") or {}
    return ERROR_STATUS_CODES.get(error.get("code"), 500)


def _json_body(operation: str) -> tuple[dict[str, Any] | None, Any | None]:
    """Return an object JSON body or a ready-to-send error response."""

    if (
        request.content_length is not None
        and request.content_length > MAX_REQUEST_BODY_BYTES
    ):
        payload = error_response(
            operation,
            RAGErrorCode.INVALID_ARGUMENT,
            f"Request body must not exceed {MAX_REQUEST_BODY_BYTES} bytes.",
        )
        return None, (jsonify(payload), 413)

    if not request.is_json:
        payload = error_response(
            operation,
            RAGErrorCode.INVALID_ARGUMENT,
            "Request body must use application/json.",
        )
        return None, (jsonify(payload), 400)

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        payload = error_response(
            operation,
            RAGErrorCode.INVALID_ARGUMENT,
            "Request body must be a JSON object.",
        )
        return None, (jsonify(payload), 400)
    return body, None


def create_app(
    settings: RAGSettings | None = None,
    pipeline_factory: PipelineFactory | None = None,
) -> Flask:
    """Create the local HTTP application with injectable pipeline instances."""

    resolved = settings or get_settings()
    factory = pipeline_factory or (lambda: RAGPipeline(settings=resolved))
    app = Flask(__name__)
    app.config.update(
        MAX_CONTENT_LENGTH=MAX_REQUEST_BODY_BYTES,
    )
    app.json.sort_keys = False

    @app.get("/")
    def service_index() -> tuple[Any, int]:
        return jsonify(
            {
                "service": SERVICE_NAME,
                "status": "healthy" if resolved.enabled else "disabled",
                "endpoints": {
                    "health": "GET /health",
                    "refresh": "POST /refresh",
                    "retrieve": "POST /retrieve",
                    "answer": "POST /answer",
                },
                "tools": list(AVAILABLE_TOOLS),
            }
        ), 200

    @app.get("/health")
    def health() -> tuple[Any, int]:
        pipeline = factory()
        try:
            scopes = list(pipeline.available_scopes)
        finally:
            close = getattr(pipeline, "close", None)
            if callable(close):
                close()

        status_code = 200 if resolved.enabled else 503
        return jsonify(
            {
                "status": "healthy" if resolved.enabled else "disabled",
                "service": SERVICE_NAME,
                "enabled": resolved.enabled,
                "available_scopes": scopes,
                "tools": list(AVAILABLE_TOOLS),
                "ollama_model": resolved.ollama_model,
            }
        ), status_code

    @app.post("/refresh")
    def refresh() -> tuple[Any, int]:
        body, failure = _json_body("refresh_corpus")
        if failure is not None:
            return failure
        assert body is not None
        payload = _execute(
            factory,
            "refresh_corpus",
            body.get("scope", DEFAULT_SCOPE),
        )
        return jsonify(payload), _status_for(payload)

    @app.post("/retrieve")
    def retrieve() -> tuple[Any, int]:
        body, failure = _json_body("retrieve_context")
        if failure is not None:
            return failure
        assert body is not None
        payload = _execute(
            factory,
            "retrieve_context",
            body.get("scope", DEFAULT_SCOPE),
            body.get("query"),
            body.get("top_k", resolved.default_top_k),
        )
        return jsonify(payload), _status_for(payload)

    @app.post("/answer")
    def answer() -> tuple[Any, int]:
        body, failure = _json_body("answer_question")
        if failure is not None:
            return failure
        assert body is not None
        payload = _execute(
            factory,
            "answer_question",
            body.get("scope", DEFAULT_SCOPE),
            body.get("question"),
            body.get("top_k", resolved.default_top_k),
        )
        return jsonify(payload), _status_for(payload)

    @app.errorhandler(404)
    def not_found(_: Any) -> tuple[Any, int]:
        payload = error_response(
            "http_request",
            RAGErrorCode.INVALID_ARGUMENT,
            "The requested RAG endpoint does not exist.",
        )
        return jsonify(payload), 404

    @app.errorhandler(405)
    def method_not_allowed(_: Any) -> tuple[Any, int]:
        payload = error_response(
            "http_request",
            RAGErrorCode.INVALID_ARGUMENT,
            "The HTTP method is not allowed for this RAG endpoint.",
        )
        return jsonify(payload), 405

    @app.errorhandler(413)
    def request_too_large(_: Any) -> tuple[Any, int]:
        payload = error_response(
            "http_request",
            RAGErrorCode.INVALID_ARGUMENT,
            f"Request body must not exceed {MAX_REQUEST_BODY_BYTES} bytes.",
        )
        return jsonify(payload), 413

    @app.errorhandler(Exception)
    def unexpected_error(error: Exception) -> tuple[Any, int]:
        app.logger.exception("Unhandled RAG HTTP request failure", exc_info=error)
        payload = error_response(
            "http_request",
            RAGErrorCode.INTERNAL_ERROR,
            "The RAG service could not complete the request.",
        )
        return jsonify(payload), 500

    return app


def main() -> None:
    """Run the local HTTP bridge on the configured host and port."""

    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger(__name__).info(
        "Starting %s at %s (bind %s:%s)",
        SERVICE_NAME,
        settings.endpoint_url,
        settings.host,
        settings.port,
    )
    app = create_app(settings=settings)
    app.run(
        host=settings.host,
        port=settings.port,
        debug=False,
        threaded=True,
        use_reloader=False,
    )


if __name__ == "__main__":
    main()
