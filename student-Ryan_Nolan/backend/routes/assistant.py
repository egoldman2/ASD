import sys
from pathlib import Path
from contextlib import closing

import requests
from flask import Blueprint, request, jsonify, abort

sys.path.append(str(Path(__file__).resolve().parents[2] / "database"))
from ryan_init_db import get_connection  

assistant_blueprint = Blueprint("assistant_blueprint", __name__, url_prefix="/api/inventory/assistant")

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:8b" 


def _build_low_stock_context():
    """Pulls current low-stock / out-of-stock products to ground the
    assistant's answer in real inventory data rather than letting it
    hallucinate product names or quantities."""
    with closing(get_connection()) as db:
        rows = db.execute(
            """
            SELECT p.name, p.stock_quantity, p.reorder_threshold, p.reorder_quantity,
                   s.name AS supplier_name
            FROM products p
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            WHERE p.stock_quantity <= p.reorder_threshold
            ORDER BY p.stock_quantity ASC
            """
        ).fetchall()

    if not rows:
        return "All products are currently above their reorder threshold."

    lines = []
    for row in rows:
        supplier = row["supplier_name"] or "no assigned supplier"
        lines.append(
            f"- {row['name']}: {row['stock_quantity']} in stock "
            f"(reorder threshold {row['reorder_threshold']}, "
            f"suggested reorder qty {row['reorder_quantity']}, supplier: {supplier})"
        )
    return "\n".join(lines)


def _call_ollama(prompt: str) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("response", "").strip()


@assistant_blueprint.post("")
def ask_assistant():
    """POST /api/inventory/assistant
    Body: { message: str }
    Returns: { reply: str }

    Grounds the LLM's answer in the current low-stock product list pulled
    straight from the products table.
    """
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()

    if not message:
        abort(400, description="A message is required")

    context = _build_low_stock_context()

    prompt = (
        "You are a restocking assistant for an inventory management system.\n"
        "Use ONLY the data below to answer. Be concise and specific about "
        "product names and quantities. If the question can't be answered "
        "from this data, say so.\n\n"
        f"Current low/out-of-stock products:\n{context}\n\n"
        f"Question: {message}\n"
    )

    try:
        reply = _call_ollama(prompt)
    except requests.exceptions.RequestException as exc:
        abort(502, description=f"Could not reach the AI assistant: {exc}")

    if not reply:
        reply = "The assistant didn't return a response. Please try again."

    return jsonify({"reply": reply})