"""Read models for Customer Support tickets."""

from contextlib import closing

from .database import get_database_connection


TICKET_COLUMNS = """
    id, customer_name, customer_email, subject, message, category, priority,
    status, assigned_to, staff_response, responded_at, created_at, updated_at
"""


def get_tickets(filters=None):
    filters = filters or {}
    conditions = []
    parameters = []

    search = filters.get("search")
    if search:
        search_pattern = f"%{search.casefold()}%"
        conditions.append(
            """
            (
                LOWER(customer_name) LIKE ?
                OR LOWER(customer_email) LIKE ?
                OR LOWER(subject) LIKE ?
                OR CAST(id AS TEXT) LIKE ?
            )
            """
        )
        parameters.extend([search_pattern] * 4)

    for field in ("status", "priority", "category"):
        if filters.get(field):
            conditions.append(f"{field} = ?")
            parameters.append(filters[field])

    assigned_to = filters.get("assigned_to")
    if assigned_to == "unassigned":
        conditions.append("assigned_to IS NULL")
    elif assigned_to:
        conditions.append("LOWER(assigned_to) = ?")
        parameters.append(assigned_to.casefold())

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with closing(get_database_connection()) as connection:
        rows = connection.execute(
            f"""
            SELECT {TICKET_COLUMNS}
            FROM support_tickets
            {where_clause}
            ORDER BY datetime(updated_at) DESC, id DESC
            """,
            parameters,
        ).fetchall()

    return [dict(row) for row in rows]


def get_ticket(ticket_id):
    with closing(get_database_connection()) as connection:
        row = connection.execute(
            f"SELECT {TICKET_COLUMNS} FROM support_tickets WHERE id = ?",
            (ticket_id,),
        ).fetchone()

    return dict(row) if row is not None else None
