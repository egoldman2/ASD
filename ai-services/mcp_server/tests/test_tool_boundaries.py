"""Guardrails that keep Chufeng's MCP tools inside their agreed boundary."""

from pathlib import Path

from mcp_server.server import REGISTERED_CHUFENG_TOOLS


CATALOGUE_TOOL_SOURCE = (
    Path(__file__).resolve().parents[1] / "tools" / "chufeng_catalogue.py"
)


def test_chufeng_tool_names_are_namespaced_and_unique():
    assert len(REGISTERED_CHUFENG_TOOLS) == 4
    assert len(set(REGISTERED_CHUFENG_TOOLS)) == len(REGISTERED_CHUFENG_TOOLS)
    assert all(name.startswith("chufeng_") for name in REGISTERED_CHUFENG_TOOLS)


def test_catalogue_tools_do_not_open_the_database_or_issue_writes():
    source = CATALOGUE_TOOL_SOURCE.read_text(encoding="utf-8")

    assert "sqlite3" not in source
    assert "requests.post(" not in source
    assert "requests.put(" not in source
    assert "requests.patch(" not in source
    assert "requests.delete(" not in source
    assert "requests.get(" in source
