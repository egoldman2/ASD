"""Read-only MCP tool logic for Howard's Order & Returns feature.

server.py registers these functions as MCP tools. Like the catalogue tools
they return the shared response envelope (success / tool / result / error) and
never modify data.

The Order & Returns HTTP API requires an authenticated session, so these
read-only tools read the feature's own SQLite database directly by path. This
is the feature's own data; no other feature's database is accessed.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from mcp_server.response import ToolErrorCode, error_response, success_response


GET_ORDER_STATUS = "howard_get_order_status"
GET_RETURN_DETAILS = "howard_get_return_details"


def _default_database_path() -> str:
    # tools -> mcp_server -> ai-services -> <repo root>
    repo_root = Path(__file__).resolve().parents[3]
    return str(repo_root / "student-Howard" / "database" / "orders.db")


ORDERS_DATABASE_PATH = os.getenv("ORDERS_DATABASE_PATH", _default_database_path())


class OrdersToolError(Exception):
    """Expected, user-safe failure raised while executing an orders tool."""

    def __init__(
        self,
        code: ToolErrorCode,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def _invalid(message: str, **details: Any) -> OrdersToolError:
    return OrdersToolError(
        ToolErrorCode.INVALID_ARGUMENT,
        message,
        details=details or None,
    )


def _positive_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _invalid(f"{field} must be a positive integer.", field=field)
    return value


def _error_payload(tool: str, error: OrdersToolError) -> dict[str, Any]:
    return error_response(tool, error.code, error.message, details=error.details)


def _unexpected_error(tool: str) -> dict[str, Any]:
    return error_response(
        tool,
        ToolErrorCode.INTERNAL_ERROR,
        "The orders tool could not complete the request.",
    )


def _connect() -> sqlite3.Connection:
    try:
        conn = sqlite3.connect(ORDERS_DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as exc:
        raise OrdersToolError(
            ToolErrorCode.UPSTREAM_UNAVAILABLE,
            "The orders database is currently unavailable.",
        ) from exc


def get_order_status(order_id: int) -> dict[str, Any]:
    """Return the status and summary of one order, with its item count."""

    try:
        validated_id = _positive_integer(order_id, "order_id")
        conn = _connect()
        try:
            order = conn.execute(
                "SELECT order_id, customer_id, order_date, status, total "
                "FROM orders WHERE order_id = ?",
                (validated_id,),
            ).fetchone()
            if order is None:
                raise OrdersToolError(
                    ToolErrorCode.RECORD_NOT_FOUND,
                    "The requested order was not found.",
                )
            item_count = conn.execute(
                "SELECT COUNT(*) FROM order_items WHERE order_id = ?",
                (validated_id,),
            ).fetchone()[0]
        finally:
            conn.close()

        return success_response(
            GET_ORDER_STATUS,
            {
                "order_id": order["order_id"],
                "customer_id": order["customer_id"],
                "order_date": str(order["order_date"])[:10],
                "status": order["status"],
                "total": float(order["total"]),
                "item_count": int(item_count),
            },
            metadata={"read_only": True},
        )
    except OrdersToolError as exc:
        return _error_payload(GET_ORDER_STATUS, exc)
    except Exception:
        return _unexpected_error(GET_ORDER_STATUS)


def get_return_details(return_id: int) -> dict[str, Any]:
    """Return one return request together with its linked order's status."""

    try:
        validated_id = _positive_integer(return_id, "return_id")
        conn = _connect()
        try:
            ret = conn.execute(
                "SELECT return_id, order_id, reason, status, created_at "
                "FROM returns WHERE return_id = ?",
                (validated_id,),
            ).fetchone()
            if ret is None:
                raise OrdersToolError(
                    ToolErrorCode.RECORD_NOT_FOUND,
                    "The requested return was not found.",
                )
            order = conn.execute(
                "SELECT status, total FROM orders WHERE order_id = ?",
                (ret["order_id"],),
            ).fetchone()
        finally:
            conn.close()

        return success_response(
            GET_RETURN_DETAILS,
            {
                "return_id": ret["return_id"],
                "order_id": ret["order_id"],
                "reason": ret["reason"],
                "status": ret["status"],
                "created_at": str(ret["created_at"])[:10],
                "order_status": order["status"] if order else "unknown",
                "order_total": float(order["total"]) if order else None,
            },
            metadata={"read_only": True},
        )
    except OrdersToolError as exc:
        return _error_payload(GET_RETURN_DETAILS, exc)
    except Exception:
        return _unexpected_error(GET_RETURN_DETAILS)
