"""SQLite persistence for the independent Customer Support database service."""

from contextlib import closing
import os
from pathlib import Path
import sqlite3

DEFAULT_DATABASE_PATH = Path("/data/support_tickets.db")
TICKET_COLUMNS = ("id", "customer_user_id", "customer_name_snapshot", "customer_email_snapshot", "subject", "category", "priority", "status", "assigned_to", "triage_applied_by", "created_at", "updated_at")
MESSAGE_COLUMNS = ("id", "ticket_id", "sender_role", "author_name", "message", "created_at")
TICKET_SELECT = ", ".join(TICKET_COLUMNS)
MESSAGE_SELECT = ", ".join(MESSAGE_COLUMNS)
TICKET_SELECT_QUALIFIED = ", ".join(f"ticket.{column}" for column in TICKET_COLUMNS)


def get_database_path(database_path=None):
    return Path(database_path or os.getenv("DATABASE_PATH") or DEFAULT_DATABASE_PATH)


def get_database_connection(database_path=None):
    """Return a row-based connection with SQLite foreign keys enabled."""
    path = get_database_path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def _fetch_messages(connection, ticket_ids):
    if not ticket_ids:
        return {}
    placeholders = ", ".join("?" for _ in ticket_ids)
    rows = connection.execute(
        f"SELECT {MESSAGE_SELECT} FROM support_ticket_messages "
        f"WHERE ticket_id IN ({placeholders}) ORDER BY datetime(created_at), id",
        tuple(ticket_ids),
    ).fetchall()
    messages = {ticket_id: [] for ticket_id in ticket_ids}
    for row in rows:
        messages.setdefault(row["ticket_id"], []).append(dict(row))
    return messages


def _ticket_dict(row, messages):
    ticket = dict(row)
    ticket["messages"] = messages.get(ticket["id"], [])
    ticket["message_count"] = len(ticket["messages"])
    return ticket


def _ticket_where(filters=None):
    filters = filters or {}
    conditions, parameters = [], []
    search = filters.get("search")
    if search:
        value = str(search).casefold().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{value}%"
        conditions.append("(LOWER(ticket.customer_name_snapshot) LIKE ? ESCAPE '\\' OR LOWER(ticket.customer_email_snapshot) LIKE ? ESCAPE '\\' OR LOWER(ticket.subject) LIKE ? ESCAPE '\\' OR CAST(ticket.id AS TEXT) LIKE ? ESCAPE '\\')")
        parameters.extend([pattern] * 4)
    for field in ("category", "priority", "status"):
        if filters.get(field):
            conditions.append(f"ticket.{field} = ?")
            parameters.append(filters[field])
    assigned_to = filters.get("assigned_to")
    if assigned_to == "unassigned":
        conditions.append("ticket.assigned_to IS NULL")
    elif assigned_to:
        conditions.append("LOWER(ticket.assigned_to) = LOWER(?)")
        parameters.append(assigned_to)
    owner_user_id = filters.get("owner_user_id")
    if owner_user_id:
        conditions.append("ticket.customer_user_id = ?")
        parameters.append(owner_user_id)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return where, parameters


def get_tickets(filters=None, database_path=None):
    where, parameters = _ticket_where(filters)
    with closing(get_database_connection(database_path)) as connection:
        rows = connection.execute(
            f"SELECT {TICKET_SELECT_QUALIFIED} FROM support_tickets AS ticket {where} "
            "ORDER BY datetime(ticket.updated_at) DESC, ticket.id DESC",
            parameters,
        ).fetchall()
        messages = _fetch_messages(connection, [row["id"] for row in rows])
        tickets = [_ticket_dict(row, messages) for row in rows]
    counts = {status: sum(ticket["status"] == status for ticket in tickets) for status in ("needs_triage", "open", "pending", "solved")}
    return tickets, counts


def search_ticket_summaries(filters=None, limit=20, offset=0, database_path=None):
    """Page ticket rows in SQL without reading any conversation bodies."""
    where, parameters = _ticket_where(filters)
    with closing(get_database_connection(database_path)) as connection:
        total = connection.execute(
            f"SELECT COUNT(*) FROM support_tickets AS ticket {where}", parameters,
        ).fetchone()[0]
        rows = connection.execute(
            f"SELECT {TICKET_SELECT_QUALIFIED} FROM support_tickets AS ticket {where} "
            "ORDER BY datetime(ticket.updated_at) DESC, ticket.id DESC LIMIT ? OFFSET ?",
            [*parameters, limit, offset],
        ).fetchall()
    next_offset = offset + len(rows) if offset + len(rows) < total else None
    return {"tickets": [dict(row) for row in rows], "total": total,
            "limit": limit, "offset": offset, "next_offset": next_offset,
            "truncated": next_offset is not None, "filters": filters or {}}


def get_ticket_context(ticket_id, message_limit=20, database_path=None):
    """Return only the latest bounded messages, displayed chronologically."""
    with closing(get_database_connection(database_path)) as connection:
        row = connection.execute(
            f"SELECT {TICKET_SELECT} FROM support_tickets WHERE id = ?", (ticket_id,),
        ).fetchone()
        if row is None:
            return None
        count = connection.execute(
            "SELECT COUNT(*) FROM support_ticket_messages WHERE ticket_id = ?", (ticket_id,),
        ).fetchone()[0]
        messages = connection.execute(
            f"SELECT {MESSAGE_SELECT} FROM support_ticket_messages WHERE ticket_id = ? "
            "ORDER BY datetime(created_at) DESC, id DESC LIMIT ?", (ticket_id, message_limit),
        ).fetchall()
    return {**dict(row), "messages": [dict(message) for message in reversed(messages)],
            "message_count": count, "message_limit": message_limit,
            "messages_truncated": count > len(messages)}


def get_queue_summary(filters=None, observed_at=None, database_path=None):
    """Aggregate the whole filtered queue without loading tickets/messages."""
    where, parameters = _ticket_where(filters)
    statuses = ("needs_triage", "open", "pending", "solved")
    priorities = ("low", "medium", "high", "urgent", "unclassified")
    fields = ["COUNT(*) AS total"]
    fields.extend(f"COALESCE(SUM({field} = '{value}'), 0) AS {field}_{value}"
                  for field, values in (("status", statuses), ("priority", priorities)) for value in values)
    fields.extend(("COALESCE(SUM(status != 'solved'), 0) AS unresolved",
                   "COALESCE(SUM(status != 'solved' AND assigned_to IS NULL), 0) AS unresolved_unassigned"))
    with closing(get_database_connection(database_path)) as connection:
        row = connection.execute(
            f"SELECT {', '.join(fields)} FROM support_tickets AS ticket {where}", parameters,
        ).fetchone()
    return {"total": row["total"], "status_counts": {value: row[f"status_{value}"] for value in statuses},
            "priority_counts": {value: row[f"priority_{value}"] for value in priorities},
            "unresolved": row["unresolved"], "unresolved_unassigned": row["unresolved_unassigned"],
            "filters": filters or {}, "observed_at": observed_at}


ATTENTION_REASONS = {
    "needs_triage": "Needs triage",
    "unassigned": "No assignee",
    "high_priority": "High or urgent priority",
    "awaiting_staff_reply": "Latest message is from the customer",
    "inactive": "No recent ticket or message activity",
}


def get_tickets_needing_attention(filters=None, inactive_hours=48, limit=20, offset=0,
                                 observed_at=None, database_path=None):
    """Filter and sort recorded review reasons before applying pagination."""
    where, parameters = _ticket_where(filters)
    cte = f"""WITH scoped AS (
        SELECT ticket.*,
            (SELECT sender_role FROM support_ticket_messages WHERE ticket_id = ticket.id
             ORDER BY datetime(created_at) DESC, id DESC LIMIT 1) AS latest_sender,
            (SELECT created_at FROM support_ticket_messages WHERE ticket_id = ticket.id
             ORDER BY datetime(created_at) DESC, id DESC LIMIT 1) AS latest_message_at
        FROM support_tickets AS ticket {where}
    ), activity AS (
        SELECT *, CASE WHEN julianday(latest_message_at) > julianday(updated_at)
                       THEN latest_message_at ELSE updated_at END AS last_activity_at FROM scoped
    ), reasons AS (
        SELECT *, status = 'needs_triage' AS needs_triage, assigned_to IS NULL AS unassigned,
            priority IN ('high', 'urgent') AS high_priority,
            COALESCE(latest_sender = 'customer', 0) AS awaiting_staff_reply,
            julianday(last_activity_at) <= julianday(?, '-' || ? || ' hours') AS inactive
        FROM activity WHERE status != 'solved'
    ), flagged AS (
        SELECT * FROM reasons WHERE needs_triage OR unassigned OR high_priority OR awaiting_staff_reply OR inactive
    )"""
    parameters = [*parameters, observed_at, inactive_hours]
    with closing(get_database_connection(database_path)) as connection:
        total = connection.execute(cte + " SELECT COUNT(*) FROM flagged", parameters).fetchone()[0]
        rows = connection.execute(cte + """ SELECT * FROM flagged
            ORDER BY CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2
                     WHEN 'low' THEN 3 ELSE 4 END, julianday(last_activity_at), id LIMIT ? OFFSET ?""",
            [*parameters, limit, offset],
        ).fetchall()
    tickets = []
    for row in rows:
        ticket = {field: row[field] for field in TICKET_COLUMNS}
        ticket["last_activity_at"] = row["last_activity_at"]
        ticket["reasons"] = [{"code": code, "label": label} for code, label in ATTENTION_REASONS.items() if row[code]]
        tickets.append(ticket)
    next_offset = offset + len(tickets) if offset + len(tickets) < total else None
    return {"tickets": tickets, "total": total, "limit": limit, "offset": offset,
            "next_offset": next_offset, "truncated": next_offset is not None,
            "filters": filters or {}, "observed_at": observed_at, "inactive_hours": inactive_hours}


def get_ticket(ticket_id, database_path=None, owner_user_id=None):
    with closing(get_database_connection(database_path)) as connection:
        query = f"SELECT {TICKET_SELECT} FROM support_tickets WHERE id = ?"
        parameters = [ticket_id]
        if owner_user_id is not None:
            query += " AND customer_user_id = ?"
            parameters.append(str(owner_user_id))
        row = connection.execute(query, parameters).fetchone()
        if row is None:
            return None
        return _ticket_dict(row, _fetch_messages(connection, [ticket_id]))


def create_ticket(ticket_values, created_at, database_path=None):
    """Create the ticket and opening customer message atomically."""
    with closing(get_database_connection(database_path)) as connection:
        with connection:
            cursor = connection.execute(
                """INSERT INTO support_tickets (
                    customer_user_id, customer_name_snapshot, customer_email_snapshot,
                    subject, category, priority, status, assigned_to,
                    triage_applied_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'unclassified', 'unclassified', 'needs_triage', NULL, NULL, ?, ?)""",
                (ticket_values["customer_user_id"], ticket_values["customer_name_snapshot"], ticket_values["customer_email_snapshot"], ticket_values["subject"], created_at, created_at),
            )
            ticket_id = cursor.lastrowid
            connection.execute(
                "INSERT INTO support_ticket_messages (ticket_id, sender_role, author_name, message, created_at) VALUES (?, 'customer', ?, ?, ?)",
                (ticket_id, ticket_values["customer_name_snapshot"], ticket_values["message"], created_at),
            )
            row = connection.execute(f"SELECT {TICKET_SELECT} FROM support_tickets WHERE id = ?", (ticket_id,)).fetchone()
            return _ticket_dict(row, _fetch_messages(connection, [ticket_id]))


def create_ticket_message(ticket_id, message_values, created_at, database_path=None, owner_user_id=None):
    with closing(get_database_connection(database_path)) as connection:
        with connection:
            query = "SELECT customer_name_snapshot, assigned_to FROM support_tickets WHERE id = ?"
            parameters = [ticket_id]
            if owner_user_id is not None:
                query += " AND customer_user_id = ?"
                parameters.append(str(owner_user_id))
            ticket = connection.execute(query, parameters).fetchone()
            if ticket is None:
                return None
            author = message_values.get("author_name")
            if not author:
                author = ticket["customer_name_snapshot"] if message_values["sender_role"] == "customer" else ticket["assigned_to"] or "Support staff"
            cursor = connection.execute(
                "INSERT INTO support_ticket_messages (ticket_id, sender_role, author_name, message, created_at) VALUES (?, ?, ?, ?, ?)",
                (ticket_id, message_values["sender_role"], author, message_values["message"], created_at),
            )
            connection.execute("UPDATE support_tickets SET updated_at = ? WHERE id = ?", (created_at, ticket_id))
            row = connection.execute(f"SELECT {MESSAGE_SELECT} FROM support_ticket_messages WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)


def update_ticket(ticket_id, ticket_values, updated_at, database_path=None):
    allowed = ("category", "priority", "status", "assigned_to", "triage_applied_by")
    assignments, parameters = [], []
    for field in allowed:
        if field in ticket_values:
            assignments.append(f"{field} = ?")
            parameters.append(ticket_values[field])
    assignments.append("updated_at = ?")
    parameters.extend((updated_at, ticket_id))
    with closing(get_database_connection(database_path)) as connection:
        with connection:
            cursor = connection.execute(f"UPDATE support_tickets SET {', '.join(assignments)} WHERE id = ?", parameters)
            if cursor.rowcount == 0:
                return None
            row = connection.execute(f"SELECT {TICKET_SELECT} FROM support_tickets WHERE id = ?", (ticket_id,)).fetchone()
            return _ticket_dict(row, _fetch_messages(connection, [ticket_id]))


def delete_ticket(ticket_id, database_path=None):
    with closing(get_database_connection(database_path)) as connection:
        with connection:
            cursor = connection.execute("DELETE FROM support_tickets WHERE id = ?", (ticket_id,))
            return cursor.rowcount > 0
