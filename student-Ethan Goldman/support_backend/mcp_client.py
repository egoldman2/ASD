"""Support-owned allowlist and input validation around shared MCP transport."""

from shared.mcp_client import MCPClient, MCPClientError, MCPToolNotAllowedError

try:
    from .validation import ValidationError, validate_admin_filters
except ImportError:
    from validation import ValidationError, validate_admin_filters


SEARCH_TICKETS = "ethan_goldman_search_tickets"
GET_TICKET_CONTEXT = "ethan_goldman_get_ticket_context"
GET_QUEUE_SUMMARY = "ethan_goldman_get_queue_summary"
GET_TICKETS_NEEDING_ATTENTION = "ethan_goldman_get_tickets_needing_attention"
GOLDMAN_ALLOWED_TOOLS = frozenset({
    SEARCH_TICKETS, GET_TICKET_CONTEXT, GET_QUEUE_SUMMARY, GET_TICKETS_NEEDING_ATTENTION,
})
TOOL_FIELDS = {
    SEARCH_TICKETS: {"search", "status", "category", "priority", "assigned_to", "limit", "offset"},
    GET_TICKET_CONTEXT: {"ticket_id", "message_limit"},
    GET_QUEUE_SUMMARY: {"category", "assigned_to"},
    GET_TICKETS_NEEDING_ATTENTION: {"category", "assigned_to", "inactive_hours", "limit", "offset"},
}
INTEGER_BOUNDS = {"ticket_id": (1, 2**63 - 1), "message_limit": (1, 50), "limit": (1, 50),
                  "offset": (0, 10000), "inactive_hours": (1, 720)}


def validate_tool_arguments(tool, arguments):
    if not isinstance(tool, str) or tool not in GOLDMAN_ALLOWED_TOOLS:
        raise MCPToolNotAllowedError("requested tool")
    if not isinstance(arguments, dict) or set(arguments) - TOOL_FIELDS[tool]:
        raise ValidationError("Unsupported support tool arguments.")
    if tool == GET_TICKET_CONTEXT and "ticket_id" not in arguments:
        raise ValidationError("ticket_id is required.")
    filters = {key: value for key, value in arguments.items() if key not in INTEGER_BOUNDS}
    result = validate_admin_filters(filters)
    for field, value in arguments.items():
        if field in INTEGER_BOUNDS:
            minimum, maximum = INTEGER_BOUNDS[field]
            if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
                raise ValidationError(f"{field} must be an integer between {minimum} and {maximum}.", field)
            result[field] = value
    return result


class SupportMCPClient(MCPClient):
    def __init__(self, settings=None, *, http_client_factory=None):
        super().__init__(settings, allowed_tools=GOLDMAN_ALLOWED_TOOLS, http_client_factory=http_client_factory)

    async def acall_tool(self, tool_name, arguments=None, *, request_headers=None):
        return await super().acall_tool(tool_name, validate_tool_arguments(
            tool_name, {} if arguments is None else arguments,
        ), request_headers=request_headers)


def validate_tool_response(tool, result):
    if (not isinstance(result, dict) or result.get("tool") != tool
            or not isinstance(result.get("success"), bool)
            or "result" not in result or "error" not in result):
        raise MCPClientError("The MCP server returned an invalid response.", code="MCP_INVALID_RESPONSE")
    if result["success"] and not isinstance(result["result"], dict):
        raise MCPClientError("The MCP server returned an invalid response.", code="MCP_INVALID_RESPONSE")
    if not result["success"] and not isinstance(result["error"], dict):
        raise MCPClientError("The MCP server returned an invalid response.", code="MCP_INVALID_RESPONSE")
    if not result["success"] and not isinstance(result["error"].get("code"), str):
        raise MCPClientError("The MCP server returned an invalid response.", code="MCP_INVALID_RESPONSE")
    return result
