"""Knowledge source adapters registered with the shared RAG pipeline."""

from .base import (
    KnowledgeDocument,
    KnowledgeSource,
    KnowledgeSourceError,
    SourceDataError,
    SourceUnavailableError,
)
from .chufeng_catalogue import ChufengCatalogueSource
from .ryan_inventory import RyanInventorySource
from .markdown_knowledge import MarkdownKnowledgeSource

__all__ = [
    "ChufengCatalogueSource",
    "MarkdownKnowledgeSource",
    "KnowledgeDocument",
    "KnowledgeSource",
    "KnowledgeSourceError",
    "RyanInventorySource",
    "SourceDataError",
    "SourceUnavailableError",
]