"""Authenticated support workflow API; mutations still use existing ticket controls."""

from flask import Blueprint, jsonify, request
from shared.multi_agent_client import MultiAgentClientError

try:
    from . import multi_agent
    from .db_client import SupportDatabaseError
    from .validation import ValidationError
except ImportError:  # Direct Docker script execution.
    import multi_agent
    from db_client import SupportDatabaseError
    from validation import ValidationError


def create_multi_agent_blueprint(*, principal, database, db_error):
    blueprint = Blueprint(
        "support_multi_agent", __name__, url_prefix="/api/support/admin/multi-agent"
    )

    def execute(operation, status=200):
        _, failure = principal("admin")
        if failure is not None:
            return failure
        try:
            multi_agent.ensure_enabled()
            if request.args:
                raise ValidationError("Workflow routes do not accept query parameters.")
            return jsonify(operation(database())), status
        except ValidationError as exc:
            return jsonify({"error": str(exc)}), 400
        except MultiAgentClientError as exc:
            return jsonify(exc.to_dict()), exc.status_code
        except SupportDatabaseError as exc:
            return db_error(exc)

    @blueprint.post("/tickets/<int:ticket_id>/workflows")
    def create_ticket_workflow(ticket_id):
        return execute(
            lambda db: multi_agent.create_workflow(
                db, ticket_id, request.get_json(silent=True)
            ),
            201,
        )

    @blueprint.get("/tickets/<int:ticket_id>/workflows")
    def list_ticket_workflows(ticket_id):
        return execute(lambda db: multi_agent.list_workflows(db, ticket_id))

    @blueprint.get("/tickets/<int:ticket_id>/workflows/<workflow_id>")
    def get_ticket_workflow(ticket_id, workflow_id):
        return execute(lambda db: multi_agent.get_workflow(db, ticket_id, workflow_id))

    return blueprint
