"""Persistence models for Customer Support tickets and message threads."""

from contextlib import closing

from .database import get_database_connection


TICKET_COLUMNS = """
    id, customer_name, customer_email, subject, category, priority,
    status, assigned_to, created_at, updated_at
"""

MESSAGE_COLUMNS = """
    id, ticket_id, sender_role, author_name, message, created_at
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
                LOWER(ticket.customer_name) LIKE ?
                OR LOWER(ticket.customer_email) LIKE ?
                OR LOWER(ticket.subject) LIKE ?
                OR CAST(ticket.id AS TEXT) LIKE ?
            )
            """
        )
        parameters.extend([search_pattern] * 4)

    for field in ("status", "priority", "category"):
        if filters.get(field):
            conditions.append(f"ticket.{field} = ?")
            parameters.append(filters[field])

    assigned_to = filters.get("assigned_to")
    if assigned_to == "unassigned":
        conditions.append("ticket.assigned_to IS NULL")
    elif assigned_to:
        conditions.append("LOWER(ticket.assigned_to) = ?")
        parameters.append(assigned_to.casefold())

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    selected_columns = ", ".join(
        f"ticket.{column.strip()}" for column in TICKET_COLUMNS.split(",")
    )

    with closing(get_database_connection()) as connection:
        rows = connection.execute(
            f"""
            SELECT
                {selected_columns},
                COUNT(message.id) AS message_count,
                MAX(message.created_at) AS last_message_at
            FROM support_tickets AS ticket
            LEFT JOIN support_ticket_messages AS message
                ON message.ticket_id = ticket.id
            {where_clause}
            GROUP BY ticket.id
            ORDER BY datetime(ticket.updated_at) DESC, ticket.id DESC
            """,
            parameters,
        ).fetchall()

    return [dict(row) for row in rows]


def _get_ticket_with_connection(connection, ticket_id):
    ticket_row = connection.execute(
        f"SELECT {TICKET_COLUMNS} FROM support_tickets WHERE id = ?",
        (ticket_id,),
    ).fetchone()
    if ticket_row is None:
        return None

    ticket = dict(ticket_row)
    message_rows = connection.execute(
        f"""
        SELECT {MESSAGE_COLUMNS}
        FROM support_ticket_messages
        WHERE ticket_id = ?
        ORDER BY datetime(created_at), id
        """,
        (ticket_id,),
    ).fetchall()
    ticket["messages"] = [dict(row) for row in message_rows]
    ticket["message_count"] = len(ticket["messages"])
    return ticket


def get_ticket(ticket_id):
    with closing(get_database_connection()) as connection:
        return _get_ticket_with_connection(connection, ticket_id)


def create_ticket(ticket_values, created_at):
    """Create a ticket and its opening customer message atomically."""
    with closing(get_database_connection()) as connection:
        cursor = connection.execute(
            """
            INSERT INTO support_tickets (
                customer_name, customer_email, subject, category, priority,
                status, assigned_to, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'open', NULL, ?, ?)
            """,
            (
                ticket_values["customer_name"],
                ticket_values["customer_email"],
                ticket_values["subject"],
                ticket_values["category"],
                ticket_values["priority"],
                created_at,
                created_at,
            ),
        )
        ticket_id = cursor.lastrowid
        connection.execute(
            """
            INSERT INTO support_ticket_messages (
                ticket_id, sender_role, author_name, message, created_at
            ) VALUES (?, 'customer', ?, ?, ?)
            """,
            (
                ticket_id,
                ticket_values["customer_name"],
                ticket_values["message"],
                created_at,
            ),
        )
        ticket = _get_ticket_with_connection(connection, ticket_id)
        connection.commit()

    return ticket


def update_ticket(ticket_id, ticket_values, updated_at):
    with closing(get_database_connection()) as connection:
        cursor = connection.execute(
            """
            UPDATE support_tickets
            SET category = ?, priority = ?, status = ?, assigned_to = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                ticket_values["category"],
                ticket_values["priority"],
                ticket_values["status"],
                ticket_values["assigned_to"],
                updated_at,
                ticket_id,
            ),
        )
        if cursor.rowcount == 0:
            return None

        ticket = _get_ticket_with_connection(connection, ticket_id)
        connection.commit()

    return ticket


def delete_ticket(ticket_id):
    with closing(get_database_connection()) as connection:
        cursor = connection.execute(
            "DELETE FROM support_tickets WHERE id = ?",
            (ticket_id,),
        )
        if cursor.rowcount == 0:
            return False

        connection.commit()
    return True


def create_ticket_message(ticket_id, sender_role, message, created_at):
    with closing(get_database_connection()) as connection:
        ticket = connection.execute(
            """
            SELECT customer_name, assigned_to
            FROM support_tickets
            WHERE id = ?
            """,
            (ticket_id,),
        ).fetchone()
        if ticket is None:
            return None

        author_name = (
            ticket["customer_name"]
            if sender_role == "customer"
            else ticket["assigned_to"] or "Support staff"
        )
        cursor = connection.execute(
            """
            INSERT INTO support_ticket_messages (
                ticket_id, sender_role, author_name, message, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (ticket_id, sender_role, author_name, message, created_at),
        )
        connection.execute(
            "UPDATE support_tickets SET updated_at = ? WHERE id = ?",
            (created_at, ticket_id),
        )
        message_row = connection.execute(
            f"""
            SELECT {MESSAGE_COLUMNS}
            FROM support_ticket_messages
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()
        connection.commit()

    return dict(message_row)
