"""Guardrails that keep Chufeng's MCP tools inside their agreed boundary."""

from pathlib import Path

from mcp_server.server import REGISTERED_CHUFENG_TOOLS


CATALOGUE_TOOL_SOURCE = (
    Path(__file__).resolve().parents[1] / "tools" / "chufeng_catalogue.py"
)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


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


def _compose_service(source: str, service_name: str) -> str:
    marker = f"  {service_name}:"
    lines = source.splitlines()
    start = lines.index(marker)
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.startswith("  ") and not line.startswith("    "):
            end = index
            break
    return "\n".join(lines[start:end])


def test_compose_bridges_to_host_mcp_without_containerising_it():
    source = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    service_names = {
        line.strip()[:-1]
        for line in source.splitlines()
        if line.startswith("  ")
        and not line.startswith("    ")
        and line.strip().endswith(":")
    }
    backend = _compose_service(source, "shared-backend")
    product_database = _compose_service(source, "product-database")

    assert "mcp-server" not in service_names
    assert "MCP_SERVER_URL:" in backend
    assert "http://host.docker.internal:8765/mcp" in backend
    assert "host.docker.internal:host-gateway" in backend
    assert '"${PRODUCT_DATABASE_HOST_PORT:-6001}:6001"' in product_database


def test_chufeng_ci_validates_mcp_without_starting_local_ai_services():
    workflow = (
        PROJECT_ROOT / ".github" / "workflows" / "Chufeng.yml"
    ).read_text(encoding="utf-8")

    assert 'MCP_ENABLED: "false"' in workflow
    assert 'RAG_ENABLED: "false"' in workflow
    assert 'AI_MODE_ENABLED: "false"' in workflow
    assert "student-Chufeng/tests" in workflow
    assert "ai-services/mcp_server/tests" in workflow
    assert "docker compose config --quiet" in workflow
    assert "--target database" in workflow
    assert "docker compose up" not in workflow
    assert "ollama pull" not in workflow
    assert "ollama-init" not in workflow
