"""Shared corpus refresh and deterministic vector indexing for local RAG."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import logging
import math
import re
from typing import Any

import chromadb

from rag_server.config import RAGSettings, get_settings
from rag_server.response import RAGErrorCode, error_response, success_response
from rag_server.sources import (
    ChufengCatalogueSource,
    KnowledgeDocument,
    KnowledgeSource,
    SourceDataError,
    SourceUnavailableError,
)


LOGGER = logging.getLogger(__name__)
TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*", re.IGNORECASE)
HASH_BYTES = hashlib.sha256().digest_size


class EmbeddingError(ValueError):
    """Raised when text cannot produce a safe deterministic embedding."""


def tokenise(text: str) -> list[str]:
    """Return stable English word-like tokens for the local hash embedder."""

    if not isinstance(text, str):
        raise EmbeddingError("Embedding input must be text.")
    return TOKEN_PATTERN.findall(text.casefold())


def embed_text(text: str, dimensions: int = 256) -> list[float]:
    """Create a deterministic, fully populated hash embedding for one text."""

    if isinstance(dimensions, bool) or not isinstance(dimensions, int):
        raise EmbeddingError("Embedding dimensions must be an integer.")
    if dimensions < 1:
        raise EmbeddingError("Embedding dimensions must be greater than zero.")

    tokens = tokenise(text)
    if not tokens:
        raise EmbeddingError("Embedding input must contain at least one token.")

    values = [0.0] * dimensions
    block_count = math.ceil(dimensions / HASH_BYTES)

    for token in tokens:
        for block_index in range(block_count):
            digest = hashlib.sha256(
                f"{block_index}:{token}".encode("utf-8")
            ).digest()
            block_start = block_index * HASH_BYTES
            for offset, byte in enumerate(digest):
                vector_index = block_start + offset
                if vector_index >= dimensions:
                    break
                values[vector_index] += (byte / 255.0) - 0.5

    norm = math.sqrt(sum(value * value for value in values))
    if not math.isfinite(norm) or norm <= 0:
        raise EmbeddingError("Embedding input produced an invalid vector.")
    return [value / norm for value in values]


def embed_texts(texts: Sequence[str], dimensions: int = 256) -> list[list[float]]:
    """Create deterministic embeddings while preserving input order."""

    if isinstance(texts, (str, bytes)) or not isinstance(texts, Sequence):
        raise EmbeddingError("Embedding inputs must be a sequence of text values.")
    return [embed_text(text, dimensions) for text in texts]


def _default_sources(settings: RAGSettings) -> dict[str, KnowledgeSource]:
    sources: list[KnowledgeSource] = [
        ChufengCatalogueSource(settings_loader=lambda: settings)
    ]
    return {source.scope: source for source in sources}


def _validated_sources(
    sources: Mapping[str, KnowledgeSource],
) -> dict[str, KnowledgeSource]:
    if not isinstance(sources, Mapping):
        raise ValueError("sources must be a mapping.")

    validated: dict[str, KnowledgeSource] = {}
    for scope, source in sources.items():
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("Every source scope must be a non-empty string.")
        cleaned_scope = scope.strip()
        if source.scope != cleaned_scope:
            raise ValueError(
                f"Source registry key {cleaned_scope!r} does not match "
                f"source scope {source.scope!r}."
            )
        if cleaned_scope in validated:
            raise ValueError(f"Duplicate source scope: {cleaned_scope}.")
        validated[cleaned_scope] = source
    return validated


def _validated_documents(
    source: KnowledgeSource,
    documents: Sequence[KnowledgeDocument],
) -> list[KnowledgeDocument]:
    if isinstance(documents, (str, bytes)) or not isinstance(documents, Sequence):
        raise SourceDataError(
            "The knowledge source returned an invalid document collection."
        )

    validated: list[KnowledgeDocument] = []
    document_ids: set[str] = set()
    for document in documents:
        if not isinstance(document, KnowledgeDocument):
            raise SourceDataError(
                "The knowledge source returned an invalid document."
            )
        if document.scope != source.scope:
            raise SourceDataError(
                "The knowledge source returned a document with the wrong scope."
            )
        if document.document_id in document_ids:
            raise SourceDataError(
                "The knowledge source returned duplicate document IDs."
            )
        document_ids.add(document.document_id)
        validated.append(document)
    return validated


def _document_metadata(document: KnowledgeDocument) -> dict[str, Any]:
    # Reserved keys are applied last so an adapter cannot override boundaries.
    return {
        **document.metadata,
        "scope": document.scope,
        "source_id": document.source_id,
        "citation_label": document.citation_label,
    }


class RAGPipeline:
    """Coordinate shared knowledge sources and a persistent Chroma collection."""

    def __init__(
        self,
        *,
        settings: RAGSettings | None = None,
        sources: Mapping[str, KnowledgeSource] | None = None,
        chroma_client: Any | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        selected_sources = (
            sources if sources is not None else _default_sources(self.settings)
        )
        self.sources = _validated_sources(selected_sources)
        self._chroma_client = chroma_client
        self._owns_chroma_client = chroma_client is None
        self._collection: Any | None = None

    @property
    def available_scopes(self) -> tuple[str, ...]:
        return tuple(sorted(self.sources))

    def _get_client(self) -> Any:
        if self._chroma_client is None:
            self.settings.chroma_path.mkdir(parents=True, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(
                path=str(self.settings.chroma_path)
            )
        return self._chroma_client

    def _get_collection(self) -> Any:
        if self._collection is None:
            self._collection = self._get_client().get_or_create_collection(
                name=self.settings.collection_name,
                metadata={
                    "hnsw:space": "cosine",
                    "embedding_dimensions": self.settings.embedding_dimensions,
                    "managed_by": "asd_release1_rag",
                },
                embedding_function=None,
            )
        return self._collection

    def close(self) -> None:
        """Release a Chroma client created by this pipeline instance."""

        client = self._chroma_client
        self._collection = None
        self._chroma_client = None
        if self._owns_chroma_client and client is not None:
            close = getattr(client, "close", None)
            if callable(close):
                close()

    def __enter__(self) -> "RAGPipeline":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def refresh_corpus(self, scope: str) -> dict[str, Any]:
        """Replace one source scope only after its new snapshot is ready."""

        operation = "refresh_corpus"
        if not self.settings.enabled:
            return error_response(
                operation,
                RAGErrorCode.RAG_DISABLED,
                "The local RAG service is disabled.",
            )
        if not isinstance(scope, str) or not scope.strip():
            return error_response(
                operation,
                RAGErrorCode.INVALID_ARGUMENT,
                "scope must be a non-empty string.",
            )

        cleaned_scope = scope.strip()
        source = self.sources.get(cleaned_scope)
        if source is None:
            return error_response(
                operation,
                RAGErrorCode.SCOPE_NOT_FOUND,
                "The requested RAG knowledge scope is not registered.",
                details={"available_scopes": list(self.available_scopes)},
            )

        try:
            documents = _validated_documents(source, source.load_documents())
            embeddings = embed_texts(
                [document.text for document in documents],
                self.settings.embedding_dimensions,
            )
        except SourceUnavailableError as exc:
            return error_response(
                operation,
                RAGErrorCode.SOURCE_UNAVAILABLE,
                str(exc),
            )
        except (SourceDataError, EmbeddingError) as exc:
            return error_response(
                operation,
                RAGErrorCode.SOURCE_DATA_INVALID,
                str(exc),
            )
        except Exception:
            LOGGER.exception("Unexpected failure while preparing scope %s", cleaned_scope)
            return error_response(
                operation,
                RAGErrorCode.INTERNAL_ERROR,
                "The RAG source could not be prepared.",
            )

        try:
            collection = self._get_collection()
            existing = collection.get(
                where={"scope": cleaned_scope},
                include=["metadatas"],
            )
            existing_ids = set(existing.get("ids") or [])
            new_ids = {document.document_id for document in documents}

            # Upsert first. Stale records are removed only after the complete new
            # snapshot has been accepted, preserving the old index on failure.
            if documents:
                collection.upsert(
                    ids=[document.document_id for document in documents],
                    embeddings=embeddings,
                    documents=[document.text for document in documents],
                    metadatas=[
                        _document_metadata(document) for document in documents
                    ],
                )

            stale_ids = sorted(existing_ids - new_ids)
            if stale_ids:
                collection.delete(ids=stale_ids)

            refreshed_at = datetime.now(timezone.utc).isoformat()
            return success_response(
                operation,
                {
                    "scope": cleaned_scope,
                    "source": source.source_name,
                    "document_count": len(documents),
                    "added_count": len(new_ids - existing_ids),
                    "updated_count": len(new_ids & existing_ids),
                    "removed_count": len(stale_ids),
                    "collection": self.settings.collection_name,
                    "collection_count": collection.count(),
                    "refreshed_at": refreshed_at,
                },
                metadata={
                    "read_only_source": True,
                    "embedding": "deterministic_sha256",
                    "embedding_dimensions": self.settings.embedding_dimensions,
                },
            )
        except Exception:
            LOGGER.exception("Unable to refresh Chroma scope %s", cleaned_scope)
            return error_response(
                operation,
                RAGErrorCode.INDEX_UNAVAILABLE,
                "The RAG vector index could not be refreshed.",
            )


def refresh_corpus(scope: str) -> dict[str, Any]:
    """Refresh one scope using the default local pipeline configuration."""

    with RAGPipeline() as pipeline:
        return pipeline.refresh_corpus(scope)
