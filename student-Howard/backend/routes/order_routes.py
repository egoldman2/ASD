import os
import sqlite3
import subprocess
import requests
from flask import Blueprint, jsonify, request

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
    resp = requests.post(OLLAMA_URL, json={"model": MODEL, "prompt": prompt, "stream": False})
    resp.raise_for_status()
    return resp.json()["response"].strip()


# ---------- Orders ----------
@order_blueprint.get("/orders")
def list_orders():
    conn = get_db()
    rows = conn.execute("SELECT * FROM orders").fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@order_blueprint.get("/orders/<int:order_id>")
def get_order(order_id):
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()
    items = conn.execute("SELECT * FROM order_items WHERE order_id=?", (order_id,)).fetchall()
    conn.close()
    if order is None:
        return jsonify({"error": "not found"}), 404
    result = dict(order)
    result["items"] = rows_to_list(items)
    return jsonify(result)


@order_blueprint.post("/orders")
def create_order():
    d = request.get_json()
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO orders (customer_id, order_date, status, total) VALUES (?,?,?,?)",
        (d["customer_id"], d["order_date"], d.get("status", "pending"), d["total"]),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"order_id": new_id}), 201


@order_blueprint.patch("/orders/<int:order_id>/status")
def update_order_status(order_id):
    d = request.get_json()
    conn = get_db()
    conn.execute("UPDATE orders SET status=? WHERE order_id=?", (d["status"], order_id))
    conn.commit()
    conn.close()
    return jsonify({"order_id": order_id, "status": d["status"]})


@order_blueprint.delete("/orders/<int:order_id>")
def delete_order(order_id):
    conn = get_db()
    conn.execute("DELETE FROM order_items WHERE order_id=?", (order_id,))
    conn.execute("DELETE FROM orders WHERE order_id=?", (order_id,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": order_id})


# ---------- Returns ----------
@order_blueprint.get("/returns")
def list_returns():
    conn = get_db()
    rows = conn.execute("SELECT * FROM returns").fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@order_blueprint.post("/returns")
def create_return():
    d = request.get_json()
    conn = get_db()
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
    d = request.get_json()
    conn = get_db()
    conn.execute("UPDATE returns SET status=? WHERE return_id=?", (d["status"], return_id))
    conn.commit()
    conn.close()
    return jsonify({"return_id": return_id, "status": d["status"]})


# ---------- HTML fragments (for HTMX) ----------
@order_blueprint.get("/orders/html")
def orders_html():
    conn = get_db()
    rows = conn.execute("SELECT * FROM orders").fetchall()
    conn.close()
    html = "<table><tr><th>Order ID</th><th>Customer ID</th><th>Date</th><th>Status</th><th>Total</th></tr>"
    for r in rows:
        html += (f"<tr><td>{r['order_id']}</td><td>{r['customer_id']}</td>"
                 f"<td>{r['order_date'][:10]}</td><td>{r['status'].capitalize()}</td><td>${r['total']}</td></tr>")
    html += "</table>"
    return html


@order_blueprint.get("/returns/html")
def returns_html():
    conn = get_db()
    rows = conn.execute("SELECT * FROM returns").fetchall()
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
    conn = get_db()
    ret = conn.execute("SELECT * FROM returns WHERE return_id=?", (return_id,)).fetchone()
    if ret is None:
        conn.close()
        return jsonify({"error": "not found"}), 404
    order = conn.execute("SELECT * FROM orders WHERE order_id=?", (ret["order_id"],)).fetchone()
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