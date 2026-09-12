"""Flask routes exposing Chufeng's MCP integration to its frontend."""

from flask import Blueprint, jsonify, request

from ..controllers import mcp_controller


mcp_blueprint = Blueprint(
    "chufeng_mcp",
    __name__,
    url_prefix="/api/chufeng/mcp",
)


@mcp_blueprint.get("/status")
def get_mcp_status():
    payload, status_code = mcp_controller.get_mcp_status()
    return jsonify(payload), status_code


@mcp_blueprint.get("/tools")
def list_mcp_tools():
    payload, status_code = mcp_controller.list_mcp_tools()
    return jsonify(payload), status_code


@mcp_blueprint.post("/tools/call")
def call_mcp_tool():
    payload, status_code = mcp_controller.call_mcp_tool(
        request.get_json(silent=True)
    )
    return jsonify(payload), status_code
