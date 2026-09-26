"""Common contracts for knowledge sources used by the shared RAG service."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping


MetadataValue = str | int | float | bool


class KnowledgeSourceError(RuntimeError):
    """Base class for expected, user-safe knowledge source failures."""


class SourceUnavailableError(KnowledgeSourceError):
    """Raised when a source cannot currently be reached."""


class SourceDataError(KnowledgeSourceError):
    """Raised when a source returns data that is unsafe or malformed."""


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _validated_metadata(
    metadata: Mapping[str, MetadataValue],
) -> dict[str, MetadataValue]:
    if not isinstance(metadata, Mapping):
        raise ValueError("metadata must be a mapping.")

    validated: dict[str, MetadataValue] = {}
    for key, value in metadata.items():
        cleaned_key = _required_text(key, "metadata key")
        if isinstance(value, bool):
            validated[cleaned_key] = value
        elif isinstance(value, (str, int, float)):
            validated[cleaned_key] = value
        else:
            raise ValueError(
                "metadata values must be strings, integers, floats, or booleans."
            )
    return validated


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    """A validated, source-neutral document ready for later RAG indexing."""

    document_id: str
    scope: str
    source_id: str
    citation_label: str
    text: str
    metadata: Mapping[str, MetadataValue]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "document_id",
            _required_text(self.document_id, "document_id"),
        )
        object.__setattr__(self, "scope", _required_text(self.scope, "scope"))
        object.__setattr__(
            self,
            "source_id",
            _required_text(self.source_id, "source_id"),
        )
        object.__setattr__(
            self,
            "citation_label",
            _required_text(self.citation_label, "citation_label"),
        )
        object.__setattr__(self, "text", _required_text(self.text, "text"))
        object.__setattr__(self, "metadata", _validated_metadata(self.metadata))

    def to_record(self) -> dict[str, Any]:
        """Return a serialisable representation for corpus and audit records."""

        return {
            "document_id": self.document_id,
            "scope": self.scope,
            "source_id": self.source_id,
            "citation_label": self.citation_label,
            "text": self.text,
            "metadata": dict(self.metadata),
        }


class KnowledgeSource(ABC):
    """Interface implemented by each team member's knowledge adapter."""

    @property
    @abstractmethod
    def scope(self) -> str:
        """Return the unique namespace used to isolate this source's documents."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return a human-readable source name used in evidence and logs."""

    @abstractmethod
    def load_documents(self) -> list[KnowledgeDocument]:
        """Load and validate a complete source snapshot without mutating it."""
