"""Bounded, public loyalty-history fields shared by the API and MCP adapter."""

from datetime import datetime


def validate_history_result(payload, customer_id, limit):
    """Validate identity and rows, returning only the approved display fields."""
    if (
        not isinstance(payload, dict)
        or type(payload.get("customer_id")) is not int
        or payload["customer_id"] != customer_id
        or type(payload.get("limit")) is not int
        or payload["limit"] != limit
        or type(payload.get("count")) is not int
        or not isinstance(payload.get("transactions"), list)
        or payload["count"] != len(payload["transactions"])
        or not 0 <= payload["count"] <= limit
    ):
        raise ValueError("Invalid loyalty history response.")
    rows = []
    identifiers = set()
    for row in payload["transactions"]:
        if (
            not isinstance(row, dict)
            or type(row.get("id")) is not int
            or row["id"] <= 0
            or row["id"] in identifiers
            or type(row.get("user_id", customer_id)) is not int
            or row.get("user_id", customer_id) != customer_id
            or type(row.get("points_change")) is not int
            or not isinstance(row.get("reason"), str)
            or not 1 <= len(row["reason"]) <= 200
            or not isinstance(row.get("created_at"), str)
            or not 1 <= len(row["created_at"]) <= 40
        ):
            raise ValueError("Invalid loyalty transaction.")
        datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        identifiers.add(row["id"])
        rows.append({key: row[key] for key in ("id", "points_change", "reason", "created_at")})
    return {"customer_id": customer_id, "limit": limit, "count": len(rows), "transactions": rows}
