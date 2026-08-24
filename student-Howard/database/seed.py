import sqlite3, os
from datetime import datetime, timedelta

DB = os.path.join(os.path.dirname(__file__), "orders.db")

conn = sqlite3.connect(DB)
with open(os.path.join(os.path.dirname(__file__), "schema.sql")) as f:
  conn.executescript(f.read())

cur = conn.cursor()
# clear existing so rerunning is safe
cur.execute("DELETE FROM returns")
cur.execute("DELETE FROM order_items")
cur.execute("DELETE FROM orders")
cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('orders','order_items','returns')")

statuses = ["pending", "shipped", "delivered", "cancelled"]
base = datetime(2026, 7, 1)

# 12 orders
for i in range (1, 13):
  cur.execute(
    "INSERT INTO orders (order_id, customer_id, order_date, status, total) VALUES (?,?,?,?,?)",
    (i, 100 + i, (base + timedelta(days=i)).isoformat(), statuses[i % 4], round(20 + i * 7.5, 2))
  )

# 12 order_items (at least one per order)
for i in range (1, 13):
  cur.execute(
    "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?,?,?,?)",
    (i, 200 + i, (i % 3) + 1, round(9.99 + i, 2))
  )

# 12 returns
reasons = ["wrong size", "damaged on arrival", "wrong colour", "changed mind",
           "faulty item", "late delivery", "missing part", "not as described",
           "duplicate order", "better price elsewhere", "wrong item sent", "quality issue"]
for i in range(1,13):
  cur.execute(
    "INSERT INTO returns (order_id, reason, status, created_at) VALUES (?,?,?,?)",
    (i, reasons[i - 1], "requested", (base + timedelta(days=i + 2)).isoformat())
  )

conn.commit()
conn.close()
print("Seeded orders.db with 12 orders, 12 order_items, 12 returns.")
