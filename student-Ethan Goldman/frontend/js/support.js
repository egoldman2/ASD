"use strict";

document.addEventListener("htmx:beforeSwap", (event) => {
  const status = event.detail.xhr.status;
  if (status >= 400 && status < 600) {
    if (workflowFeedback(event.detail.target)) {
      showSupportConnectionError(event);
      event.detail.shouldSwap = false;
      event.detail.isError = false;
      return;
    }
    event.detail.shouldSwap = true;
    event.detail.isError = false;
  }
});

const loader = document.querySelector("[data-admin-ticket-loader]");
if (loader) {
  const ticketId = new URLSearchParams(window.location.search).get("ticket") || "";
  if (!/^\d{1,20}$/.test(ticketId)) {
    loader.className = "supportPage adminState adminState--error";
    loader.textContent = "Select a valid ticket from the staff queue.";
  } else {
    loader.setAttribute("hx-get", `/api/support/ui/admin/tickets/${ticketId}`);
  }
}

// Examples fill the question; submission invokes the selected assistant.
document.addEventListener("click", (event) => {
  const example = event.target.closest("[data-support-question]");
  if (!example) return;
  const input = example.closest("form").querySelector('[name="question"]');
  input.value = example.dataset.supportQuestion;
  input.focus();
});

document.addEventListener("htmx:sendError", showSupportConnectionError);
document.addEventListener("htmx:timeout", showSupportConnectionError);
document.addEventListener("htmx:beforeRequest", (event) => {
  const target = event.detail.target;
  const feedback = workflowFeedback(target);
  if (feedback) {
    target.setAttribute("aria-busy", "true");
    feedback.textContent = "Working on the selected ticket workflow. This may take several minutes…";
    feedback.setAttribute("role", "status");
    return;
  }
  if (!target || !["mcp-results", "mcp-assistant-result", "rag-answer-result"].includes(target.id)) return;
  target.textContent = target.id === "rag-answer-result" ? "Finding support guidance…" : "Loading support data…";
  target.removeAttribute("role");
});
document.addEventListener("htmx:afterRequest", (event) => {
  const panel = event.detail.elt && event.detail.elt.closest("#multi-agent-panel");
  if (panel) panel.setAttribute("aria-busy", "false");
});
function workflowFeedback(target) {
  return target && target.id === "multi-agent-panel" ? target.querySelector("#multi-agent-feedback") : null;
}
function showSupportConnectionError(event) {
  const target = event.detail.target;
  const feedback = workflowFeedback(target);
  if (feedback) {
    target.setAttribute("aria-busy", "false");
    feedback.textContent = "The workflow request could not be confirmed. Reload recorded history before retrying; your ticket has not been changed by this workflow.";
    feedback.setAttribute("role", "alert");
    return;
  }
  if (!target || !["mcp-results", "mcp-assistant-result", "rag-answer-result"].includes(target.id)) return;
  target.textContent = "The support request could not complete. Check your connection and try again.";
  target.setAttribute("role", "alert");
}
