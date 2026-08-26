"""Read models for Customer Support tickets."""

from contextlib import closing

from .database import get_database_connection


TICKET_COLUMNS = """
    id, customer_name, customer_email, subject, message, category, priority,
    status, assigned_to, staff_response, responded_at, created_at, updated_at
"""


def get_tickets():
    with closing(get_database_connection()) as connection:
        rows = connection.execute(
            f"""
            SELECT {TICKET_COLUMNS}
            FROM support_tickets
            ORDER BY datetime(updated_at) DESC, id DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def get_ticket(ticket_id):
    with closing(get_database_connection()) as connection:
        row = connection.execute(
            f"SELECT {TICKET_COLUMNS} FROM support_tickets WHERE id = ?",
            (ticket_id,),
        ).fetchone()

    return dict(row) if row is not None else None
