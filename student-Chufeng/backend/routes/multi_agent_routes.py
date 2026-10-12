"""Flask routes for Chufeng's Product Catalogue Multi-Agent workflows."""

from flask import Blueprint, g, jsonify, request

from ..controllers import multi_agent_controller


multi_agent_blueprint = Blueprint(
    "chufeng_multi_agent",
    __name__,
    url_prefix="/api/chufeng/multi-agent",
)


@multi_agent_blueprint.get("/status")
def get_multi_agent_status():
    payload, status_code = multi_agent_controller.get_status()
    return jsonify(payload), status_code


@multi_agent_blueprint.post("/workflows")
def create_multi_agent_workflow():
    payload, status_code = multi_agent_controller.create_workflow(
        request.get_json(silent=True)
    )
    return jsonify(payload), status_code


@multi_agent_blueprint.get("/workflows")
def list_multi_agent_workflows():
    payload, status_code = multi_agent_controller.list_workflows()
    return jsonify(payload), status_code


@multi_agent_blueprint.get("/workflows/latest")
def get_latest_multi_agent_workflow():
    payload, status_code = multi_agent_controller.latest_workflow()
    return jsonify(payload), status_code


@multi_agent_blueprint.get("/workflows/<workflow_id>")
def get_multi_agent_workflow(workflow_id):
    payload, status_code = multi_agent_controller.get_workflow(workflow_id)
    return jsonify(payload), status_code


@multi_agent_blueprint.post("/workflows/<workflow_id>/review")
def review_multi_agent_workflow(workflow_id):
    payload, status_code = multi_agent_controller.submit_human_review(
        workflow_id,
        request.get_json(silent=True),
        getattr(g, "authenticated_user", None),
    )
    return jsonify(payload), status_code
