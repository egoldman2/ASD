"""Tests for Ethan Ting's safe, read-only loyalty MCP tool."""

import ast
from pathlib import Path

import pytest

from mcp_server.tools.ethan_ting_customer import calculate_loyalty_tier


@pytest.mark.parametrize(
    ("points", "tier", "next_tier", "remaining"),
    [
        (0, "Bronze", "Silver", 500),
        (499, "Bronze", "Silver", 1),
        (500, "Silver", "Gold", 500),
        (720, "Silver", "Gold", 280),
        (999, "Silver", "Gold", 1),
        (1000, "Gold", None, 0),
        (1500, "Gold", None, 0),
    ],
)
def test_calculate_loyalty_tier(points, tier, next_tier, remaining):
    response = calculate_loyalty_tier(points)

    assert response["success"] is True
    assert response["tool"] == "ethan_ting_calculate_loyalty_tier"
    assert response["result"] == {
        "points_balance": points,
        "tier": tier,
        "next_tier": next_tier,
        "points_to_next_tier": remaining,
    }
    assert response["metadata"]["read_only"] is True


@pytest.mark.parametrize("points", [-1, True, False, 3.5, "500", None])
def test_calculate_loyalty_tier_rejects_invalid_points(points):
    response = calculate_loyalty_tier(points)

    assert response["success"] is False
    assert response["result"] is None
    assert response["error"]["code"] == "INVALID_ARGUMENT"
    assert response["error"]["details"]["field"] == "points_balance"


def test_tool_matches_customer_database_tier_rules():
    """Catch threshold drift between the MCP tool and database service."""

    database_app = (
        Path(__file__).resolve().parents[3]
        / "student-Ethan Ting"
        / "database"
        / "app.py"
    )
    source = ast.parse(database_app.read_text(encoding="utf-8"))
    loyalty_function = next(
        node
        for node in source.body
        if isinstance(node, ast.FunctionDef) and node.name == "loyalty_status"
    )
    namespace = {}
    isolated_function = ast.Module(body=[loyalty_function], type_ignores=[])
    exec(compile(isolated_function, str(database_app), "exec"), namespace)
    loyalty_status = namespace["loyalty_status"]
    for points in (0, 1, 499, 500, 501, 999, 1000, 1500):
        expected = loyalty_status(points)
        result = calculate_loyalty_tier(points)["result"]
        assert {
            "tier": result["tier"],
            "next_tier": result["next_tier"],
            "points_to_next_tier": result["points_to_next_tier"],
        } == expected
