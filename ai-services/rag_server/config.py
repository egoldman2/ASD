"""Environment-backed configuration for the shared local RAG service."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlsplit


BASE_DIR = Path(__file__).resolve().parent

DEFAULT_RAG_ENABLED = True
# Listen on every local interface so Dockerised student backends can reach the
# host-side service through host.docker.internal.  This is still a local
# development service and must not be exposed on a public network.
DEFAULT_RAG_HOST = "0.0.0.0"
DEFAULT_RAG_PORT = 5003
DEFAULT_PRODUCT_DATABASE_API_URL = (
    "http://127.0.0.1:6001/api/database/products"
)
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:0.5b"
DEFAULT_CHROMA_PATH = BASE_DIR / "chroma"
DEFAULT_COLLECTION_NAME = "asd_release1_shared_context"
DEFAULT_AUDIT_PATH = BASE_DIR / "rag-audit.jsonl"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 45.0
DEFAULT_TOP_K = 5
DEFAULT_MAX_TOP_K = 20
DEFAULT_MIN_RELEVANCE_SCORE = 0.25
DEFAULT_EMBEDDING_DIMENSIONS = 256
DEFAULT_LOG_LEVEL = "INFO"

VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


class ConfigurationError(ValueError):
    """Raised when a RAG environment setting is invalid."""


def _required_text(value: str, setting_name: str) -> str:
    if not isinstance(value, str):
        raise ConfigurationError(f"{setting_name} must be text.")

    cleaned = value.strip()
    if not cleaned:
        raise ConfigurationError(f"{setting_name} must not be empty.")
    return cleaned


def _boolean_from_environment(value: str, setting_name: str) -> bool:
    cleaned = _required_text(value, setting_name).lower()
    if cleaned in TRUE_VALUES:
        return True
    if cleaned in FALSE_VALUES:
        return False
    raise ConfigurationError(
        f"{setting_name} must be one of: true, false, 1, 0, yes, no, on, off."
    )


def _integer_from_environment(
    value: str,
    setting_name: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{setting_name} must be an integer.") from exc

    if not minimum <= parsed <= maximum:
        raise ConfigurationError(
            f"{setting_name} must be between {minimum} and {maximum}."
        )
    return parsed


def _positive_float_from_environment(value: str, setting_name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{setting_name} must be a number.") from exc

    if parsed <= 0:
        raise ConfigurationError(f"{setting_name} must be greater than zero.")
    return parsed


def _score_from_environment(value: str, setting_name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{setting_name} must be a number.") from exc

    if not 0.0 <= parsed <= 1.0:
        raise ConfigurationError(f"{setting_name} must be between 0 and 1.")
    return parsed


def _directory_from_environment(value: str, setting_name: str) -> Path:
    path_text = _required_text(value, setting_name)
    return Path(path_text).expanduser().resolve()


def _url_from_environment(value: str, setting_name: str) -> str:
    url = _required_text(value, setting_name).rstrip("/")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ConfigurationError(
            f"{setting_name} must be a valid HTTP or HTTPS URL."
        )
    return url


def _file_from_environment(value: str, setting_name: str) -> Path:
    path = _directory_from_environment(value, setting_name)
    if path.name in {"", ".", ".."}:
        raise ConfigurationError(f"{setting_name} must identify a file path.")
    if path.exists() and path.is_dir():
        raise ConfigurationError(f"{setting_name} must identify a file, not a directory.")
    return path


def _log_level_from_environment(value: str) -> str:
    log_level = _required_text(value, "RAG_LOG_LEVEL").upper()
    if log_level not in VALID_LOG_LEVELS:
        allowed = ", ".join(sorted(VALID_LOG_LEVELS))
        raise ConfigurationError(f"RAG_LOG_LEVEL must be one of: {allowed}.")
    return log_level


@dataclass(frozen=True, slots=True)
class RAGSettings:
    """Validated configuration shared by every RAG service entry point."""

    enabled: bool
    host: str
    port: int
    product_database_api_url: str
    ollama_url: str
    ollama_model: str
    chroma_path: Path
    collection_name: str
    audit_path: Path
    request_timeout_seconds: float
    default_top_k: int
    max_top_k: int
    min_relevance_score: float
    embedding_dimensions: int
    log_level: str

    @property
    def endpoint_url(self) -> str:
        """Return the host-side URL used to reach the local RAG HTTP server."""

        display_host = "127.0.0.1" if self.host == "0.0.0.0" else self.host
        return f"http://{display_host}:{self.port}"

    @classmethod
    def from_environment(cls) -> "RAGSettings":
        """Build settings from environment variables and fail fast if invalid."""

        enabled = _boolean_from_environment(
            os.getenv("RAG_ENABLED", str(DEFAULT_RAG_ENABLED)),
            "RAG_ENABLED",
        )
        host = _required_text(
            os.getenv("RAG_HOST", DEFAULT_RAG_HOST),
            "RAG_HOST",
        )
        port = _integer_from_environment(
            os.getenv("RAG_PORT", str(DEFAULT_RAG_PORT)),
            "RAG_PORT",
            minimum=1,
            maximum=65535,
        )
        product_database_api_url = _url_from_environment(
            os.getenv(
                "PRODUCT_DATABASE_API_URL",
                DEFAULT_PRODUCT_DATABASE_API_URL,
            ),
            "PRODUCT_DATABASE_API_URL",
        )
        ollama_url = _url_from_environment(
            os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL),
            "OLLAMA_URL",
        )
        ollama_model = _required_text(
            os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
            "OLLAMA_MODEL",
        )
        chroma_path = _directory_from_environment(
            os.getenv("RAG_CHROMA_PATH", str(DEFAULT_CHROMA_PATH)),
            "RAG_CHROMA_PATH",
        )
        collection_name = _required_text(
            os.getenv("RAG_COLLECTION_NAME", DEFAULT_COLLECTION_NAME),
            "RAG_COLLECTION_NAME",
        )
        audit_path = _file_from_environment(
            os.getenv("RAG_AUDIT_PATH", str(DEFAULT_AUDIT_PATH)),
            "RAG_AUDIT_PATH",
        )
        request_timeout_seconds = _positive_float_from_environment(
            os.getenv(
                "RAG_REQUEST_TIMEOUT_SECONDS",
                str(DEFAULT_REQUEST_TIMEOUT_SECONDS),
            ),
            "RAG_REQUEST_TIMEOUT_SECONDS",
        )
        default_top_k = _integer_from_environment(
            os.getenv("RAG_DEFAULT_TOP_K", str(DEFAULT_TOP_K)),
            "RAG_DEFAULT_TOP_K",
            minimum=1,
            maximum=100,
        )
        max_top_k = _integer_from_environment(
            os.getenv("RAG_MAX_TOP_K", str(DEFAULT_MAX_TOP_K)),
            "RAG_MAX_TOP_K",
            minimum=1,
            maximum=100,
        )
        if default_top_k > max_top_k:
            raise ConfigurationError(
                "RAG_DEFAULT_TOP_K must not be greater than RAG_MAX_TOP_K."
            )
        min_relevance_score = _score_from_environment(
            os.getenv(
                "RAG_MIN_RELEVANCE_SCORE",
                str(DEFAULT_MIN_RELEVANCE_SCORE),
            ),
            "RAG_MIN_RELEVANCE_SCORE",
        )
        embedding_dimensions = _integer_from_environment(
            os.getenv(
                "RAG_EMBEDDING_DIMENSIONS",
                str(DEFAULT_EMBEDDING_DIMENSIONS),
            ),
            "RAG_EMBEDDING_DIMENSIONS",
            minimum=32,
            maximum=4096,
        )
        log_level = _log_level_from_environment(
            os.getenv("RAG_LOG_LEVEL", DEFAULT_LOG_LEVEL)
        )

        return cls(
            enabled=enabled,
            host=host,
            port=port,
            product_database_api_url=product_database_api_url,
            ollama_url=ollama_url,
            ollama_model=ollama_model,
            chroma_path=chroma_path,
            collection_name=collection_name,
            audit_path=audit_path,
            request_timeout_seconds=request_timeout_seconds,
            default_top_k=default_top_k,
            max_top_k=max_top_k,
            min_relevance_score=min_relevance_score,
            embedding_dimensions=embedding_dimensions,
            log_level=log_level,
        )


def get_settings() -> RAGSettings:
    """Load settings on demand so tests can safely override the environment."""

    return RAGSettings.from_environment()
