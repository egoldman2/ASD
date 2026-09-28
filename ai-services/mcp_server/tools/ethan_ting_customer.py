"""Read-only, customer-safe MCP tools for Ethan Ting's loyalty feature.

This first tool calculates a tier from a supplied points balance. It does not
look up customers or expose account records from the unauthenticated local MCP
service. The thresholds match the customer database service's loyalty rules.
"""

from __future__ import annotations

from typing import Any

from mcp_server.response import ToolErrorCode, error_response, success_response


CALCULATE_LOYALTY_TIER = "ethan_ting_calculate_loyalty_tier"


def calculate_loyalty_tier(points_balance: int) -> dict[str, Any]:
    """Return the tier and progress for a non-negative points balance."""

    if (
        isinstance(points_balance, bool)
        or not isinstance(points_balance, int)
        or points_balance < 0
    ):
        return error_response(
            CALCULATE_LOYALTY_TIER,
            ToolErrorCode.INVALID_ARGUMENT,
            "points_balance must be a non-negative integer.",
            details={"field": "points_balance"},
        )

    if points_balance >= 1000:
        tier = "Gold"
        next_tier = None
        points_to_next_tier = 0
    elif points_balance >= 500:
        tier = "Silver"
        next_tier = "Gold"
        points_to_next_tier = 1000 - points_balance
    else:
        tier = "Bronze"
        next_tier = "Silver"
        points_to_next_tier = 500 - points_balance

    return success_response(
        CALCULATE_LOYALTY_TIER,
        {
            "points_balance": points_balance,
            "tier": tier,
            "next_tier": next_tier,
            "points_to_next_tier": points_to_next_tier,
        },
        metadata={"read_only": True},
    )
