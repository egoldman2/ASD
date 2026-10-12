"""Configuration tests for safe, repeatable Multi-Agent Server startup."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from multi_agent_server.config import (
    BASE_DIR,
    ConfigurationError,
    MultiAgentSettings,
)


ENVIRONMENT_SETTINGS = (
    "MULTI_AGENT_HOST",
    "MULTI_AGENT_PORT",
    "OLLAMA_URL",
    "OLLAMA_PLANNER_MODEL",
    "OLLAMA_WORKER_MODEL",
    "OLLAMA_REVIEWER_MODEL",
    "OLLAMA_TIMEOUT_SECONDS",
    "MULTI_AGENT_MAX_REQUEST_BYTES",
    "MULTI_AGENT_LOG_DIR",
)


def clear_settings(monkeypatch):
    for setting in ENVIRONMENT_SETTINGS:
        monkeypatch.delenv(setting, raising=False)


def test_default_settings_are_local_and_match_the_lab_models(monkeypatch):
    clear_settings(monkeypatch)

    settings = MultiAgentSettings.from_environment()

    assert settings.host == "127.0.0.1"
    assert settings.port == 5004
    assert settings.endpoint_url == "http://127.0.0.1:5004"
    assert settings.ollama_url == "http://localhost:11434"
    assert settings.ollama_generate_url == (
        "http://localhost:11434/api/generate"
    )
    assert settings.planner_model == "qwen2.5:0.5b"
    assert settings.worker_model == "qwen2.5:0.5b"
    assert settings.reviewer_model == "llama3.1:8b"
    assert settings.timeout_seconds == 45.0
    assert settings.max_request_bytes == 65_536
    assert settings.log_dir == BASE_DIR
    assert settings.history_path == BASE_DIR / "workflow_history.jsonl"
    assert settings.audit_path == BASE_DIR / "coordination_audit.jsonl"


def test_settings_read_and_normalise_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("MULTI_AGENT_HOST", "0.0.0.0")
    monkeypatch.setenv("MULTI_AGENT_PORT", "9504")
    monkeypatch.setenv("OLLAMA_URL", "https://ollama.example.test/")
    monkeypatch.setenv("OLLAMA_PLANNER_MODEL", "planner:test")
    monkeypatch.setenv("OLLAMA_WORKER_MODEL", "worker:test")
    monkeypatch.setenv("OLLAMA_REVIEWER_MODEL", "reviewer:test")
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("MULTI_AGENT_MAX_REQUEST_BYTES", "2048")
    monkeypatch.setenv("MULTI_AGENT_LOG_DIR", str(tmp_path))

    settings = MultiAgentSettings.from_environment()

    assert settings.host == "0.0.0.0"
    assert settings.port == 9504
    assert settings.endpoint_url == "http://127.0.0.1:9504"
    assert settings.ollama_url == "https://ollama.example.test"
    assert settings.planner_model == "planner:test"
    assert settings.worker_model == "worker:test"
    assert settings.reviewer_model == "reviewer:test"
    assert settings.timeout_seconds == 2.5
    assert settings.max_request_bytes == 2048
    assert settings.log_dir == tmp_path.resolve()
    assert settings.history_path == tmp_path / "workflow_history.jsonl"
    assert settings.audit_path == tmp_path / "coordination_audit.jsonl"


def test_relative_log_directory_is_resolved_from_the_service_directory(
    monkeypatch,
):
    clear_settings(monkeypatch)
    monkeypatch.setenv("MULTI_AGENT_LOG_DIR", "runtime-logs")

    settings = MultiAgentSettings.from_environment()

    assert settings.log_dir == (BASE_DIR / "runtime-logs").resolve()


def test_settings_are_immutable(monkeypatch):
    clear_settings(monkeypatch)
    settings = MultiAgentSettings.from_environment()

    with pytest.raises(FrozenInstanceError):
        settings.port = 6000


@pytest.mark.parametrize(
    ("setting", "value", "message"),
    [
        ("MULTI_AGENT_HOST", "   ", "must not be empty"),
        ("MULTI_AGENT_PORT", "0", "between 1 and 65535"),
        ("MULTI_AGENT_PORT", "65536", "between 1 and 65535"),
        ("MULTI_AGENT_PORT", "not-a-port", "must be an integer"),
        ("OLLAMA_URL", "localhost:11434", "must be an HTTP"),
        ("OLLAMA_URL", "ftp://localhost", "must be an HTTP"),
        ("OLLAMA_URL", "http://user:pass@localhost", "must be an HTTP"),
        ("OLLAMA_URL", "http://localhost/api", "must be an HTTP"),
        ("OLLAMA_URL", "http://localhost?x=1", "must be an HTTP"),
        ("OLLAMA_URL", "http://localhost#models", "must be an HTTP"),
        ("OLLAMA_URL", "http://localhost:0", "must be an HTTP"),
        ("OLLAMA_URL", "http://localhost:invalid", "valid host and port"),
        ("OLLAMA_PLANNER_MODEL", "   ", "must not be empty"),
        ("OLLAMA_WORKER_MODEL", "   ", "must not be empty"),
        ("OLLAMA_REVIEWER_MODEL", "   ", "must not be empty"),
        ("OLLAMA_TIMEOUT_SECONDS", "0", "greater than zero"),
        ("OLLAMA_TIMEOUT_SECONDS", "slow", "must be a number"),
        ("OLLAMA_TIMEOUT_SECONDS", "nan", "greater than zero"),
        ("OLLAMA_TIMEOUT_SECONDS", "inf", "greater than zero"),
        ("MULTI_AGENT_MAX_REQUEST_BYTES", "0", "greater than zero"),
        ("MULTI_AGENT_MAX_REQUEST_BYTES", "large", "must be an integer"),
        ("MULTI_AGENT_LOG_DIR", "   ", "must not be empty"),
    ],
)
def test_invalid_environment_settings_fail_early(
    monkeypatch,
    setting,
    value,
    message,
):
    clear_settings(monkeypatch)
    monkeypatch.setenv(setting, value)

    with pytest.raises(ConfigurationError, match=message):
        MultiAgentSettings.from_environment()


def test_log_paths_are_path_objects(monkeypatch, tmp_path):
    clear_settings(monkeypatch)
    monkeypatch.setenv("MULTI_AGENT_LOG_DIR", str(tmp_path))

    settings = MultiAgentSettings.from_environment()

    assert isinstance(settings.log_dir, Path)
    assert isinstance(settings.history_path, Path)
    assert isinstance(settings.audit_path, Path)
