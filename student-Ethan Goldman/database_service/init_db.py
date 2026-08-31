"""Create, migrate, and seed the Customer Support SQLite database."""

from contextlib import closing
from datetime import datetime, timezone
import argparse
from pathlib import Path
import sys

try:
    from .database import DEFAULT_DATABASE_PATH, get_database_connection, get_database_path
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from database import DEFAULT_DATABASE_PATH, get_database_connection, get_database_path

SERVICE_DIRECTORY = Path(__file__).resolve().parent
SCHEMA_PATH = SERVICE_DIRECTORY / "schema.sql"
SEED_PATH = SERVICE_DIRECTORY / "seed.sql"
REQUIRED_TICKETS = {"id", "customer_user_id", "customer_name_snapshot", "customer_email_snapshot", "subject", "category", "priority", "status", "assigned_to", "triage_applied_by", "created_at", "updated_at"}
REQUIRED_MESSAGES = {"id", "ticket_id", "sender_role", "author_name", "message", "created_at"}
INDEX_NAMES = ("idx_support_tickets_owner", "idx_support_tickets_status", "idx_support_tickets_priority", "idx_support_tickets_category", "idx_support_tickets_assigned_to", "idx_support_tickets_created_at", "idx_support_ticket_messages_ticket_created")
AUTH_LINKED_SEED_OWNERS = {
    2001: ("5", "Mia Wilson", "mia@example.test"),
    2002: ("2", "Demo Customer", "customer@asd.local"),
    2003: ("3", "Ava Chen", "ava@example.test"),
    2004: ("6", "Noah Brown", "noah@example.test"),
    2005: ("4", "Liam Smith", "liam@example.test"),
    2006: ("9", "Zoe Thomas", "zoe@example.test"),
    2007: ("7", "Isla Taylor", "isla@example.test"),
    2008: ("8", "Jack Anderson", "jack@example.test"),
    2009: ("3", "Ava Chen", "ava@example.test"),
    2010: ("10", "Leo Martin", "leo@example.test"),
    2011: ("7", "Isla Taylor", "isla@example.test"),
    2012: ("4", "Liam Smith", "liam@example.test"),
}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _exists(connection, name):
    return connection.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone() is not None


def _columns(connection, name):
    return {row["name"]: row["notnull"] for row in connection.execute(f"PRAGMA table_info({name})")}


def _sql(connection, name):
    row = connection.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone()
    return (row["sql"] or "").lower() if row else ""


def _needs_ticket_rebuild(connection):
    if not _exists(connection, "support_tickets"):
        return False
    columns = _columns(connection, "support_tickets")
    if not REQUIRED_TICKETS.issubset(columns):
        return True
    if any(columns[field] != 1 for field in REQUIRED_TICKETS - {"id", "assigned_to", "triage_applied_by"}):
        return True
    table_sql = _sql(connection, "support_tickets")
    return (
        "unclassified" not in table_sql
        or "needs_triage" not in table_sql
        or "trim(triage_applied_by)) between 1 and 128" not in table_sql
    )


def _needs_message_rebuild(connection):
    if not _exists(connection, "support_ticket_messages"):
        return False
    columns = _columns(connection, "support_ticket_messages")
    return (not REQUIRED_MESSAGES.issubset(columns) or any(columns[field] != 1 for field in REQUIRED_MESSAGES - {"id"}) or "on delete cascade" not in _sql(connection, "support_ticket_messages"))


def _text(value):
    return "" if value is None else str(value).strip()


def _bounded(value, minimum, maximum, fallback):
    value = _text(value)
    return (value if len(value) >= minimum else fallback)[:maximum]


def _category(value):
    value = _text(value).casefold()
    value = {"shipping": "delivery", "shipment": "delivery", "billing": "payment", "technical": "account", "general": "other"}.get(value, value)
    return value if value in {"order", "return", "payment", "product", "delivery", "account", "other", "unclassified"} else "unclassified"


def _priority(value):
    value = _text(value).casefold()
    return value if value in {"low", "medium", "high", "urgent", "unclassified"} else "unclassified"


def _status(value):
    value = _text(value).casefold()
    if value in {"open", "pending", "solved", "needs_triage"}:
        return value
    return "solved" if value in {"closed", "resolved", "complete", "completed"} else "needs_triage"


def _ticket_values(row):
    keys = set(row.keys())
    ticket_id = row["id"]
    email_field = (
        "customer_email_snapshot"
        if "customer_email_snapshot" in keys
        else "customer_email"
    )
    name_field = (
        "customer_name_snapshot"
        if "customer_name_snapshot" in keys
        else "customer_name"
    )
    email = _text(row[email_field]) if email_field in keys else ""
    owner = _text(row["customer_user_id"]) if "customer_user_id" in keys else ""
    owner = owner or (
        f"legacy-email:{email.casefold()}" if email else f"legacy-ticket:{ticket_id}"
    )
    safe_email = _bounded(email, 3, 254, f"legacy-ticket-{ticket_id}@invalid.local")
    if "@" not in safe_email:
        safe_email = f"legacy-ticket-{ticket_id}@invalid.local"
    created = _text(row["created_at"]) if "created_at" in keys else ""
    created = created or _now()
    return {
        "id": ticket_id,
        "customer_user_id": owner,
        "customer_name_snapshot": _bounded(row[name_field] if name_field in keys else "", 2, 100, f"Legacy customer {ticket_id}"),
        "customer_email_snapshot": safe_email,
        "subject": _bounded(row["subject"] if "subject" in keys else "", 5, 160, f"Legacy support request {ticket_id}"),
        "category": _category(row["category"] if "category" in keys else ""),
        "priority": _priority(row["priority"] if "priority" in keys else ""),
        "status": _status(row["status"] if "status" in keys else ""),
        "assigned_to": _text(row["assigned_to"]) if "assigned_to" in keys and 2 <= len(_text(row["assigned_to"])) <= 100 else None,
        "triage_applied_by": _text(row["triage_applied_by"]) if "triage_applied_by" in keys and 1 <= len(_text(row["triage_applied_by"])) <= 128 else None,
        "created_at": created,
        "updated_at": _text(row["updated_at"]) if "updated_at" in keys and _text(row["updated_at"]) else created,
    }


def _message_values(row, tickets):
    keys = set(row.keys())
    ticket_id = row["ticket_id"] if "ticket_id" in keys else None
    if ticket_id not in tickets:
        return None
    ticket = tickets[ticket_id]
    role = _text(row["sender_role"]).casefold() if "sender_role" in keys else "customer"
    role = role if role in {"customer", "staff"} else "customer"
    author = _text(row["author_name"]) if "author_name" in keys else ""
    if not 2 <= len(author) <= 100:
        author = ticket["customer_name_snapshot"] if role == "customer" else ticket["assigned_to"] or "Support staff"
    return {"id": row["id"] if "id" in keys else None, "ticket_id": ticket_id, "sender_role": role, "author_name": author, "message": _bounded(row["message"] if "message" in keys else "", 1, 2000, "Legacy ticket message"), "created_at": _text(row["created_at"]) if "created_at" in keys and _text(row["created_at"]) else ticket["created_at"]}


def _embedded(row, ticket):
    keys, result = set(row.keys()), []
    if "message" in keys and _text(row["message"]):
        result.append({"ticket_id": ticket["id"], "sender_role": "customer", "author_name": ticket["customer_name_snapshot"], "message": _bounded(row["message"], 1, 2000, "Legacy ticket message"), "created_at": ticket["created_at"]})
    if "staff_response" in keys and _text(row["staff_response"]):
        result.append({"ticket_id": ticket["id"], "sender_role": "staff", "author_name": ticket["assigned_to"] or "Support staff", "message": _bounded(row["staff_response"], 1, 2000, "Legacy staff response"), "created_at": _text(row["responded_at"]) if "responded_at" in keys and _text(row["responded_at"]) else ticket["updated_at"]})
    return result


def _drop_indexes(connection):
    for name in INDEX_NAMES:
        connection.execute(f"DROP INDEX IF EXISTS {name}")


def _insert_tickets(connection, tickets):
    if tickets:
        columns = ("id", "customer_user_id", "customer_name_snapshot", "customer_email_snapshot", "subject", "category", "priority", "status", "assigned_to", "triage_applied_by", "created_at", "updated_at")
        connection.executemany(f"INSERT INTO support_tickets ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})", [tuple(ticket[column] for column in columns) for ticket in tickets])


def _insert_messages(connection, messages):
    with_ids = [message for message in messages if message.get("id") is not None]
    without_ids = [message for message in messages if message.get("id") is None]
    connection.executemany("INSERT INTO support_ticket_messages (id, ticket_id, sender_role, author_name, message, created_at) VALUES (?, ?, ?, ?, ?, ?)", [(m["id"], m["ticket_id"], m["sender_role"], m["author_name"], m["message"], m["created_at"]) for m in with_ids]) if with_ids else None
    connection.executemany("INSERT INTO support_ticket_messages (ticket_id, sender_role, author_name, message, created_at) VALUES (?, ?, ?, ?, ?)", [(m["ticket_id"], m["sender_role"], m["author_name"], m["message"], m["created_at"]) for m in without_ids]) if without_ids else None


def _rebuild_legacy(connection):
    old_tickets = connection.execute("SELECT * FROM support_tickets").fetchall()
    old_messages = connection.execute("SELECT * FROM support_ticket_messages").fetchall() if _exists(connection, "support_ticket_messages") else []
    tickets = [_ticket_values(row) for row in old_tickets]
    by_id = {ticket["id"]: ticket for ticket in tickets}
    messages = [_message_values(row, by_id) for row in old_messages]
    messages = [message for message in messages if message]
    keys = {(m["ticket_id"], m["sender_role"], m["message"]) for m in messages}
    for row, ticket in zip(old_tickets, tickets):
        for message in _embedded(row, ticket):
            key = (message["ticket_id"], message["sender_role"], message["message"])
            if key not in keys:
                messages.append(message); keys.add(key)
    connection.commit()
    connection.execute("PRAGMA foreign_keys = OFF")
    _drop_indexes(connection)
    connection.execute("ALTER TABLE support_tickets RENAME TO support_tickets_legacy")
    if _exists(connection, "support_ticket_messages"):
        connection.execute("ALTER TABLE support_ticket_messages RENAME TO support_ticket_messages_legacy")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    _insert_tickets(connection, tickets)
    _insert_messages(connection, messages)
    connection.execute("DROP TABLE IF EXISTS support_ticket_messages_legacy")
    connection.execute("DROP TABLE IF EXISTS support_tickets_legacy")
    connection.commit()
    connection.execute("PRAGMA foreign_keys = ON")


def _rebuild_messages(connection):
    rows = connection.execute("SELECT * FROM support_ticket_messages").fetchall()
    tickets = {row["id"]: dict(row) for row in connection.execute("SELECT * FROM support_tickets")}
    messages = [message for message in (_message_values(row, tickets) for row in rows) if message]
    connection.commit(); connection.execute("PRAGMA foreign_keys = OFF"); _drop_indexes(connection)
    connection.execute("ALTER TABLE support_ticket_messages RENAME TO support_ticket_messages_legacy")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8")); _insert_messages(connection, messages)
    connection.execute("DROP TABLE support_ticket_messages_legacy"); connection.commit(); connection.execute("PRAGMA foreign_keys = ON")


def _remap_legacy_seed_owners(connection):
    """One-way migration from pre-auth demo identifiers to real auth seed IDs."""
    remapped = 0
    for ticket_id, (owner_id, name, email) in AUTH_LINKED_SEED_OWNERS.items():
        cursor = connection.execute(
            """UPDATE support_tickets
               SET customer_user_id = ?, customer_name_snapshot = ?,
                   customer_email_snapshot = ?
               WHERE id = ? AND (
                   customer_user_id LIKE 'customer-%'
                   OR customer_user_id = ?
                   OR customer_user_id = ?
               )""",
            (
                owner_id,
                name,
                email,
                ticket_id,
                f"legacy-ticket:{ticket_id}",
                f"legacy-email:{email.casefold()}",
            ),
        )
        if cursor.rowcount:
            connection.execute(
                """UPDATE support_ticket_messages
                   SET author_name = ?
                   WHERE ticket_id = ? AND sender_role = 'customer'""",
                (name, ticket_id),
            )
            remapped += cursor.rowcount
    return remapped


def initialize_database(database_path=None, reset=False):
    path = get_database_path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    schema, seed = SCHEMA_PATH.read_text(encoding="utf-8"), SEED_PATH.read_text(encoding="utf-8")
    with closing(get_database_connection(path)) as connection:
        if reset:
            connection.execute("DROP TABLE IF EXISTS support_ticket_messages"); connection.execute("DROP TABLE IF EXISTS support_tickets"); connection.commit()
        migrated = False
        if _needs_ticket_rebuild(connection):
            _rebuild_legacy(connection); migrated = True
        else:
            connection.executescript(schema)
            if _needs_message_rebuild(connection):
                _rebuild_messages(connection); migrated = True
        connection.execute("PRAGMA foreign_keys = ON")
        remapped = _remap_legacy_seed_owners(connection)
        counts = [connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("support_tickets", "support_ticket_messages")]
        seeded = False
        if counts[0] < 12 or counts[1] < 12:
            connection.executescript(seed); seeded = True
        connection.commit()
        counts = [connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("support_tickets", "support_ticket_messages")]
        if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError("SQLite foreign key enforcement could not be enabled")
    return {"initialized": reset or migrated or seeded or bool(remapped), "tickets": counts[0], "messages": counts[1], "path": str(path)}


def main():
    parser = argparse.ArgumentParser(description="Create or migrate the Customer Support database API database.")
    parser.add_argument("--database-path", default=None, help=f"SQLite path (default: DATABASE_PATH or {DEFAULT_DATABASE_PATH}).")
    parser.add_argument("--reset", action="store_true", help="Replace support tables with the current schema and seed data.")
    args = parser.parse_args(); result = initialize_database(args.database_path, reset=args.reset)
    action = "initialized" if result["initialized"] else "already initialized"
    print(f"Database {action}: {result['path']} ({result['tickets']} tickets, {result['messages']} messages)")


if __name__ == "__main__":
    main()
