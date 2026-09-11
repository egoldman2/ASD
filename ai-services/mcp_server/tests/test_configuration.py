"""Configuration tests for safe, repeatable local MCP startup."""

import pytest

from mcp_server.config import ConfigurationError, MCPSettings


def test_settings_read_and_normalise_environment(monkeypatch):
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_PORT", "9123")
    monkeypatch.setenv("MCP_PATH", "custom-mcp/")
    monkeypatch.setenv("PRODUCT_DATABASE_API_URL", "http://localhost:7001/api/")
    monkeypatch.setenv("MCP_REQUEST_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("MCP_LOG_LEVEL", "debug")

    settings = MCPSettings.from_environment()

    assert settings.host == "0.0.0.0"
    assert settings.port == 9123
    assert settings.path == "/custom-mcp"
    assert settings.product_database_api_url == "http://localhost:7001/api"
    assert settings.request_timeout_seconds == 2.5
    assert settings.log_level == "DEBUG"
    assert settings.endpoint_url == "http://127.0.0.1:9123/custom-mcp"


@pytest.mark.parametrize(
    ("setting", "value", "message"),
    [
        ("MCP_PORT", "0", "between 1 and 65535"),
        ("MCP_PORT", "not-a-port", "must be an integer"),
        ("MCP_REQUEST_TIMEOUT_SECONDS", "0", "greater than zero"),
        ("MCP_PATH", "   ", "must not be empty"),
        ("MCP_LOG_LEVEL", "verbose", "must be one of"),
    ],
)
def test_invalid_environment_settings_fail_early(
    monkeypatch,
    setting,
    value,
    message,
):
    monkeypatch.setenv(setting, value)

    with pytest.raises(ConfigurationError, match=message):
        MCPSettings.from_environment()
