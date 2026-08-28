from importlib import import_module
import json


VALID_ANALYSIS = {
    "summary": "The customer reports a missing parcel after a delivered scan.",
    "category": "delivery",
    "sentiment": "negative",
    "priority": "high",
    "draft_response": (
        "Thank you for confirming the delivery details. We are reviewing the "
        "courier investigation and will update you as soon as possible."
    ),
}


def _ai_controller():
    return import_module(
        "student-Ethan Goldman.backend.controllers.ai_controller"
    )


def test_ai_analysis_is_structured_private_and_read_only(client, monkeypatch):
    ai_controller = _ai_controller()
    prompts = []

    def fake_ollama(prompt):
        prompts.append(prompt)
        return json.dumps(VALID_ANALYSIS)

    monkeypatch.setattr(ai_controller, "_call_ollama", fake_ollama)
    client.post(
        "/api/support-tickets/1011/messages",
        json={
            "sender_role": "customer",
            "message": (
                "Oliver Jones can be reached at oliver.jones@example.com; "
                "please ask Alex Morgan for an update."
            ),
        },
    )
    before = client.get("/api/support-tickets/1011").json["ticket"]

    response = client.post(
        "/api/ai/support-assistant", json={"ticket_id": 1011}
    )

    assert response.status_code == 200
    assert response.json["analysis"] == VALID_ANALYSIS
    assert response.json["model"] == "qwen2.5:0.5b"
    assert set(response.json["workflow"]) == {"plan", "act", "observe", "adapt"}
    assert "<ticket_data>" in prompts[0]
    assert "Oliver Jones" not in prompts[0]
    assert "oliver.jones@example.com" not in prompts[0]
    assert "Alex Morgan" not in prompts[0]
    assert "1011" not in prompts[0]
    assert prompts[0].count("[name removed]") == 2
    assert "[email removed]" in prompts[0]
    assert client.get("/api/support-tickets/1011").json["ticket"] == before


def test_ai_analysis_validates_input_and_missing_ticket(client, monkeypatch):
    ai_controller = _ai_controller()
    calls = []
    monkeypatch.setattr(ai_controller, "_call_ollama", calls.append)

    missing_body = client.post("/api/ai/support-assistant")
    invalid_id = client.post(
        "/api/ai/support-assistant", json={"ticket_id": "1011"}
    )
    missing_ticket = client.post(
        "/api/ai/support-assistant", json={"ticket_id": 9999}
    )

    assert missing_body.status_code == 400
    assert invalid_id.status_code == 400
    assert missing_ticket.status_code == 404
    assert calls == []


def test_ai_analysis_retries_invalid_output_once(client, monkeypatch):
    ai_controller = _ai_controller()
    responses = iter(("not json", json.dumps(VALID_ANALYSIS)))
    prompts = []

    def fake_ollama(prompt):
        prompts.append(prompt)
        return next(responses)

    monkeypatch.setattr(ai_controller, "_call_ollama", fake_ollama)
    response = client.post(
        "/api/ai/support-assistant", json={"ticket_id": 1011}
    )

    assert response.status_code == 200
    assert len(prompts) == 2
    assert "Correction required" in prompts[1]
    assert "corrected response" in response.json["workflow"]["adapt"]


def test_ai_analysis_retries_invalid_enum(client, monkeypatch):
    ai_controller = _ai_controller()
    invalid = {**VALID_ANALYSIS, "sentiment": "furious"}
    responses = iter((json.dumps(invalid), json.dumps(VALID_ANALYSIS)))
    monkeypatch.setattr(ai_controller, "_call_ollama", lambda _prompt: next(responses))

    response = client.post(
        "/api/ai/support-assistant", json={"ticket_id": 1011}
    )

    assert response.status_code == 200
    assert response.json["analysis"]["sentiment"] == "negative"


def test_ai_analysis_rejects_repeated_invalid_output(client, monkeypatch):
    ai_controller = _ai_controller()
    calls = []

    def invalid_ollama(prompt):
        calls.append(prompt)
        return json.dumps({"summary": "Incomplete"})

    monkeypatch.setattr(ai_controller, "_call_ollama", invalid_ollama)
    response = client.post(
        "/api/ai/support-assistant", json={"ticket_id": 1011}
    )

    assert response.status_code == 502
    assert response.json == {
        "error": "The AI assistant returned an invalid response."
    }
    assert len(calls) == 2


def test_ai_analysis_handles_unavailable_ollama(client, monkeypatch):
    ai_controller = _ai_controller()

    def unavailable(_prompt):
        raise ai_controller.OllamaUnavailableError

    monkeypatch.setattr(ai_controller, "_call_ollama", unavailable)
    response = client.post(
        "/api/ai/support-assistant", json={"ticket_id": 1011}
    )

    assert response.status_code == 503
    assert response.json == {"error": "The AI assistant is currently unavailable."}


def test_ai_analysis_handles_invalid_ollama_envelope(client, monkeypatch):
    ai_controller = _ai_controller()

    def invalid_response(_prompt):
        raise ai_controller.OllamaResponseError

    monkeypatch.setattr(ai_controller, "_call_ollama", invalid_response)
    response = client.post(
        "/api/ai/support-assistant", json={"ticket_id": 1011}
    )

    assert response.status_code == 502
    assert response.json == {
        "error": "The AI assistant returned an invalid response."
    }


def test_staff_htmx_ai_analysis_renders_escaped_result(client, monkeypatch):
    ai_controller = _ai_controller()
    unsafe_analysis = {
        **VALID_ANALYSIS,
        "draft_response": "<script>alert('unsafe')</script> Staff review draft.",
    }
    monkeypatch.setattr(
        ai_controller, "_call_ollama", lambda _prompt: json.dumps(unsafe_analysis)
    )

    response = client.post(
        "/support-ui/staff/tickets/1011/ai-analysis",
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert b"Suggested response" in response.data
    assert b"Plan" in response.data
    assert b"&lt;script&gt;" in response.data
    assert b"<script>" not in response.data
