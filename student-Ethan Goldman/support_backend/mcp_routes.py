"""Admin-facing MCP routes, separate from the host tools' data callbacks."""

from flask import Blueprint, current_app, jsonify, request
from shared.mcp_client import MCPClientError

try:
    from .mcp_client import SupportMCPClient, validate_tool_arguments, validate_tool_response
    from .validation import ValidationError
    from .mcp_assistant import answer_question, validate_question
except ImportError:
    from mcp_client import SupportMCPClient, validate_tool_arguments, validate_tool_response
    from validation import ValidationError
    from mcp_assistant import answer_question, validate_question


TOOL_ERROR_STATUSES = {"INVALID_ARGUMENT": 400, "AUTHENTICATION_REQUIRED": 401,
                       "TOOL_NOT_ALLOWED": 403, "RECORD_NOT_FOUND": 404,
                       "UPSTREAM_UNAVAILABLE": 503}


def support_mcp_client():
    client = current_app.extensions.get("support_mcp_client")
    if client is None:
        client = SupportMCPClient()
        current_app.extensions["support_mcp_client"] = client
    return client


def session_headers():
    # Called only after staff authentication; never accept credentials in JSON.
    cookie = request.cookies.get("ethan_session", "")
    return {"Cookie": "ethan_session=" + cookie}


def create_mcp_blueprint(*, principal):
    blueprint = Blueprint("support_mcp", __name__, url_prefix="/api/support/admin/mcp")

    @blueprint.get("/tools")
    def list_tools():
        _, error = principal("admin")
        if error is not None:
            return error
        try:
            return jsonify({"tools": support_mcp_client().list_tools(request_headers=session_headers())})
        except MCPClientError as exc:
            return jsonify(exc.to_dict()), exc.status_code

    @blueprint.post("/tools/call")
    def call_tool():
        _, error = principal("admin")
        if error is not None:
            return error
        try:
            if len(request.get_data()) > 4096:
                return jsonify({"error": "Tool request is too large."}), 413
            payload = request.get_json(silent=True) if request.is_json else None
            if not isinstance(payload, dict) or set(payload) - {"tool", "arguments"} or "tool" not in payload:
                raise ValidationError("Provide a JSON tool name and arguments only.")
            arguments = validate_tool_arguments(payload["tool"], payload.get("arguments", {}))
            result = support_mcp_client().call_tool(payload["tool"], arguments, request_headers=session_headers())
            result = validate_tool_response(payload["tool"], result)
            status = 200 if result["success"] else TOOL_ERROR_STATUSES.get(result["error"].get("code"), 502)
            return jsonify(result), status
        except ValidationError as exc:
            return jsonify({"error": str(exc)}), 400
        except MCPClientError as exc:
            return jsonify(exc.to_dict()), exc.status_code

    @blueprint.post("/assistant")
    def assistant():
        _, error = principal("admin")
        if error is not None:
            return error
        try:
            if len(request.get_data()) > 4096:
                return jsonify({"error": "Assistant request is too large."}), 413
            payload = request.get_json(silent=True) if request.is_json else None
            question, ticket_id = validate_question(payload)
            result, status = answer_question(
                question.strip(), ticket_id, support_mcp_client(), session_headers(),
                model=current_app.extensions.get("support_mcp_model"),
            )
            return jsonify(result), status
        except ValidationError as exc:
            return jsonify({"error": str(exc)}), 400
        except MCPClientError as exc:
            return jsonify(exc.to_dict()), exc.status_code

    return blueprint
