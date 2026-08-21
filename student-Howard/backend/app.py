import sqlite3, os
from flask import Flask, request, jsonify

app = Flask(__name__)
DB = os.path.join(os.path.dirname(__file__), "..", "database", "orders.db")

def get_db():
  conn = sqlite3.connect(DB)
  conn.row_factory = sqlite3.Row
  return conn

def rows_to_list(rows):
  return [dict(r) for r in rows]

# Orders
@app.route("/orders", methods=["GET"])
def list_orders():
    conn = get_db()
    rows = conn.execute("SELECT * FROM orders").fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))

@app.route("/orders/<int:order_id>", methods=["GET"])
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

@app.route("/orders", methods=["POST"])
def create_order():
    d = request.get_json()
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO orders (customer_id, order_date, status, total) VALUES (?,?,?,?)",
        (d["customer_id"], d["order_date"], d.get("status", "pending"), d["total"])
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"order_id": new_id}), 201

@app.route("/orders/<int:order_id>/status", methods=["PATCH"])
def update_order_status(order_id):
    d = request.get_json()
    conn = get_db()
    conn.execute("UPDATE orders SET status=? WHERE order_id=?", (d["status"], order_id))
    conn.commit()
    conn.close()
    return jsonify({"order_id": order_id, "status": d["status"]})

@app.route("/orders/<int:order_id>", methods=["DELETE"])
def delete_order(order_id):
    conn = get_db()
    conn.execute("DELETE FROM order_items WHERE order_id=?", (order_id,))
    conn.execute("DELETE FROM orders WHERE order_id=?", (order_id,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": order_id})

# Returns 
@app.route("/returns", methods=["GET"])
def list_returns():
    conn = get_db()
    rows = conn.execute("SELECT * FROM returns").fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))

@app.route("/returns", methods=["POST"])
def create_return():
    d = request.get_json()
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO returns (order_id, reason, status, created_at) VALUES (?,?,?,?)",
        (d["order_id"], d["reason"], d.get("status", "requested"), d["created_at"])
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"return_id": new_id}), 201

@app.route("/returns/<int:return_id>/status", methods=["PATCH"])
def update_return_status(return_id):
    d = request.get_json()
    conn = get_db()
    conn.execute("UPDATE returns SET status=? WHERE return_id=?", (d["status"], return_id))
    conn.commit()
    conn.close()
    return jsonify({"return_id": return_id, "status": d["status"]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
