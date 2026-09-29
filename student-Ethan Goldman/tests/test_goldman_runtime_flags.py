"""Disabled support AI remains safe through JSON and HTMX routes."""

from importlib import import_module

import pytest


def test_disabled_ai_returns_clear_states_without_model_calls(support_stack, monkeypatch):
    ai = import_module("student-Ethan Goldman.support_backend.ai")
    monkeypatch.setenv("AI_MODE_ENABLED", "false")
    monkeypatch.setattr(ai.OllamaClient, "chat", lambda *args: pytest.fail("Disabled route invoked model"))
    admin = support_stack.admin()
    json_result = admin.post(support_stack.backend.url + "/api/support/admin/tickets/2002/ai-analysis",
                             headers=support_stack.origin_headers, timeout=10)
    assert json_result.status_code == 503 and json_result.json()["error"] == "AI mode is disabled."
    ui_result = admin.post(support_stack.backend.url + "/api/support/ui/admin/tickets/2002/ai-analysis",
                           headers=support_stack.htmx_headers, timeout=10)
    assert ui_result.status_code == 503 and "AI mode is disabled." in ui_result.text
    assert 'id="ai-panel"' in ui_result.text
    assert admin.get(support_stack.backend.url + "/api/support/admin/tickets", timeout=10).status_code == 200
