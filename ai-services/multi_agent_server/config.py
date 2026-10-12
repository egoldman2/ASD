"""Environment-backed configuration for the shared Multi-Agent Server."""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
from urllib.parse import urlsplit


BASE_DIR = Path(__file__).resolve().parent

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5004
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_PLANNER_MODEL = "qwen2.5:0.5b"
DEFAULT_WORKER_MODEL = "qwen2.5:0.5b"
DEFAULT_REVIEWER_MODEL = "llama3.1:8b"
DEFAULT_TIMEOUT_SECONDS = 45.0
DEFAULT_MAX_REQUEST_BYTES = 65_536


class ConfigurationError(ValueError):
    """Raised when a Multi-Agent Server setting is invalid."""


def _required_text(value: str, setting_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ConfigurationError(f"{setting_name} must not be empty.")
    return cleaned


def _port(value: str) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(
            "MULTI_AGENT_PORT must be an integer."
        ) from exc
    if not 1 <= port <= 65_535:
        raise ConfigurationError(
            "MULTI_AGENT_PORT must be between 1 and 65535."
        )
    return port


def _positive_float(value: str, setting_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(
            f"{setting_name} must be a number."
        ) from exc
    if not math.isfinite(number) or number <= 0:
        raise ConfigurationError(
            f"{setting_name} must be greater than zero."
        )
    return number


def _positive_int(value: str, setting_name: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(
            f"{setting_name} must be an integer."
        ) from exc
    if number <= 0:
        raise ConfigurationError(
            f"{setting_name} must be greater than zero."
        )
    return number


def _http_origin(value: str, setting_name: str) -> str:
    cleaned = _required_text(value, setting_name).rstrip("/")
    try:
        parsed = urlsplit(cleaned)
        parsed_port = parsed.port
    except ValueError as exc:
        raise ConfigurationError(
            f"{setting_name} must contain a valid host and port."
        ) from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or (parsed_port is not None and not 1 <= parsed_port <= 65_535)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ConfigurationError(
            f"{setting_name} must be an HTTP(S) origin without credentials, "
            "a path, query, or fragment."
        )
    return cleaned


def _log_directory(value: str) -> Path:
    cleaned = _required_text(value, "MULTI_AGENT_LOG_DIR")
    path = Path(cleaned).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


@dataclass(frozen=True, slots=True)
class MultiAgentSettings:
    """Validated runtime settings shared by every server component."""

    host: str
    port: int
    ollama_url: str
    planner_model: str
    worker_model: str
    reviewer_model: str
    timeout_seconds: float
    max_request_bytes: int
    log_dir: Path

    @property
    def endpoint_url(self) -> str:
        """Return the local HTTP endpoint advertised to callers."""

        display_host = "127.0.0.1" if self.host == "0.0.0.0" else self.host
        return f"http://{display_host}:{self.port}"

    @property
    def ollama_generate_url(self) -> str:
        """Return the Ollama generate endpoint used by the model client."""

        return f"{self.ollama_url}/api/generate"

    @property
    def history_path(self) -> Path:
        """Return the configured workflow history path."""

        return self.log_dir / "workflow_history.jsonl"

    @property
    def audit_path(self) -> Path:
        """Return the configured coordination audit path."""

        return self.log_dir / "coordination_audit.jsonl"

    @classmethod
    def from_environment(cls) -> "MultiAgentSettings":
        """Build settings on demand so tests can safely override the environment."""

        return cls(
            host=_required_text(
                os.getenv("MULTI_AGENT_HOST", DEFAULT_HOST),
                "MULTI_AGENT_HOST",
            ),
            port=_port(os.getenv("MULTI_AGENT_PORT", str(DEFAULT_PORT))),
            ollama_url=_http_origin(
                os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL),
                "OLLAMA_URL",
            ),
            planner_model=_required_text(
                os.getenv("OLLAMA_PLANNER_MODEL", DEFAULT_PLANNER_MODEL),
                "OLLAMA_PLANNER_MODEL",
            ),
            worker_model=_required_text(
                os.getenv("OLLAMA_WORKER_MODEL", DEFAULT_WORKER_MODEL),
                "OLLAMA_WORKER_MODEL",
            ),
            reviewer_model=_required_text(
                os.getenv("OLLAMA_REVIEWER_MODEL", DEFAULT_REVIEWER_MODEL),
                "OLLAMA_REVIEWER_MODEL",
            ),
            timeout_seconds=_positive_float(
                os.getenv(
                    "OLLAMA_TIMEOUT_SECONDS",
                    str(DEFAULT_TIMEOUT_SECONDS),
                ),
                "OLLAMA_TIMEOUT_SECONDS",
            ),
            max_request_bytes=_positive_int(
                os.getenv(
                    "MULTI_AGENT_MAX_REQUEST_BYTES",
                    str(DEFAULT_MAX_REQUEST_BYTES),
                ),
                "MULTI_AGENT_MAX_REQUEST_BYTES",
            ),
            log_dir=_log_directory(
                os.getenv("MULTI_AGENT_LOG_DIR", str(BASE_DIR))
            ),
        )


def get_settings() -> MultiAgentSettings:
    """Load validated Multi-Agent Server settings from the environment."""

    return MultiAgentSettings.from_environment()
