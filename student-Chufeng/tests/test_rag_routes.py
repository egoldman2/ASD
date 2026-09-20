
"""Route tests for Chufeng's personal RAG backend integration."""

from importlib import import_module


rag_controller = import_module(
    "student-Chufeng.backend.controllers.rag_controller"
)
rag_client_module = import_module(
    "student-Chufeng.backend.services.rag_client"
)
RAGClientError = rag_client_module.RAGClientError


def envelope(operation, data=None, *, success=True, error=None):
    return {
        "success": success,
        "operation": operation,
        "data": data,
        "citations": [],
        "confidence": "high" if success else None,
        "insufficient_context": False,
        "error": error,
    }


class StubRAGClient:
    def __init__(self, failure=None):
        self.failure = failure
        self.calls = []

    def _result(self, operation, *args):
        self.calls.append((operation, args))
        if self.failure:
            raise self.failure
        return envelope(operation, {"arguments": list(args)})

    def health(self):
        if self.failure:
            raise self.failure
        return {
            "status": "healthy",
            "enabled": True,
            "ollama_model": "qwen2.5:0.5b",
        }

    def refresh_corpus(self):
        return self._result("refresh_corpus")

    def retrieve_context(self, query, top_k):
        return self._result("retrieve_context", query, top_k)

    def answer_question(self, question, top_k):
        return self._result("answer_question", question, top_k)


def use_stub(monkeypatch, stub):
    monkeypatch.setattr(rag_controller, "_create_client", lambda: stub)


def test_status_reports_connected_rag(client, monkeypatch):
    use_stub(monkeypatch, StubRAGClient())

    response = client.get("/api/chufeng/rag/status")

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "enabled": True,
        "available": True,
        "scope": "chufeng_catalogue",
        "ollama_model": "qwen2.5:0.5b",
        "error": None,
    }


def test_status_reports_unavailable_rag_without_failing_page(client, monkeypatch):
    failure = RAGClientError(
        "The RAG server is unavailable.",
        code="RAG_UNAVAILABLE",
        status_code=503,
    )
    use_stub(monkeypatch, StubRAGClient(failure=failure))

    response = client.get("/api/chufeng/rag/status")

    assert response.status_code == 200
    assert response.get_json()["available"] is False
    assert response.get_json()["error"]["code"] == "RAG_UNAVAILABLE"


def test_refresh_route_calls_personal_corpus_refresh(client, monkeypatch):
    stub = StubRAGClient()
    use_stub(monkeypatch, stub)

    response = client.post("/api/chufeng/rag/refresh")

    assert response.status_code == 200
    assert stub.calls == [("refresh_corpus", ())]


def test_retrieve_and_answer_routes_validate_and_forward_input(client, monkeypatch):
    stub = StubRAGClient()
    use_stub(monkeypatch, stub)

    retrieval = client.post(
        "/api/chufeng/rag/retrieve",
        json={"query": " mechanical keyboard ", "top_k": 3},
    )
    answer = client.post(
        "/api/chufeng/rag/answer",
        json={"question": " What is available? ", "top_k": 4},
    )

    assert retrieval.status_code == answer.status_code == 200
    assert stub.calls == [
        ("retrieve_context", ("mechanical keyboard", 3)),
        ("answer_question", ("What is available?", 4)),
    ]


def test_routes_reject_invalid_input_before_calling_rag(client, monkeypatch):
    stub = StubRAGClient()
    use_stub(monkeypatch, stub)

    missing_question = client.post("/api/chufeng/rag/answer", json={})
    invalid_top_k = client.post(
        "/api/chufeng/rag/retrieve",
        json={"query": "keyboard", "top_k": 21},
    )

    assert missing_question.status_code == 400
    assert invalid_top_k.status_code == 400
    assert stub.calls == []


def test_route_maps_rag_service_error_to_http_status(client, monkeypatch):
    failure = {
        "success": False,
        "operation": "answer_question",
        "data": None,
        "citations": [],
        "confidence": None,
        "insufficient_context": False,
        "error": {
            "code": "OLLAMA_UNAVAILABLE",
            "message": "The local Ollama service is unavailable.",
        },
    }

    class FailingRAGClient(StubRAGClient):
        def answer_question(self, question, top_k):
            return failure

    use_stub(monkeypatch, FailingRAGClient())

    response = client.post(
        "/api/chufeng/rag/answer",
        json={"question": "What is available?"},
    )

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "OLLAMA_UNAVAILABLE"
