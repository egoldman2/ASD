(function () {
  "use strict";

  const API_ORIGIN = "http://localhost:8102";
  const RAG_STATUS_API = `${API_ORIGIN}/api/inventory/rag/status`;
  const RAG_REFRESH_API = `${API_ORIGIN}/api/inventory/rag/refresh`;
  const RAG_ANSWER_API = `${API_ORIGIN}/api/inventory/rag/answer`;

  const statusLine = document.getElementById("ragStatusLine");
  const form = document.getElementById("ragForm");
  const question = document.getElementById("ragQuestion");
  const askButton = document.getElementById("ragAskButton");
  const refreshButton = document.getElementById("ragRefreshButton");
  const answerBox = document.getElementById("ragAnswer");
  const confidenceLine = document.getElementById("ragConfidence");
  const citationsBox = document.getElementById("ragCitations");

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  function clearResult() {
    answerBox.value = "";
    confidenceLine.textContent = "";
    citationsBox.innerHTML = "";
  }

  async function refreshStatus() {
    if (!statusLine) return;
    try {
      const response = await fetch(RAG_STATUS_API, {
        method: "GET",
        headers: { Accept: "application/json" },
        credentials: "include",
      });
      const data = await response.json();

      if (!data.enabled) {
        statusLine.textContent = "RAG is disabled in this environment.";
      } else if (!data.available) {
        statusLine.textContent = "RAG server is unreachable right now.";
      } else {
        statusLine.textContent = `RAG connected: scope ${data.scope}, model ${data.model}.`;
      }
    } catch (err) {
      statusLine.textContent = "Could not check RAG status.";
    }
  }

  async function post(url, body) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(body),
    });
    const payload = await response.json();
    return { status: response.status, payload };
  }

  function renderAnswer(status, payload) {
    clearResult();

    if (payload && payload.error && !payload.success) {
      answerBox.value = `[HTTP ${status}] ${payload.error.code}: ${payload.error.message}`;
      return;
    }

    const data = payload.data || {};
    answerBox.value = data.answer || "No answer returned.";

    if (payload.insufficient_context) {
      confidenceLine.textContent = "Confidence: insufficient. No relevant context was found, so no answer was generated.";
    } else {
      confidenceLine.textContent = `Confidence: ${payload.confidence}`;
    }

    const citations = Array.isArray(payload.citations) ? payload.citations : [];
    if (citations.length) {
      citationsBox.innerHTML =
        "<strong>Sources:</strong><ul>" +
        citations
          .map((c) => `<li>[${escapeHtml(c.rank)}] ${escapeHtml(c.label)}</li>`)
          .join("") +
        "</ul>";
    } else {
      citationsBox.textContent = "Sources: none";
    }
  }

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();

    const text = question.value.trim();
    if (!text) return;

    clearResult();
    answerBox.placeholder = "Thinking...";
    askButton.disabled = true;

    try {
      const { status, payload } = await post(RAG_ANSWER_API, { question: text });
      renderAnswer(status, payload);
    } catch (err) {
      answerBox.value = "The knowledge assistant is unavailable right now. Please try again.";
      console.error("RAG answer failed:", err);
    } finally {
      answerBox.placeholder = "The grounded answer will appear here.";
      askButton.disabled = false;
    }
  });

  refreshButton?.addEventListener("click", async () => {
    clearResult();
    refreshButton.disabled = true;
    answerBox.value = "Refreshing knowledge...";

    try {
      const { status, payload } = await post(RAG_REFRESH_API, {});
      if (payload && payload.success) {
        answerBox.value = `Knowledge refreshed: ${payload.data.document_count} documents indexed.`;
      } else {
        const err = payload.error || {};
        answerBox.value = `[HTTP ${status}] ${err.code}: ${err.message}`;
      }
    } catch (err) {
      answerBox.value = "Could not refresh knowledge.";
      console.error("RAG refresh failed:", err);
    } finally {
      refreshButton.disabled = false;
    }
  });

  document.addEventListener("DOMContentLoaded", refreshStatus);
})();