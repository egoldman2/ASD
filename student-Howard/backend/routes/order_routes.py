import os
import sqlite3
import subprocess
import requests
from flask import Blueprint, current_app, g, jsonify, request
from shared.feature_flags import feature_enabled

order_blueprint = Blueprint(
    "order_returns",
    __name__,
    url_prefix="/api/order-returns",
)

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "database", "orders.db")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/api/generate"
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:0.5b")


def _ensure_db():
    """Seed the database if it does not exist (shared backend doesn't run seed.py)."""
    if not os.path.exists(DB):
        schema_dir = os.path.dirname(DB)
        seed_path = os.path.join(schema_dir, "seed.py")
        if os.path.exists(seed_path):
            subprocess.run(["python", "seed.py"], cwd=schema_dir, check=False)


_ensure_db()


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def rows_to_list(rows):
    return [dict(r) for r in rows]


def ask_ollama(prompt):
    if not feature_enabled():
        raise requests.RequestException("AI mode is disabled.")
    resp = requests.post(OLLAMA_URL, json={"model": MODEL, "prompt": prompt, "stream": False}, timeout=60)
    resp.raise_for_status()
    return resp.json()["response"].strip()


def current_user():
    user = getattr(g, "authenticated_user", None)
    if user is None and current_app.config.get("TESTING"):
        return {"id": 1, "role": "admin"}
    return user


def authentication_failure():
    return jsonify({"error": "You must sign in."}), 401


def administrator_failure():
    return jsonify({"error": "Administrator access required."}), 403


def customer_id(user):
    return None if user.get("role") == "admin" else user.get("id")


def order_for_user(conn, order_id, user):
    owner_id = customer_id(user)
    if owner_id is None:
        return conn.execute(
            "SELECT * FROM orders WHERE order_id=?",
            (order_id,),
        ).fetchone()
    return conn.execute(
        "SELECT * FROM orders WHERE order_id=? AND customer_id=?",
        (order_id, owner_id),
    ).fetchone()


# ---------- Orders ----------
@order_blueprint.get("/orders")
def list_orders():
    user = current_user()
    if user is None:
        return authentication_failure()

    conn = get_db()
    owner_id = customer_id(user)
    if owner_id is None:
        rows = conn.execute("SELECT * FROM orders").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM orders WHERE customer_id=?",
            (owner_id,),
        ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@order_blueprint.get("/orders/<int:order_id>")
def get_order(order_id):
    user = current_user()
    if user is None:
        return authentication_failure()

    conn = get_db()
    order = order_for_user(conn, order_id, user)
    items = []
    if order is not None:
        items = conn.execute(
            "SELECT * FROM order_items WHERE order_id=?",
            (order_id,),
        ).fetchall()
    conn.close()
    if order is None:
        return jsonify({"error": "not found"}), 404
    result = dict(order)
    result["items"] = rows_to_list(items)
    return jsonify(result)


@order_blueprint.post("/orders")
def create_order():
    user = current_user()
    if user is None:
        return authentication_failure()

    d = request.get_json() or {}
    owner_id = customer_id(user)
    requested_customer_id = d.get("customer_id") if owner_id is None else owner_id
    if requested_customer_id is None:
        return jsonify({"error": "A customer ID is required."}), 400

    conn = get_db()
    cur = conn.execute(
        "INSERT INTO orders (customer_id, order_date, status, total) VALUES (?,?,?,?)",
        (requested_customer_id, d["order_date"], d.get("status", "pending"), d["total"]),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"order_id": new_id}), 201


@order_blueprint.patch("/orders/<int:order_id>/status")
def update_order_status(order_id):
    user = current_user()
    if user is None:
        return authentication_failure()
    if user.get("role") != "admin":
        return administrator_failure()

    d = request.get_json()
    conn = get_db()
    conn.execute("UPDATE orders SET status=? WHERE order_id=?", (d["status"], order_id))
    conn.commit()
    conn.close()
    return jsonify({"order_id": order_id, "status": d["status"]})


@order_blueprint.delete("/orders/<int:order_id>")
def delete_order(order_id):
    user = current_user()
    if user is None:
        return authentication_failure()
    if user.get("role") != "admin":
        return administrator_failure()

    conn = get_db()
    conn.execute("DELETE FROM order_items WHERE order_id=?", (order_id,))
    conn.execute("DELETE FROM orders WHERE order_id=?", (order_id,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": order_id})


# ---------- Returns ----------
@order_blueprint.get("/returns")
def list_returns():
    user = current_user()
    if user is None:
        return authentication_failure()

    conn = get_db()
    owner_id = customer_id(user)
    if owner_id is None:
        rows = conn.execute("SELECT * FROM returns").fetchall()
    else:
        rows = conn.execute(
            """
            SELECT returns.*
            FROM returns
            JOIN orders ON orders.order_id = returns.order_id
            WHERE orders.customer_id=?
            """,
            (owner_id,),
        ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@order_blueprint.post("/returns")
def create_return():
    user = current_user()
    if user is None:
        return authentication_failure()

    d = request.get_json() or {}
    conn = get_db()
    if order_for_user(conn, d.get("order_id"), user) is None:
        conn.close()
        return jsonify({"error": "Order not found."}), 404

    cur = conn.execute(
        "INSERT INTO returns (order_id, reason, status, created_at) VALUES (?,?,?,?)",
        (d["order_id"], d["reason"], d.get("status", "requested"), d["created_at"]),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"return_id": new_id}), 201


@order_blueprint.patch("/returns/<int:return_id>/status")
def update_return_status(return_id):
    user = current_user()
    if user is None:
        return authentication_failure()
    if user.get("role") != "admin":
        return administrator_failure()

    d = request.get_json()
    conn = get_db()
    conn.execute("UPDATE returns SET status=? WHERE return_id=?", (d["status"], return_id))
    conn.commit()
    conn.close()
    return jsonify({"return_id": return_id, "status": d["status"]})


# ---------- HTML fragments (for HTMX) ----------
@order_blueprint.get("/orders/html")
def orders_html():
    user = current_user()
    if user is None:
        return authentication_failure()
    conn = get_db()
    owner_id = customer_id(user)
    is_admin = owner_id is None
    if is_admin:
        rows = conn.execute("SELECT * FROM orders").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM orders WHERE customer_id=?",
            (owner_id,),
        ).fetchall()
    conn.close()
    if is_admin:
        html = "<table><tr><th>Order ID</th><th>Customer ID</th><th>Date</th><th>Status</th><th>Total</th></tr>"
        for r in rows:
            html += (f"<tr><td>{r['order_id']}</td><td>{r['customer_id']}</td>"
                     f"<td>{r['order_date'][:10]}</td><td>{r['status'].capitalize()}</td><td>${r['total']}</td></tr>")
    else:
        html = "<table><tr><th>Order ID</th><th>Date</th><th>Status</th><th>Total</th></tr>"
        for r in rows:
            html += (f"<tr><td>{r['order_id']}</td>"
                     f"<td>{r['order_date'][:10]}</td><td>{r['status'].capitalize()}</td><td>${r['total']}</td></tr>")
    html += "</table>"
    return html


@order_blueprint.get("/returns/html")
def returns_html():
    user = current_user()
    if user is None:
        return authentication_failure()

    conn = get_db()
    owner_id = customer_id(user)
    if owner_id is None:
        rows = conn.execute("SELECT * FROM returns").fetchall()
    else:
        rows = conn.execute(
            """
            SELECT returns.*
            FROM returns
            JOIN orders ON orders.order_id = returns.order_id
            WHERE orders.customer_id=?
            """,
            (owner_id,),
        ).fetchall()
    conn.close()
    html = "<table><tr><th>Return ID</th><th>Order ID</th><th>Reason</th><th>Status</th></tr>"
    for r in rows:
        html += (f"<tr><td>{r['return_id']}</td><td>{r['order_id']}</td>"
                 f"<td>{r['reason'].capitalize()}</td><td>{r['status'].capitalize()}</td></tr>")
    html += "</table>"
    return html


# ---------- AI advice (advisory only, never writes to DB) ----------
@order_blueprint.get("/returns/<int:return_id>/advice")
def return_advice(return_id):
    user = current_user()
    if user is None:
        return authentication_failure()

    conn = get_db()
    ret = conn.execute("SELECT * FROM returns WHERE return_id=?", (return_id,)).fetchone()
    if ret is None:
        conn.close()
        return jsonify({"error": "not found"}), 404
    order = conn.execute("SELECT * FROM orders WHERE order_id=?", (ret["order_id"],)).fetchone()
    if order is None or (
        customer_id(user) is not None
        and order["customer_id"] != customer_id(user)
    ):
        conn.close()
        return jsonify({"error": "not found"}), 404
    conn.close()

    prompt = (
        "You are a retail customer-service assistant. "
        "Summarise the order problem and recommend the next action. "
        "Do NOT change any status yourself - only advise.\n\n"
        f"Return reason: {ret['reason']}\n"
        f"Current return status: {ret['status']}\n"
        f"Order status: {order['status'] if order else 'unknown'}\n"
        f"Order total: {order['total'] if order else 'unknown'}\n\n"
        "Give a 2-sentence summary and one recommended action."
    )
    advice = ask_ollama(prompt)
    return jsonify({
        "return_id": return_id,
        "ai_summary": advice,
        "note": "Advisory only. Use the status endpoint to actually change status.",
    })


# ---------- Release 1: MCP integration ----------
import asyncio as _asyncio

MCP_ENABLED = os.environ.get("MCP_ENABLED", "true").lower() == "true"
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:8765/mcp")
MCP_TIMEOUT_SECONDS = float(os.environ.get("MCP_TIMEOUT_SECONDS", "15"))


async def _mcp_call(tool_name, arguments):
    import json
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(MCP_SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            if result.structuredContent is not None:
                return result.structuredContent
            for block in result.content:
                if getattr(block, "type", None) == "text":
                    try:
                        return json.loads(block.text)
                    except ValueError:
                        return {"text": block.text}
            return {}


def call_mcp_tool(tool_name, arguments):
    """Call a tool on the shared MCP server; frontend reaches MCP only via here."""
    if not MCP_ENABLED:
        return {
            "success": False,
            "tool": tool_name,
            "result": None,
            "error": {"code": "MCP_DISABLED",
                      "message": "MCP is disabled in this environment."},
        }
    try:
        return _asyncio.run(
            _asyncio.wait_for(_mcp_call(tool_name, arguments),
                              timeout=MCP_TIMEOUT_SECONDS)
        )
    except Exception as exc:
        return {
            "success": False,
            "tool": tool_name,
            "result": None,
            "error": {"code": "MCP_UNAVAILABLE",
                      "message": f"Could not reach the MCP server: {exc}"},
        }


@order_blueprint.get("/mcp/order-status/<int:order_id>")
def mcp_order_status(order_id):
    return jsonify(call_mcp_tool("howard_get_order_status", {"order_id": order_id}))


@order_blueprint.get("/mcp/return-details/<int:return_id>")
def mcp_return_details(return_id):
    return jsonify(call_mcp_tool("howard_get_return_details", {"return_id": return_id}))


# ---------- Release 1: RAG integration ----------
RAG_ENABLED = os.environ.get("RAG_ENABLED", "true").lower() == "true"
RAG_SERVER_URL = os.environ.get("RAG_SERVER_URL", "http://127.0.0.1:5003").rstrip("/")
RAG_TIMEOUT_SECONDS = float(os.environ.get("RAG_CLIENT_TIMEOUT_SECONDS", "60"))


@order_blueprint.post("/rag/answer")
def rag_answer():
    """Send a question to the shared RAG server and return its grounded answer."""
    if not RAG_ENABLED:
        return jsonify({
            "success": False, "operation": "answer_question", "data": None,
            "citations": [], "confidence": None, "insufficient_context": False,
            "error": {"code": "RAG_DISABLED",
                      "message": "RAG is disabled in this environment."},
        }), 503

    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    if not question:
        return jsonify({
            "success": False, "operation": "answer_question", "data": None,
            "citations": [], "confidence": None, "insufficient_context": False,
            "error": {"code": "INVALID_ARGUMENT",
                      "message": "question must be a non-empty string."},
        }), 400

    payload = {"question": question}
    scope = body.get("scope")
    if scope:
        payload["scope"] = scope

    try:
        resp = requests.post(RAG_SERVER_URL + "/answer", json=payload,
                             timeout=RAG_TIMEOUT_SECONDS)
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as exc:
        return jsonify({
            "success": False, "operation": "answer_question", "data": None,
            "citations": [], "confidence": None, "insufficient_context": False,
            "error": {"code": "RAG_UNAVAILABLE",
                      "message": f"Could not reach the RAG server: {exc}"},
        }), 503
