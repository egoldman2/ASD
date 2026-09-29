"use strict";

document.addEventListener("htmx:beforeSwap", (event) => {
  const status = event.detail.xhr.status;
  if (status >= 400 && status < 600) {
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
  if (!target || !["mcp-results", "mcp-assistant-result", "rag-answer-result"].includes(target.id)) return;
  target.textContent = target.id === "rag-answer-result" ? "Finding support guidance…" : "Loading support data…";
  target.removeAttribute("role");
});
function showSupportConnectionError(event) {
  const target = event.detail.target;
  if (!target || !["mcp-results", "mcp-assistant-result", "rag-answer-result"].includes(target.id)) return;
  target.textContent = "The support request could not complete. Check your connection and try again.";
  target.setAttribute("role", "alert");
}
