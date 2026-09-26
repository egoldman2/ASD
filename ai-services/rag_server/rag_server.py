
"""MCP stdio entry point for the shared ASD marketplace RAG pipeline.

The MCP process deliberately uses stdio, matching the teaching example and
allowing an MCP-capable AI client to launch it directly.  Dockerised project
backends use the separate HTTP adapter in :mod:`rag_http_server`.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, cast

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rag_server.config import RAGSettings, get_settings
from rag_server.rag_pipeline import RAGPipeline


SERVER_NAME = "ASD Marketplace RAG"
DEFAULT_SCOPE = "chufeng_catalogue"
REFRESH_CORPUS = "refresh_corpus"
RETRIEVE_CONTEXT = "retrieve_context"
ANSWER_QUESTION = "answer_question"
AVAILABLE_TOOLS = (REFRESH_CORPUS, RETRIEVE_CONTEXT, ANSWER_QUESTION)

SERVER_INSTRUCTIONS = """
Shared local retrieval-augmented generation service for the ASD marketplace.

Call refresh_corpus after the underlying source data changes. Use
retrieve_context when cited evidence is required without generation, and use
answer_question for an Ollama-generated answer grounded only in retrieved
evidence. Every operation returns a stable structured envelope. Treat an
insufficient_context response as an instruction not to invent an answer.
""".strip()

READ_ONLY_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

REFRESH_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

PipelineFactory = Callable[[], RAGPipeline]


def _execute(
    pipeline_factory: PipelineFactory,
    method_name: str,
    *args: Any,
) -> dict[str, Any]:
    """Run one operation and always release its local Chroma client."""

    pipeline = pipeline_factory()
    try:
        method = getattr(pipeline, method_name)
        return cast(dict[str, Any], method(*args))
    finally:
        close = getattr(pipeline, "close", None)
        if callable(close):
            close()


def create_server(
    settings: RAGSettings | None = None,
    pipeline_factory: PipelineFactory | None = None,
) -> FastMCP:
    """Create an isolated MCP server, with dependency injection for tests."""

    resolved = settings or get_settings()
    factory = pipeline_factory or (lambda: RAGPipeline(settings=resolved))
    server = FastMCP(
        name=SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        log_level=cast(Any, resolved.log_level),
    )

    def refresh_corpus(
        scope: str = DEFAULT_SCOPE,
    ) -> dict[str, Any]:
        """Refresh one registered knowledge scope from its read-only source."""

        return _execute(factory, REFRESH_CORPUS, scope)

    def retrieve_context(
        query: str,
        top_k: int = resolved.default_top_k,
        scope: str = DEFAULT_SCOPE,
    ) -> dict[str, Any]:
        """Retrieve the most relevant cited evidence for a question."""

        return _execute(factory, RETRIEVE_CONTEXT, scope, query, top_k)

    def answer_question(
        question: str,
        top_k: int = resolved.default_top_k,
        scope: str = DEFAULT_SCOPE,
    ) -> dict[str, Any]:
        """Answer using Ollama and only evidence retrieved from one scope."""

        return _execute(factory, ANSWER_QUESTION, scope, question, top_k)

    server.tool(
        name=REFRESH_CORPUS,
        title="Refresh RAG Corpus",
        description=(
            "Rebuild one ChromaDB knowledge scope from its authoritative "
            "read-only source. This changes only the local vector index."
        ),
        annotations=REFRESH_ANNOTATIONS,
        structured_output=True,
    )(refresh_corpus)
    server.tool(
        name=RETRIEVE_CONTEXT,
        title="Retrieve Grounded Context",
        description=(
            "Retrieve relevant evidence with citations, confidence, and "
            "distance metadata from one indexed knowledge scope."
        ),
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )(retrieve_context)
    server.tool(
        name=ANSWER_QUESTION,
        title="Answer a Grounded Question",
        description=(
            "Generate a cited answer with local Ollama using only retrieved "
            "evidence; reports insufficient context instead of guessing."
        ),
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )(answer_question)
    return server


mcp = create_server()


def main() -> None:
    """Run over stdio for direct use by MCP-capable AI clients."""

    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger(__name__).info(
        "Starting %s over stdio with tools: %s",
        SERVER_NAME,
        ", ".join(AVAILABLE_TOOLS),
    )
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
