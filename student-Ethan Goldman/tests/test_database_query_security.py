"""Exercise SQL-looking data through the real parameterized SQLite helpers."""

from importlib import import_module
import sqlite3


def test_query_fragments_keep_values_literal_and_do_not_touch_other_tickets(tmp_path):
    database = import_module('student-Ethan Goldman.database_service.database')
    initialize = import_module('student-Ethan Goldman.database_service.init_db').initialize_database
    path = tmp_path / 'query-security.db'
    initialize(path)
    with sqlite3.connect(path) as connection:
        before_tickets = connection.execute('SELECT * FROM support_tickets ORDER BY id').fetchall()
        before_messages = connection.execute('SELECT * FROM support_ticket_messages ORDER BY id').fetchall()
    payload = "' OR 1=1 -- %_"
    stamp = '2026-10-17T00:00:00Z'
    ticket = database.create_ticket({
        'customer_user_id': '2', 'customer_name_snapshot': 'SQL Fixture',
        'customer_email_snapshot': 'sql-fixture@example.test',
        'subject': payload, 'message': payload,
    }, stamp, path)
    ticket_id = ticket['id']
    filters = {'search': payload, "status='open' OR 1=1 --": 'ignored'}
    tickets, _ = database.get_tickets(filters, path)
    assert [row['id'] for row in tickets] == [ticket_id]
    summaries = database.search_ticket_summaries(filters, database_path=path)
    assert summaries['total'] == 1 and summaries['tickets'][0]['id'] == ticket_id
    assert database.get_queue_summary(filters, database_path=path)['total'] == 1
    attention = database.get_tickets_needing_attention(filters, observed_at=stamp, database_path=path)
    assert attention['total'] == 1 and attention['tickets'][0]['id'] == ticket_id
    assert database.get_tickets({'owner_user_id': "2' OR 1=1 --"}, path)[0] == []
    assert database.get_ticket('2002 OR 1=1', path) is None
    assert database.get_ticket(ticket_id, path, owner_user_id="2' OR 1=1 --") is None
    assert database.get_ticket_context(ticket_id, database_path=path)['messages'][0]['message'] == payload
    message = database.create_ticket_message(ticket_id, {
        'sender_role': 'staff', 'author_name': 'SQL Fixture', 'message': payload,
    }, stamp, path)
    assert message['message'] == payload
    assignment = "reviewer', status='solved' WHERE 1=1 --"
    updated = database.update_ticket(ticket_id, {
        'assigned_to': assignment, "status='solved' WHERE 1=1 --": 'solved',
    }, stamp, path)
    assert updated['assigned_to'] == assignment and updated['status'] == 'needs_triage'
    assert database.get_ticket(ticket_id, path)['subject'] == payload
    assert database.get_ticket_context(ticket_id, database_path=path)['message_count'] == 2
    assert database.delete_ticket(ticket_id, path)
    with sqlite3.connect(path) as connection:
        assert connection.execute('SELECT * FROM support_tickets ORDER BY id').fetchall() == before_tickets
        assert connection.execute('SELECT * FROM support_ticket_messages ORDER BY id').fetchall() == before_messages


def test_legacy_migration_keeps_sql_looking_values_literal_and_is_idempotent(tmp_path):
    initialize = import_module('student-Ethan Goldman.database_service.init_db').initialize_database
    database = import_module('student-Ethan Goldman.database_service.database')
    path = tmp_path / 'legacy-query-security.db'
    payload = "Legacy ' OR 1=1; DROP TABLE support_tickets; --"
    with sqlite3.connect(path) as connection:
        connection.execute('''CREATE TABLE support_tickets (
            id INTEGER PRIMARY KEY, customer_name TEXT, customer_email TEXT,
            subject TEXT, category TEXT, priority TEXT, status TEXT,
            assigned_to TEXT, message TEXT, created_at TEXT, updated_at TEXT)''')
        connection.execute('INSERT INTO support_tickets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                           (77, payload, 'sql-fixture@example.test', payload, 'general', 'medium',
                            'open', None, payload, '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z'))
    first = initialize(path)
    ticket = database.get_ticket(77, path)
    assert ticket['customer_name_snapshot'] == ticket['subject'] == payload
    assert ticket['messages'][0]['message'] == payload
    second = initialize(path)
    assert second['initialized'] is False
    assert (second['tickets'], second['messages']) == (first['tickets'], first['messages'])
    assert database.get_ticket(77, path) == ticket
