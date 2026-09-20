"""Main MCP and HTTP entry-point tests for the shared RAG service."""

import asyncio
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from rag_server.rag_http_server import MAX_REQUEST_BODY_BYTES, create_app
from rag_server.rag_server import AVAILABLE_TOOLS, SERVER_NAME, create_server
from rag_server.response import RAGErrorCode, error_response, success_response


AI_SERVICES_ROOT = Path(__file__).resolve().parents[2]


class FakePipeline:
    available_scopes = ("chufeng_catalogue",)

    def __init__(self, response=None, failure=None):
        self.response = response
        self.failure = failure
        self.calls = []
        self.closed = False

    def close(self):
        self.closed = True

    def _call(self, operation, *args):
        self.calls.append((operation, args))
        if self.failure:
            raise self.failure
        return self.response or success_response(operation, {"arguments": list(args)})

    def refresh_corpus(self, scope):
        return self._call("refresh_corpus", scope)

    def retrieve_context(self, scope, query, top_k):
        return self._call("retrieve_context", scope, query, top_k)

    def answer_question(self, scope, question, top_k):
        return self._call("answer_question", scope, question, top_k)


def factory_recorder(**options):
    created = []

    def factory():
        pipeline = FakePipeline(**options)
        created.append(pipeline)
        return pipeline

    return factory, created


def test_real_stdio_protocol_lists_rag_tools():
    async def exercise():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "rag_server.rag_server"],
            cwd=AI_SERVICES_ROOT,
        )
        async with stdio_client(parameters) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                initialised = await session.initialize()
                listed = await session.list_tools()
        return initialised, listed

    initialised, listed = asyncio.run(exercise())
    assert initialised.serverInfo.name == SERVER_NAME
    assert [tool.name for tool in listed.tools] == list(AVAILABLE_TOOLS)


def test_mcp_tools_forward_arguments_and_close_pipeline(rag_settings):
    factory, created = factory_recorder()
    server = create_server(rag_settings, factory)
    tools = {tool.name: tool for tool in server._tool_manager.list_tools()}

    assert set(tools) == set(AVAILABLE_TOOLS)
    assert tools["refresh_corpus"].annotations.readOnlyHint is False
    assert tools["answer_question"].annotations.readOnlyHint is True

    answer = asyncio.run(
        server._tool_manager.call_tool(
            "answer_question",
            {"question": "What is available?", "top_k": 2},
        )
    )
    assert answer["data"]["arguments"] == [
        "chufeng_catalogue",
        "What is available?",
        2,
    ]
    assert created[0].closed is True


def test_http_health_and_operation_routes(rag_settings):
    factory, created = factory_recorder()
    client = create_app(rag_settings, factory).test_client()

    health = client.get("/health")
    refresh = client.post("/refresh", json={})
    retrieval = client.post("/retrieve", json={"query": "keyboard"})
    answer = client.post("/answer", json={"question": "What is available?"})

    assert health.status_code == 200
    assert health.json["tools"] == list(AVAILABLE_TOOLS)
    assert refresh.status_code == retrieval.status_code == answer.status_code == 200
    assert all(pipeline.closed for pipeline in created)


def test_http_returns_structured_input_and_service_errors(rag_settings):
    unavailable = error_response(
        "answer_question",
        RAGErrorCode.OLLAMA_UNAVAILABLE,
        "Ollama is unavailable.",
    )
    factory, _ = factory_recorder(response=unavailable)
    client = create_app(rag_settings, factory).test_client()

    invalid = client.post("/answer", data="not-json")
    service_error = client.post("/answer", json={"question": "test"})

    assert invalid.status_code == 400
    assert invalid.json["error"]["code"] == "INVALID_ARGUMENT"
    assert service_error.status_code == 503
    assert service_error.json["error"]["code"] == "OLLAMA_UNAVAILABLE"


def test_http_rejects_oversized_body_and_hides_unexpected_errors(rag_settings):
    normal_client = create_app(rag_settings, FakePipeline).test_client()
    oversized = normal_client.post(
        "/answer",
        data='{"question":"' + ("x" * MAX_REQUEST_BODY_BYTES) + '"}',
        content_type="application/json",
    )

    factory, created = factory_recorder(failure=RuntimeError("private details"))
    app = create_app(rag_settings, factory)
    app.config["PROPAGATE_EXCEPTIONS"] = False
    unexpected = app.test_client().post("/answer", json={"question": "test"})

    assert oversized.status_code == 413
    assert unexpected.status_code == 500
    assert unexpected.json["error"]["code"] == "INTERNAL_ERROR"
    assert "private details" not in unexpected.get_data(as_text=True)
    assert created[0].closed is True
