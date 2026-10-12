"""Flask application entry point for the shared Multi-Agent Server."""

from __future__ import annotations

import logging
from typing import Any

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from multi_agent_server.agents.planner_agent import (
    PlannerAgent,
    PlannerResponseError,
)
from multi_agent_server.agents.reviewer_agent import (
    ReviewerAgent,
    ReviewerInputError,
    ReviewerResponseError,
)
from multi_agent_server.agents.worker_agent import (
    WorkerAgent,
    WorkerInputError,
    WorkerResponseError,
)
from multi_agent_server.config import MultiAgentSettings, get_settings
from multi_agent_server.contracts import (
    ContractValidationError,
    HumanReviewRequest,
    WorkflowRequest,
)
from multi_agent_server.coordinator import WorkflowCoordinator
from multi_agent_server.model_client import (
    ModelConnectionError,
    ModelHTTPError,
    ModelResponseError,
    ModelTimeoutError,
    OllamaModelClient,
)
from multi_agent_server.workflow_store import (
    DuplicateWorkflowError,
    WorkflowAlreadyReviewedError,
    WorkflowNotFoundError,
    WorkflowStateError,
    WorkflowStore,
    WorkflowStoreError,
)


SERVICE_NAME = "asd-marketplace-multi-agent"


def _error_payload(
    code: str,
    message: str,
    *,
    field: str | None = None,
    **details: Any,
) -> dict[str, dict[str, Any]]:
    error: dict[str, Any] = {"code": code, "message": message}
    if field is not None:
        error["field"] = field
    error.update(details)
    return {"error": error}


def build_coordinator(settings: MultiAgentSettings) -> WorkflowCoordinator:
    """Build the production workflow graph without contacting Ollama yet."""

    if not isinstance(settings, MultiAgentSettings):
        raise TypeError("settings must be MultiAgentSettings.")
    model_client = OllamaModelClient(settings)
    return WorkflowCoordinator(
        PlannerAgent(model_client),
        WorkerAgent(model_client),
        ReviewerAgent(model_client),
        WorkflowStore(settings.history_path, settings.audit_path),
    )


def create_app(
    settings: MultiAgentSettings | None = None,
    coordinator: WorkflowCoordinator | Any | None = None,
) -> Flask:
    """Create the HTTP adapter with an injectable workflow coordinator."""

    resolved = settings or get_settings()
    workflow_coordinator = (
        build_coordinator(resolved) if coordinator is None else coordinator
    )
    for method_name in (
        "run",
        "list_workflows",
        "get_latest_workflow",
        "get_workflow",
        "submit_human_review",
    ):
        if not callable(getattr(workflow_coordinator, method_name, None)):
            raise TypeError(
                f"coordinator must provide a callable {method_name}()."
            )

    app = Flask(__name__)
    app.config.update(
        MAX_CONTENT_LENGTH=resolved.max_request_bytes,
    )
    app.json.ensure_ascii = False
    app.json.sort_keys = False
    app.extensions["workflow_coordinator"] = workflow_coordinator
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    def json_body() -> tuple[Any | None, tuple[Any, int] | None]:
        if (
            request.content_length is not None
            and request.content_length > resolved.max_request_bytes
        ):
            return None, (
                jsonify(
                    _error_payload(
                        "request_too_large",
                        "Request body must not exceed "
                        f"{resolved.max_request_bytes} bytes.",
                    )
                ),
                413,
            )
        if not request.is_json:
            return None, (
                jsonify(
                    _error_payload(
                        "unsupported_media_type",
                        "Request body must use application/json.",
                    )
                ),
                415,
            )
        payload = request.get_json(silent=True)
        if payload is None:
            return None, (
                jsonify(
                    _error_payload(
                        "invalid_json",
                        "Request body must contain valid JSON.",
                    )
                ),
                400,
            )
        return payload, None

    @app.get("/health")
    def health() -> tuple[Any, int]:
        return jsonify({"status": "ok", "service": SERVICE_NAME}), 200

    @app.post("/api/workflows")
    def create_workflow() -> tuple[Any, int]:
        payload, failure = json_body()
        if failure is not None:
            return failure
        workflow_request = WorkflowRequest.from_dict(payload)
        result = workflow_coordinator.run(workflow_request)
        return jsonify(result), 201

    @app.get("/api/workflows")
    def list_workflows() -> tuple[Any, int]:
        workflows = workflow_coordinator.list_workflows()
        return jsonify({"count": len(workflows), "workflows": workflows}), 200

    @app.get("/api/workflows/latest")
    def latest_workflow() -> tuple[Any, int]:
        workflow = workflow_coordinator.get_latest_workflow()
        if workflow is None:
            return (
                jsonify(
                    _error_payload(
                        "workflow_not_found",
                        "No workflows have been recorded.",
                    )
                ),
                404,
            )
        return jsonify(workflow), 200

    @app.get("/api/workflows/<workflow_id>")
    def get_workflow(workflow_id: str) -> tuple[Any, int]:
        return jsonify(workflow_coordinator.get_workflow(workflow_id)), 200

    @app.post("/api/workflows/<workflow_id>/review")
    def submit_human_review(workflow_id: str) -> tuple[Any, int]:
        payload, failure = json_body()
        if failure is not None:
            return failure
        review = HumanReviewRequest.from_dict(payload)
        result = workflow_coordinator.submit_human_review(workflow_id, review)
        return jsonify(result), 200

    @app.errorhandler(ContractValidationError)
    def contract_error(error: ContractValidationError) -> tuple[Any, int]:
        return jsonify(error.to_dict()), 400

    @app.errorhandler(WorkflowNotFoundError)
    def workflow_not_found(error: WorkflowNotFoundError) -> tuple[Any, int]:
        return jsonify(_error_payload("workflow_not_found", str(error))), 404

    @app.errorhandler(DuplicateWorkflowError)
    def duplicate_workflow(error: DuplicateWorkflowError) -> tuple[Any, int]:
        return jsonify(_error_payload("duplicate_workflow", str(error))), 409

    @app.errorhandler(WorkflowAlreadyReviewedError)
    def workflow_already_reviewed(
        error: WorkflowAlreadyReviewedError,
    ) -> tuple[Any, int]:
        return jsonify(_error_payload("workflow_already_reviewed", str(error))), 409

    @app.errorhandler(ModelConnectionError)
    def model_connection_error(error: ModelConnectionError) -> tuple[Any, int]:
        return jsonify(error.to_dict()), 503

    @app.errorhandler(ModelTimeoutError)
    def model_timeout_error(error: ModelTimeoutError) -> tuple[Any, int]:
        return jsonify(error.to_dict()), 504

    @app.errorhandler(ModelHTTPError)
    @app.errorhandler(ModelResponseError)
    def model_upstream_error(error: Any) -> tuple[Any, int]:
        return jsonify(error.to_dict()), 502

    @app.errorhandler(PlannerResponseError)
    @app.errorhandler(WorkerResponseError)
    @app.errorhandler(ReviewerResponseError)
    def agent_response_error(error: Any) -> tuple[Any, int]:
        return jsonify(_error_payload(error.code, str(error))), 502

    @app.errorhandler(WorkerInputError)
    @app.errorhandler(ReviewerInputError)
    @app.errorhandler(WorkflowStateError)
    def workflow_state_error(_: Exception) -> tuple[Any, int]:
        return (
            jsonify(
                _error_payload(
                    "workflow_state_error",
                    "The workflow produced inconsistent internal state.",
                )
            ),
            500,
        )

    @app.errorhandler(WorkflowStoreError)
    def workflow_store_error(_: WorkflowStoreError) -> tuple[Any, int]:
        return (
            jsonify(
                _error_payload(
                    "workflow_store_error",
                    "Workflow persistence is unavailable.",
                )
            ),
            500,
        )

    @app.errorhandler(HTTPException)
    def http_error(error: HTTPException) -> tuple[Any, int]:
        status = error.code or 500
        code, message = {
            404: ("endpoint_not_found", "The requested endpoint does not exist."),
            405: ("method_not_allowed", "The HTTP method is not allowed."),
            413: (
                "request_too_large",
                f"Request body must not exceed {resolved.max_request_bytes} bytes.",
            ),
        }.get(status, ("http_error", "The HTTP request could not be completed."))
        return jsonify(_error_payload(code, message)), status

    @app.errorhandler(Exception)
    def unexpected_error(error: Exception) -> tuple[Any, int]:
        app.logger.exception(
            "Unhandled Multi-Agent HTTP request failure",
            exc_info=error,
        )
        return (
            jsonify(
                _error_payload(
                    "internal_error",
                    "The Multi-Agent service could not complete the request.",
                )
            ),
            500,
        )

    return app


def main() -> None:
    """Run the local non-containerised Multi-Agent HTTP service."""

    settings = get_settings()
    logging.basicConfig(
        level=logging.INFO,
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
