"""Deterministic tests for the shared Ollama model client."""

from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from multi_agent_server.config import MultiAgentSettings
from multi_agent_server.model_client import (
    AgentRole,
    ModelConnectionError,
    ModelGeneration,
    ModelHTTPError,
    ModelResponseError,
    ModelTimeoutError,
    OllamaModelClient,
)


@pytest.fixture
def settings():
    return MultiAgentSettings(
        host="127.0.0.1",
        port=5004,
        ollama_url="http://localhost:11434",
        planner_model="planner:test",
        worker_model="worker:test",
        reviewer_model="reviewer:test",
        timeout_seconds=12.5,
        max_request_bytes=65_536,
        log_dir=Path("runtime-logs"),
    )


def successful_session(text="Generated answer"):
    response = Mock(status_code=200)
    response.json.return_value = {"response": text, "done": True}
    session = Mock()
    session.post.return_value = response
    return session


@pytest.mark.parametrize(
    ("role", "expected_model"),
    [
        (AgentRole.PLANNER, "planner:test"),
        (AgentRole.WORKER, "worker:test"),
        (AgentRole.REVIEWER, "reviewer:test"),
        (" PLANNER ", "planner:test"),
    ],
)
def test_model_for_selects_the_role_configuration(settings, role, expected_model):
    client = OllamaModelClient(settings, successful_session())

    assert client.model_for(role) == expected_model


def test_generate_sends_one_non_streaming_request(settings):
    session = successful_session("  Use the supplied evidence.  ")
    client = OllamaModelClient(settings, session)

    result = client.generate(AgentRole.WORKER, "Analyse this evidence")

    session.post.assert_called_once_with(
        "http://localhost:11434/api/generate",
        json={
            "model": "worker:test",
            "prompt": "Analyse this evidence",
            "stream": False,
            "options": {"temperature": 0.1},
        },
        timeout=12.5,
    )
    assert isinstance(result, ModelGeneration)
    assert result.role is AgentRole.WORKER
    assert result.model == "worker:test"
    assert result.text == "Use the supplied evidence."
    assert result.elapsed_ms >= 0
    assert result.to_dict() == {
        "role": "worker",
        "model": "worker:test",
        "response": "Use the supplied evidence.",
        "elapsed_ms": result.elapsed_ms,
    }


@pytest.mark.parametrize("role", [None, "", "manager", 12])
def test_invalid_roles_fail_before_calling_ollama(settings, role):
    session = successful_session()
    client = OllamaModelClient(settings, session)

    with pytest.raises(ValueError, match="planner, worker, reviewer"):
        client.generate(role, "prompt")

    session.post.assert_not_called()


@pytest.mark.parametrize(
    ("prompt", "error_type", "message"),
    [
        (None, TypeError, "prompt must be a string"),
        ("   ", ValueError, "prompt must not be empty"),
    ],
)
def test_invalid_prompts_fail_before_calling_ollama(
    settings, prompt, error_type, message
):
    session = successful_session()
    client = OllamaModelClient(settings, session)

    with pytest.raises(error_type, match=message):
        client.generate(AgentRole.PLANNER, prompt)

    session.post.assert_not_called()


@pytest.mark.parametrize(
    ("network_error", "expected_error", "code"),
    [
        (requests.Timeout("slow"), ModelTimeoutError, "model_timeout"),
        (
            requests.ConnectionError("offline"),
            ModelConnectionError,
            "model_connection_error",
        ),
        (
            requests.RequestException("request failed"),
            ModelConnectionError,
            "model_connection_error",
        ),
    ],
)
def test_network_errors_are_categorised(
    settings, network_error, expected_error, code
):
    session = Mock()
    session.post.side_effect = network_error
    client = OllamaModelClient(settings, session)

    with pytest.raises(expected_error) as caught:
        client.generate(AgentRole.PLANNER, "Make a plan")

    assert caught.value.code == code
    assert caught.value.role is AgentRole.PLANNER
    assert caught.value.model == "planner:test"
    assert "slow" not in str(caught.value)


def test_http_error_keeps_status_without_exposing_response_body(settings):
    response = Mock(status_code=404, text="sensitive server response")
    session = Mock()
    session.post.return_value = response
    client = OllamaModelClient(settings, session)

    with pytest.raises(ModelHTTPError) as caught:
        client.generate(AgentRole.REVIEWER, "Review the answer")

    assert caught.value.status_code == 404
    assert caught.value.to_dict() == {
        "error": {
            "code": "model_http_error",
            "message": "Ollama returned HTTP 404.",
            "role": "reviewer",
            "model": "reviewer:test",
            "status_code": 404,
        }
    }
    assert "sensitive" not in str(caught.value)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ([], "must be a JSON object"),
        ({}, "missing generated text"),
        ({"response": None}, "missing generated text"),
        ({"response": "   "}, "missing generated text"),
    ],
)
def test_invalid_success_payloads_are_rejected(settings, payload, message):
    response = Mock(status_code=200)
    response.json.return_value = payload
    session = Mock()
    session.post.return_value = response
    client = OllamaModelClient(settings, session)

    with pytest.raises(ModelResponseError, match=message):
        client.generate(AgentRole.WORKER, "Do the work")


def test_invalid_json_is_rejected(settings):
    response = Mock(status_code=200)
    response.json.side_effect = ValueError("not json")
    session = Mock()
    session.post.return_value = response
    client = OllamaModelClient(settings, session)

    with pytest.raises(ModelResponseError, match="invalid JSON") as caught:
        client.generate(AgentRole.WORKER, "Do the work")

    assert caught.value.to_dict()["error"]["code"] == "model_response_error"
