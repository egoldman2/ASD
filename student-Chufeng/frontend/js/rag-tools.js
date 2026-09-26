
const RAG_API_ROOT = "http://localhost:5000/api/chufeng/rag";
const RAG_STATUS_URL = `${RAG_API_ROOT}/status`;
const RAG_REFRESH_URL = `${RAG_API_ROOT}/refresh`;
const RAG_RETRIEVE_URL = `${RAG_API_ROOT}/retrieve`;
const RAG_ANSWER_URL = `${RAG_API_ROOT}/answer`;
const RAG_MODE_STORAGE_KEY = "chufeng_rag_mode_enabled";

const statusDot = document.querySelector("#ragStatusDot");
const statusTitle = document.querySelector("#ragStatusTitle");
const statusMessage = document.querySelector("#ragStatusMessage");
const modelBadge = document.querySelector("#ragModelBadge");
const refreshStatusButton = document.querySelector("#refreshRagStatusButton");
const ragModeToggle = document.querySelector("#ragModeToggle");
const ragModeState = document.querySelector("#ragModeState");
const ragWorkspace = document.querySelector(".mcpWorkspace");
const taskButtons = [...document.querySelectorAll("[data-rag-panel]")];
const taskPanels = [...document.querySelectorAll(".mcpToolPanel")];
const refreshCorpusForm = document.querySelector("#refreshCorpusForm");
const retrieveContextForm = document.querySelector("#retrieveContextForm");
const answerQuestionForm = document.querySelector("#answerQuestionForm");
const resultSection = document.querySelector("#ragResultSection");
const resultTitle = document.querySelector("#ragResultTitle");
const resultStatus = document.querySelector("#ragResultStatus");
const confidenceBadge = document.querySelector("#ragConfidenceBadge");
const friendlyResult = document.querySelector("#ragFriendlyResult");
const evidenceOperation = document.querySelector("#ragEvidenceOperation");
const evidenceScope = document.querySelector("#ragEvidenceScope");
const requestOutput = document.querySelector("#ragRequestOutput");
const responseOutput = document.querySelector("#ragResponseOutput");

function isRagModeEnabled() {
  return ragModeToggle.checked;
}

function requestHeaders(includeJson = false) {
  const headers = { "X-RAG-Mode": isRagModeEnabled() ? "on" : "off" };
  if (includeJson) headers["Content-Type"] = "application/json";
  return headers;
}

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    throw new Error(`The backend returned an invalid response (${response.status}).`);
  }
}

function setConnectionState(state, title, message, model = "Model unavailable") {
  statusDot.className = `mcpStatusDot mcpStatusDot--${state}`;
  statusTitle.textContent = title;
  statusMessage.textContent = message;
  modelBadge.textContent = model;
}

async function loadRagStatus() {
  if (!isRagModeEnabled()) {
    setConnectionState(
      "offline",
      "RAG mode disabled",
      "Enable RAG mode to check the connection and run the workflow.",
    );
    return;
  }

  refreshStatusButton.disabled = true;
  refreshStatusButton.textContent = "Checking...";
  setConnectionState("checking", "Checking RAG status...", "Contacting the Chufeng backend.");

  try {
    const response = await fetch(RAG_STATUS_URL, { headers: requestHeaders() });
    const payload = await readJson(response);
    if (!response.ok || payload.success !== true) {
      throw new Error(payload.error?.message || "Unable to check RAG status.");
    }
    if (!payload.enabled) {
      setConnectionState(
        "offline",
        "RAG integration disabled",
        payload.error?.message || "Enable RAG in the backend configuration.",
      );
      return;
    }
    if (!payload.available) {
      setConnectionState(
        "offline",
        "RAG server unavailable",
        payload.error?.message || "Start the local RAG server and try again.",
      );
      return;
    }
    setConnectionState(
      "online",
      "RAG connected",
      `Knowledge scope ${payload.scope} is ready for grounded retrieval.`,
      payload.ollama_model || "Local Ollama",
    );
  } catch (error) {
    console.error("Unable to check RAG status:", error);
    setConnectionState("offline", "RAG connection failed", error.message);
  } finally {
    refreshStatusButton.disabled = false;
    refreshStatusButton.textContent = "Refresh status";
  }
}

function selectTaskPanel(panelId) {
  taskButtons.forEach((button) => {
    const selected = button.dataset.ragPanel === panelId;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-selected", String(selected));
  });
  taskPanels.forEach((panel) => {
    panel.hidden = panel.id !== panelId;
  });
}

function topKFromForm(form) {
  const topK = Number(new FormData(form).get("top_k"));
  if (!Number.isInteger(topK) || topK < 1 || topK > 20) {
    throw new Error("Top K must be a whole number between 1 and 20.");
  }
  return topK;
}

function textElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  element.textContent = text;
  return element;
}

function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("en-AU");
}

function citationList(citations) {
  const list = document.createElement("ol");
  list.className = "ragCitationList";
  citations.forEach((citation) => {
    const item = document.createElement("li");
    const label = citation.label || citation.document_id || "Catalogue evidence";
    const sourceId = citation.source_id || "unknown source";
    item.append(
      textElement("strong", "", label),
      textElement("span", "ragSourceId", `Source: ${sourceId}`),
    );
    list.append(item);
  });
  return list;
}

function renderRefresh(payload) {
  const data = payload.data || {};
  const heading = textElement("h3", "", "Knowledge base refreshed");
  const summary = document.createElement("div");
  summary.className = "ragMetricGrid";
  [
    ["Documents", data.document_count],
    ["Added", data.added_count],
    ["Updated", data.updated_count],
    ["Removed", data.removed_count],
  ].forEach(([label, value]) => {
    const metric = document.createElement("div");
    metric.append(textElement("span", "", label), textElement("strong", "", value ?? 0));
    summary.append(metric);
  });
  const detail = textElement(
    "p",
    "ragResultNote",
    `${data.source || "Catalogue source"} → ${data.collection || "ChromaDB"} · ${formatDate(data.refreshed_at || "now")}`,
  );
  friendlyResult.append(heading, summary, detail);
}

function renderRetrieval(payload) {
  const data = payload.data || {};
  const results = Array.isArray(data.results) ? data.results : [];
  friendlyResult.append(
    textElement("h3", "", `${results.length} relevant context ${results.length === 1 ? "result" : "results"}`),
  );
  if (!results.length) {
    friendlyResult.append(textElement("p", "ragResultNote", "No evidence passed the minimum relevance threshold."));
    return;
  }
  const resultList = document.createElement("div");
  resultList.className = "ragRetrievalList";
  results.forEach((result) => {
    const card = document.createElement("article");
    card.className = "ragRetrievalCard";
    const citation = result.citation || {};
    const score = Number(result.relevance_score);
    card.append(
      textElement("p", "ragRank", `#${result.rank ?? "-"} · ${citation.label || result.document_id || "Evidence"}`),
      textElement("p", "ragDocumentText", result.text || "No document text returned."),
      textElement(
        "p",
        "ragResultMeta",
        `Source: ${citation.source_id || "unknown"} · Relevance: ${Number.isFinite(score) ? `${Math.round(score * 100)}%` : "n/a"} · Distance: ${result.distance ?? "n/a"}`,
      ),
    );
    resultList.append(card);
  });
  friendlyResult.append(resultList);
}

function renderAnswer(payload) {
  const data = payload.data || {};
  friendlyResult.append(
    textElement("h3", "", payload.insufficient_context ? "Insufficient grounded context" : "Grounded answer"),
    textElement("p", "ragAnswerText", data.answer || "No answer was returned."),
    textElement("p", "ragResultNote", `Model: ${data.model || "not invoked"} · Retrieved: ${data.retrieved_count ?? 0}`),
  );
  const citations = Array.isArray(payload.citations) ? payload.citations : [];
  if (citations.length) {
    friendlyResult.append(textElement("h4", "ragCitationHeading", "Cited sources"), citationList(citations));
  } else {
    friendlyResult.append(textElement("p", "ragResultNote", "No sources were cited."));
  }
}

function renderFriendlyResult(operation, payload) {
  friendlyResult.replaceChildren();
  if (operation === "refresh_corpus") renderRefresh(payload);
  if (operation === "retrieve_context") renderRetrieval(payload);
  if (operation === "answer_question") renderAnswer(payload);
}

function showResult(operation, requestBody, payload, ok) {
  resultSection.hidden = false;
  resultTitle.textContent = {
    refresh_corpus: "Corpus refresh result",
    retrieve_context: "Retrieved RAG context",
    answer_question: "Grounded answer",
  }[operation] || "RAG result";
  evidenceOperation.textContent = operation;
  evidenceScope.textContent = payload.data?.scope || "chufeng_catalogue";
  requestOutput.textContent = JSON.stringify(requestBody, null, 2);
  responseOutput.textContent = JSON.stringify(payload, null, 2);
  resultStatus.textContent = ok ? "Verified live result" : "Request failed";
  resultStatus.className = `mcpResultStatus ${ok ? "mcpResultStatus--success" : "mcpResultStatus--error"}`;

  const confidence = payload.confidence;
  confidenceBadge.hidden = !confidence;
  confidenceBadge.textContent = confidence ? `${confidence} confidence` : "";
  confidenceBadge.className = `ragConfidenceBadge ragConfidenceBadge--${confidence || "none"}`;

  if (ok && payload.success === true) {
    renderFriendlyResult(operation, payload);
  } else {
    friendlyResult.replaceChildren(
      textElement("p", "", payload.error?.message || "The RAG request failed."),
    );
  }
  resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function runOperation({ operation, url, body, submitButton }) {
  if (!isRagModeEnabled()) {
    showResult(
      operation,
      body,
      { error: { code: "RAG_DISABLED", message: "Enable RAG mode before running this task." } },
      false,
    );
    return;
  }

  const originalText = submitButton.textContent;
  submitButton.disabled = true;
  submitButton.textContent = "Running...";
  try {
    const options = { method: "POST", headers: requestHeaders(true) };
    if (body !== null) options.body = JSON.stringify(body);
    const response = await fetch(url, options);
    const payload = await readJson(response);
    showResult(operation, body || { scope: "chufeng_catalogue" }, payload, response.ok && payload.success === true);
  } catch (error) {
    console.error(`Unable to run ${operation}:`, error);
    showResult(operation, body || {}, { error: { code: "NETWORK_ERROR", message: error.message } }, false);
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = originalText;
  }
}

function updateRagMode() {
  const enabled = isRagModeEnabled();
  localStorage.setItem(RAG_MODE_STORAGE_KEY, String(enabled));
  ragModeState.textContent = enabled ? "ON" : "OFF";
  ragModeState.className = `mcpModeState ${enabled ? "mcpModeState--on" : "mcpModeState--off"}`;
  ragWorkspace.classList.toggle("mcpWorkspace--disabled", !enabled);
  ragWorkspace.querySelectorAll("button, input, textarea").forEach((control) => {
    control.disabled = !enabled;
  });
  loadRagStatus();
}

taskButtons.forEach((button) => {
  button.addEventListener("click", () => selectTaskPanel(button.dataset.ragPanel));
});

refreshCorpusForm.addEventListener("submit", (event) => {
  event.preventDefault();
  runOperation({
    operation: "refresh_corpus",
    url: RAG_REFRESH_URL,
    body: null,
    submitButton: event.submitter,
  });
});

retrieveContextForm.addEventListener("submit", (event) => {
  event.preventDefault();
  try {
    const formData = new FormData(retrieveContextForm);
    runOperation({
      operation: "retrieve_context",
      url: RAG_RETRIEVE_URL,
      body: { query: String(formData.get("query") || "").trim(), top_k: topKFromForm(retrieveContextForm) },
      submitButton: event.submitter,
    });
  } catch (error) {
    showResult("retrieve_context", {}, { error: { message: error.message } }, false);
  }
});

answerQuestionForm.addEventListener("submit", (event) => {
  event.preventDefault();
  try {
    const formData = new FormData(answerQuestionForm);
    runOperation({
      operation: "answer_question",
      url: RAG_ANSWER_URL,
      body: { question: String(formData.get("question") || "").trim(), top_k: topKFromForm(answerQuestionForm) },
      submitButton: event.submitter,
    });
  } catch (error) {
    showResult("answer_question", {}, { error: { message: error.message } }, false);
  }
});

refreshStatusButton.addEventListener("click", loadRagStatus);
ragModeToggle.addEventListener("change", updateRagMode);

const savedMode = localStorage.getItem(RAG_MODE_STORAGE_KEY);
ragModeToggle.checked = savedMode === null ? true : savedMode === "true";
updateRagMode();
