"""Disabled runtime paths cannot contact models even when integrations are present."""

from importlib import import_module
from pathlib import Path

import pytest
import requests

from shared.feature_flags import feature_enabled


@pytest.mark.parametrize("value,enabled", [("true", True), ("1", True), ("YES", True), ("on", True),
                                          ("false", False), ("0", False), ("off", False), ("unexpected", False)])
def test_feature_switches_fail_closed(monkeypatch, value, enabled):
    monkeypatch.setenv("AI_MODE_ENABLED", value)
    assert feature_enabled() is enabled


@pytest.mark.parametrize("module_name,function,arguments,error_name", [
    ("student-Chufeng.backend.controllers.ai_controller", "_call_ollama", ("question",), "OllamaUnavailableError"),
    ("student-Ethan Ting.backend.app", "ollama_chat", ("system", "question", 20), "OllamaUnavailableError"),
    ("student-Howard.backend.routes.order_routes", "ask_ollama", ("question",), None),
    ("student-Ryan_Nolan.backend.routes.assistant", "_call_ollama", ("question",), None),
])
def test_existing_model_boundaries_reject_disabled_calls(monkeypatch, module_name, function, arguments, error_name):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / "student-Ryan_Nolan/backend"))
    monkeypatch.setenv("AI_MODE_ENABLED", "false")
    module = import_module(module_name)

    def forbidden(*args, **kwargs):
        pytest.fail("Disabled mode contacted a model")

    monkeypatch.setattr(requests, "post", forbidden)
    if module_name.startswith("student-Chufeng"):
        monkeypatch.setattr(module.request, "urlopen", forbidden)
    if module_name.startswith("student-Ethan Ting"):
        monkeypatch.setattr(module, "urlopen", forbidden)
    error = getattr(module, error_name) if error_name else requests.RequestException
    with pytest.raises(error):
        getattr(module, function)(*arguments)


def test_catalogue_disabled_before_database_or_model(monkeypatch):
    module = import_module("student-Chufeng.backend.controllers.ai_controller")
    monkeypatch.setenv("AI_MODE_ENABLED", "false")
    monkeypatch.setattr(module.product_model, "get_products", lambda: pytest.fail("Disabled AI read catalogue"))
    monkeypatch.setattr(module, "_call_ollama", lambda *_: pytest.fail("Disabled AI contacted model"))
    body, status = module.ask_product_assistant({"message": "Recommend a product"})
    assert status == 503 and body["code"] == "AI_MODE_DISABLED"


def test_support_disabled_before_context_or_injected_client(monkeypatch):
    module = import_module("student-Ethan Goldman.support_backend.ai")
    monkeypatch.setenv("AI_MODE_ENABLED", "false")
    monkeypatch.setattr(module, "redact_ticket_context", lambda *_: pytest.fail("Disabled AI processed context"))
    with pytest.raises(module.OllamaDisabledError):
        module.analyze_ticket({})
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: pytest.fail("Disabled AI contacted model"))
    with pytest.raises(module.OllamaDisabledError):
        module.OllamaClient("http://127.0.0.1:1", "test").chat("question")


def test_rag_generation_requires_ai_mode_even_when_rag_enabled(monkeypatch):
    module = import_module("student-Chufeng.backend.services.rag_client")
    monkeypatch.setenv("AI_MODE_ENABLED", "false")
    client = module.ChufengRAGClient(module.RAGClientSettings(True, "http://127.0.0.1:1", 1),
                                    http_request=lambda **_: pytest.fail("Disabled generation contacted RAG"))
    with pytest.raises(module.RAGClientError) as error:
        client.answer_question("Which product?", 3)
    assert error.value.code == "AI_MODE_DISABLED"


def test_host_rag_and_runner_do_not_contact_models_when_disabled(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / "ai-services"))
    monkeypatch.setenv("AI_MODE_ENABLED", "false")
    rag = import_module("rag_server.ollama_client")
    client = rag.OllamaClient(http_post=lambda *args, **kwargs: pytest.fail("Disabled host RAG contacted model"))
    with pytest.raises(rag.OllamaUnavailableError, match="disabled"):
        client.generate_answer("system", "question")
    runner = import_module("agentic_loop")
    monkeypatch.setattr(runner.request, "urlopen", lambda *args, **kwargs: pytest.fail("Disabled runner contacted model"))
    with pytest.raises(runner.OllamaError, match="disabled"):
        runner._call_ollama("question")
