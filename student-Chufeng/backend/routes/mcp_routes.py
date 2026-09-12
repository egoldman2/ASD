"""Flask routes exposing Chufeng's MCP integration to its frontend."""

from flask import Blueprint, jsonify, request

from ..controllers import mcp_controller


mcp_blueprint = Blueprint(
    "chufeng_mcp",
    __name__,
    url_prefix="/api/chufeng/mcp",
)

MCP_MODE_HEADER = "X-MCP-Mode"
MCP_MODE_ON_VALUES = {"1", "true", "yes", "on"}


def _request_mcp_mode_enabled():
    value = request.headers.get(MCP_MODE_HEADER, "on")
    return value.strip().lower() in MCP_MODE_ON_VALUES


def _mcp_mode_disabled_response():
    return jsonify(
        {
            "error": {
                "code": "MCP_DISABLED",
                "message": "MCP mode is disabled for this request.",
            }
        }
    ), 403


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
    if not _request_mcp_mode_enabled():
        return _mcp_mode_disabled_response()

    payload, status_code = mcp_controller.call_mcp_tool(
        request.get_json(silent=True)
    )
    return jsonify(payload), status_code
