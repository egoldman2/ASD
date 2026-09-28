"""Whole-queue aggregates and deterministic attention rules with a fixed clock."""

from contextlib import closing
from importlib import import_module

import pytest
import requests

database = import_module("student-Ethan Goldman.database_service.database")
database_app = import_module("student-Ethan Goldman.database_service.app")
OBSERVED_AT = "2026-09-27T12:00:00Z"


@pytest.fixture
def empty_queue(support_stack, monkeypatch):
    with closing(database.get_database_connection(support_stack.database_path)) as connection:
        with connection:
            connection.execute("DELETE FROM support_tickets")
    monkeypatch.setattr(database_app, "_now", lambda: OBSERVED_AT)
    return support_stack


def ticket(stack, *, status="open", priority="medium", assigned_to="Ethan Goldman",
           category="delivery", updated_at="2026-09-27T11:00:00Z", sender="staff", message_at=None):
    result = database.create_ticket({
        "customer_user_id": "2", "customer_name_snapshot": "Jane Hidden",
        "customer_email_snapshot": "jane.private@example.test",
        "subject": "Delivery case for Jane Hidden", "message": "Opening question",
    }, "2026-09-01T00:00:00Z", stack.database_path)
    database.create_ticket_message(result["id"], {
        "sender_role": sender, "author_name": "Jane Hidden" if sender == "customer" else "Ethan Goldman",
        "message": "Latest message",
    }, message_at or updated_at, stack.database_path)
    database.update_ticket(result["id"], {
        "status": status, "priority": priority, "assigned_to": assigned_to, "category": category,
    }, updated_at, stack.database_path)
    return result["id"]


def test_summary_counts_full_filtered_queue_without_message_reads(empty_queue, monkeypatch):
    stack = empty_queue
    statuses = ("needs_triage", "open", "pending", "solved")
    priorities = ("low", "medium", "high", "urgent", "unclassified")
    for index in range(60):
        ticket(stack, status=statuses[index % 4], priority=priorities[index % 5],
               assigned_to=None if index % 2 == 0 else "Ethan Goldman")
    queries = []
    connect = database.get_database_connection

    def traced(path=None):
        connection = connect(path)
        connection.set_trace_callback(queries.append)
        return connection

    monkeypatch.setattr(database, "get_database_connection", traced)
    admin = stack.admin()
    endpoint = stack.backend.url + "/api/support/admin/tool-data/summary"
    response = admin.get(endpoint, timeout=10)
    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 60 and result["observed_at"] == OBSERVED_AT
    assert result["status_counts"] == dict.fromkeys(statuses, 15)
    assert result["priority_counts"] == dict.fromkeys(priorities, 12)
    assert result["unresolved"] == 45 and result["unresolved_unassigned"] == 30
    assert not any("support_ticket_messages" in query for query in queries)
    assert "Jane Hidden" not in str(result)
    assert "customer" not in str(result)
    unassigned = admin.get(endpoint, params={"assigned_to": "unassigned"}, timeout=10).json()
    assert unassigned["total"] == unassigned["unresolved"] == unassigned["unresolved_unassigned"] == 30
    assigned = admin.get(endpoint, params={"assigned_to": "ethan goldman", "category": "delivery"}, timeout=10).json()
    assert assigned["total"] == 30 and assigned["unresolved_unassigned"] == 0
    page = admin.get(stack.backend.url + "/api/support/admin/tool-data/tickets", timeout=10).json()
    assert page["total"] == 60 and len(page["tickets"]) == 20
    empty = admin.get(endpoint, params={"category": "account"}, timeout=10).json()
    assert empty["total"] == empty["unresolved"] == empty["unresolved_unassigned"] == 0
    assert set(empty["status_counts"].values()) == set(empty["priority_counts"].values()) == {0}


def test_attention_returns_all_reasons_and_excludes_solved(empty_queue):
    stack = empty_queue
    ids = {
        "all": ticket(stack, status="needs_triage", priority="urgent", assigned_to=None,
                      sender="customer", updated_at="2026-09-25T12:00:00Z"),
        "solved": ticket(stack, status="solved", priority="urgent", assigned_to=None,
                         sender="customer", updated_at="2026-09-20T00:00:00Z"),
        "triage": ticket(stack, status="needs_triage"),
        "unassigned": ticket(stack, assigned_to=None),
        "priority": ticket(stack, priority="high"),
        "reply": ticket(stack, sender="customer"),
        "inactive": ticket(stack, updated_at="2026-09-25T14:00:00+02:00"),
        "recent": ticket(stack, updated_at="2026-09-25T12:00:01Z"),
        "new_message": ticket(stack, updated_at="2026-09-20T00:00:00Z",
                              message_at="2026-09-27T11:00:00Z"),
        "new_update": ticket(stack, message_at="2026-09-20T00:00:00Z"),
    }
    admin = stack.admin()
    endpoint = stack.backend.url + "/api/support/admin/tool-data/attention"
    result = admin.get(endpoint, timeout=10).json()
    by_id = {item["id"]: item for item in result["tickets"]}
    assert set(by_id) == {ids[key] for key in ("all", "triage", "unassigned", "priority", "reply", "inactive")}
    assert result["total"] == 6 and result["inactive_hours"] == 48 and result["observed_at"] == OBSERVED_AT
    reasons = lambda key: {reason["code"] for reason in by_id[ids[key]]["reasons"]}
    assert reasons("all") == {"needs_triage", "unassigned", "high_priority", "awaiting_staff_reply", "inactive"}
    for key, code in (("triage", "needs_triage"), ("unassigned", "unassigned"),
                      ("priority", "high_priority"), ("reply", "awaiting_staff_reply"), ("inactive", "inactive")):
        assert reasons(key) == {code}
    assert by_id[ids["all"]]["last_activity_at"] == "2026-09-25T12:00:00Z"
    assert "Jane Hidden" not in str(result) and "customer_user_id" not in str(result)
    # A later staff message changes the reply reason; ticket updates alone do not.
    database.create_ticket_message(ids["reply"], {"sender_role": "staff", "author_name": "Ethan Goldman",
                                                "message": "Staff responded"}, OBSERVED_AT, stack.database_path)
    replied = admin.get(endpoint, timeout=10).json()
    assert ids["reply"] not in {item["id"] for item in replied["tickets"]}


def test_attention_sorts_before_paging_and_respects_filters(empty_queue):
    stack = empty_queue
    urgent_new = ticket(stack, priority="urgent", updated_at="2026-09-27T11:00:00Z")
    urgent_old_a = ticket(stack, priority="urgent", updated_at="2026-09-26T11:00:00Z")
    urgent_old_b = ticket(stack, priority="urgent", updated_at="2026-09-26T11:00:00Z")
    high = ticket(stack, priority="high", updated_at="2026-09-20T11:00:00Z")
    medium = ticket(stack, priority="medium", assigned_to=None)
    low = ticket(stack, priority="low", assigned_to=None)
    unclassified = ticket(stack, priority="unclassified", assigned_to=None)
    account = ticket(stack, priority="urgent", category="account", assigned_to="Other staff")
    admin = stack.admin()
    endpoint = stack.backend.url + "/api/support/admin/tool-data/attention"
    expected = [urgent_old_a, urgent_old_b, urgent_new, high, medium, low, unclassified]
    actual = []
    for offset in range(0, 7, 2):
        page = admin.get(endpoint, params={"category": "delivery", "limit": 2, "offset": offset}, timeout=10).json()
        assert page["total"] == 7
        actual.extend(item["id"] for item in page["tickets"])
        assert page["next_offset"] == (offset + 2 if offset < 6 else None)
    assert actual == expected
    assigned = admin.get(endpoint, params={"assigned_to": "other staff"}, timeout=10).json()
    assert [item["id"] for item in assigned["tickets"]] == [account]
    empty = admin.get(endpoint, params={"category": "payment"}, timeout=10).json()
    assert empty["total"] == 0 and empty["tickets"] == [] and empty["truncated"] is False


def test_queue_routes_are_protected_and_bounded(empty_queue):
    stack = empty_queue
    admin, customer = stack.admin(), stack.customer()
    for path in ("/summary", "/attention"):
        endpoint = stack.backend.url + "/api/support/admin/tool-data" + path
        assert requests.get(endpoint, timeout=10).status_code == 401
        assert customer.get(endpoint, timeout=10).status_code == 403
        for query in ({"status": "open"}, {"category": "invalid"},
                      {"customer_user_id": "2"}, [("assigned_to", "a"), ("assigned_to", "b")]):
            assert admin.get(endpoint, params=query, timeout=10).status_code == 400
    endpoint = stack.backend.url + "/api/support/admin/tool-data/attention"
    for query in ({"inactive_hours": 0}, {"inactive_hours": 721}, {"inactive_hours": "48.1"},
                  {"limit": 51}, {"offset": -1}, {"offset": 10001}, {"inactive_hours": "9" * 5000}):
        assert admin.get(endpoint, params=query, timeout=10).status_code == 400
    for query in ({"inactive_hours": 1}, {"inactive_hours": 720}):
        assert admin.get(endpoint, params=query, timeout=10).status_code == 200
    internal = stack.database.url + "/api/tool-data/attention"
    for query in ({"inactive_hours": 721}, {"limit": 51}, {"status": "open"}):
        assert requests.get(internal, params=query, timeout=10).status_code == 400
