const MULTI_AGENT_API_ROOT = "http://localhost:5000/api/chufeng/multi-agent";
const MULTI_AGENT_STATUS_URL = `${MULTI_AGENT_API_ROOT}/status`;
const MULTI_AGENT_WORKFLOWS_URL = `${MULTI_AGENT_API_ROOT}/workflows`;
const PRODUCTS_API_URL = "http://localhost:5000/api/products";

const statusDot = document.querySelector("#multiAgentStatusDot");
const statusTitle = document.querySelector("#multiAgentStatusTitle");
const statusMessage = document.querySelector("#multiAgentStatusMessage");
const featureBadge = document.querySelector("#multiAgentFeatureBadge");
const refreshStatusButton = document.querySelector("#refreshMultiAgentStatusButton");
const workflowForm = document.querySelector("#multiAgentWorkflowForm");
const productSelect = document.querySelector("#multiAgentProductSelect");
const productHint = document.querySelector("#multiAgentProductHint");
const runWorkflowButton = document.querySelector("#runMultiAgentWorkflowButton");
const loadLatestButton = document.querySelector("#loadLatestWorkflowButton");
const resultSection = document.querySelector("#multiAgentResultSection");
const resultTitle = document.querySelector("#multiAgentResultTitle");
const resultStatus = document.querySelector("#multiAgentResultStatus");
const workflowIdOutput = document.querySelector("#multiAgentWorkflowId");
const workflowFeatureOutput = document.querySelector("#multiAgentWorkflowFeature");
const workflowTimeOutput = document.querySelector("#multiAgentWorkflowTime");
const agentGrid = document.querySelector("#multiAgentAgentGrid");
const evidenceList = document.querySelector("#multiAgentEvidenceList");
const reviewPanel = document.querySelector("#multiAgentHumanReviewPanel");
const reviewForm = document.querySelector("#multiAgentReviewForm");
const reviewSummary = document.querySelector("#multiAgentReviewSummary");
const submitReviewButton = document.querySelector("#submitMultiAgentReviewButton");
const rawOutput = document.querySelector("#multiAgentRawOutput");
const refreshHistoryButton = document.querySelector("#refreshMultiAgentHistoryButton");
const historyMessage = document.querySelector("#multiAgentHistoryMessage");
const historyList = document.querySelector("#multiAgentHistoryList");

let activeWorkflowId = null;

function textElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  element.textContent = text;
  return element;
}

function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value || "-") : date.toLocaleString("en-AU");
}

function errorMessage(payload, fallback) {
  if (typeof payload?.error === "string") return payload.error;
  if (typeof payload?.error?.message === "string") return payload.error.message;
  if (typeof payload?.message === "string") return payload.message;
  return fallback;
}

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    throw new Error(`The backend returned an invalid response (${response.status}).`);
  }
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    credentials: "include",
    ...options,
  });
  const payload = await readJson(response);
  if (!response.ok) {
    const error = new Error(errorMessage(payload, `Request failed with status ${response.status}.`));
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

function jsonRequest(method, body) {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

function setConnectionState(state, title, message) {
  statusDot.className = `mcpStatusDot mcpStatusDot--${state}`;
  statusTitle.textContent = title;
  statusMessage.textContent = message;
}

async function loadStatus() {
  refreshStatusButton.disabled = true;
  refreshStatusButton.textContent = "Checking...";
  setConnectionState("checking", "Checking Multi-Agent status...", "Contacting the Chufeng backend.");
  try {
    const payload = await requestJson(MULTI_AGENT_STATUS_URL);
    featureBadge.textContent = payload.feature || "product_catalogue";
    if (!payload.enabled) {
      setConnectionState("offline", "Multi-Agent integration disabled", errorMessage(payload, "Enable the service in backend configuration."));
    } else if (!payload.available) {
      setConnectionState("offline", "Multi-Agent server unavailable", errorMessage(payload, "Start the shared Multi-Agent server and try again."));
    } else {
      setConnectionState("online", "Multi-Agent server connected", "Planner, Worker, Reviewer, and Human Review are ready.");
    }
  } catch (error) {
    const message = error.status === 401
      ? "Sign in before using the protected Multi-Agent workflow."
      : error.message;
    setConnectionState("offline", "Multi-Agent connection failed", message);
  } finally {
    refreshStatusButton.disabled = false;
    refreshStatusButton.textContent = "Refresh status";
  }
}

async function loadProducts() {
  try {
    const payload = await requestJson(PRODUCTS_API_URL);
    const products = Array.isArray(payload.products) ? payload.products : [];
    products.forEach((product) => {
      const option = document.createElement("option");
      option.value = String(product.id);
      option.textContent = `#${product.id} · ${product.name} · ${product.stock_quantity} in stock`;
      productSelect.append(option);
    });
    productHint.textContent = products.length
      ? `${products.length} live products available. Selecting one keeps the evidence focused.`
      : "No products are currently available; the catalogue snapshot option may fail.";
  } catch (error) {
    productHint.textContent = `Products could not be loaded: ${error.message}`;
    productHint.classList.add("multiAgentFieldError");
  }
}

function agentCard(label, result, bodyKey) {
  const card = document.createElement("article");
  card.className = "multiAgentAgentCard";
  const heading = document.createElement("div");
  heading.className = "multiAgentAgentHeading";
  heading.append(
    textElement("h3", "", label),
    textElement("span", "multiAgentAgentStatus", result?.status || "not run"),
  );
  const output = textElement(
    "p",
    "multiAgentAgentOutput",
    result?.[bodyKey] || "No output was returned.",
  );
  const metadata = textElement(
    "p",
    "multiAgentAgentMeta",
    `Model: ${result?.model || "n/a"} · ${result?.elapsed_ms ?? "-"} ms`,
  );
  card.append(heading, output, metadata);
  return card;
}

function renderAgents(workflow) {
  agentGrid.replaceChildren(
    agentCard("Planner", workflow.planner_result, "plan"),
    agentCard("Worker", workflow.worker_result, "output"),
    agentCard("Reviewer", workflow.reviewer_result, "review"),
  );
}

function renderEvidence(workflow) {
  evidenceList.replaceChildren();
  const evidence = Array.isArray(workflow.request?.evidence) ? workflow.request.evidence : [];
  if (!evidence.length) {
    evidenceList.append(textElement("p", "ragResultNote", "No evidence was recorded for this workflow."));
    return;
  }

  evidence.forEach((item) => {
    const card = document.createElement("article");
    card.className = "multiAgentEvidenceCard";
    const source = item.source || {};
    const data = document.createElement("pre");
    data.textContent = JSON.stringify(item.data ?? {}, null, 2);
    card.append(
      textElement("h4", "", item.evidence_id || "Catalogue evidence"),
      textElement("p", "multiAgentEvidenceSource", `${source.service || "unknown service"} · ${source.endpoint || "unknown endpoint"}`),
      textElement("p", "multiAgentEvidenceSource", `Retrieved ${formatDate(source.retrieved_at)}`),
      data,
    );
    evidenceList.append(card);
  });
}

function humanDecisionLabel(decision) {
  return {
    accept: "Accepted",
    partially_accept: "Partially accepted",
    reject: "Rejected",
  }[decision] || String(decision || "Reviewed");
}

function renderHumanReview(workflow) {
  const review = workflow.human_review;
  reviewPanel.hidden = false;
  if (review && typeof review === "object") {
    reviewForm.hidden = true;
    reviewSummary.hidden = false;
    reviewSummary.replaceChildren(
      textElement("strong", "", humanDecisionLabel(review.decision)),
      textElement("p", "", review.reason || "No reason recorded."),
      textElement("small", "", `Reviewed by ${review.reviewed_by || "unknown reviewer"} · ${formatDate(review.reviewed_at)}`),
    );
  } else {
    reviewSummary.hidden = true;
    reviewSummary.replaceChildren();
    reviewForm.hidden = false;
  }
}

function statusClass(status) {
  if (["accepted", "partially_accepted", "awaiting_human_review", "completed"].includes(status)) {
    return "mcpResultStatus--success";
  }
  return "mcpResultStatus--error";
}

function renderWorkflow(workflow, { scroll = true } = {}) {
  activeWorkflowId = workflow.workflow_id;
  resultSection.hidden = false;
  resultTitle.textContent = workflow.request?.user_request || "Multi-Agent workflow";
  resultStatus.textContent = String(workflow.status || "unknown").replaceAll("_", " ");
  resultStatus.className = `mcpResultStatus ${statusClass(workflow.status)}`;
  workflowIdOutput.textContent = workflow.workflow_id || "-";
  workflowFeatureOutput.textContent = workflow.request?.feature || "-";
  workflowTimeOutput.textContent = formatDate(workflow.timestamp);
  renderAgents(workflow);
  renderEvidence(workflow);
  renderHumanReview(workflow);
  rawOutput.textContent = JSON.stringify(workflow, null, 2);
  if (scroll) resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderWorkflowError(title, error) {
  activeWorkflowId = null;
  resultSection.hidden = false;
  resultTitle.textContent = title;
  resultStatus.textContent = "Request failed";
  resultStatus.className = "mcpResultStatus mcpResultStatus--error";
  workflowIdOutput.textContent = "-";
  workflowFeatureOutput.textContent = "product_catalogue";
  workflowTimeOutput.textContent = "-";
  agentGrid.replaceChildren(textElement("p", "multiAgentError", error.message));
  evidenceList.replaceChildren();
  reviewPanel.hidden = true;
  rawOutput.textContent = JSON.stringify(error.payload || { error: error.message }, null, 2);
  resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function loadWorkflow(workflowId) {
  try {
    const workflow = await requestJson(`${MULTI_AGENT_WORKFLOWS_URL}/${encodeURIComponent(workflowId)}`);
    renderWorkflow(workflow);
  } catch (error) {
    renderWorkflowError("Unable to load workflow", error);
  }
}

function historyCard(workflow) {
  const card = document.createElement("article");
  card.className = "multiAgentHistoryCard";
  const content = document.createElement("div");
  content.append(
    textElement("strong", "", workflow.request?.user_request || "Untitled catalogue workflow"),
    textElement("p", "", `${formatDate(workflow.timestamp)} · ${String(workflow.status || "unknown").replaceAll("_", " ")}`),
    textElement("small", "", workflow.workflow_id || "No workflow ID"),
  );
  const button = textElement("button", "mcpSecondaryButton", "View details");
  button.type = "button";
  button.addEventListener("click", () => loadWorkflow(workflow.workflow_id));
  card.append(content, button);
  return card;
}

async function loadHistory() {
  refreshHistoryButton.disabled = true;
  refreshHistoryButton.textContent = "Loading...";
  historyMessage.textContent = "Loading Product Catalogue workflows...";
  historyList.replaceChildren();
  try {
    const payload = await requestJson(MULTI_AGENT_WORKFLOWS_URL);
    const workflows = Array.isArray(payload.workflows) ? [...payload.workflows].reverse() : [];
    historyMessage.textContent = workflows.length
      ? `${workflows.length} Product Catalogue workflow${workflows.length === 1 ? "" : "s"} recorded.`
      : "No Product Catalogue workflows have been recorded yet.";
    historyList.replaceChildren(...workflows.map(historyCard));
  } catch (error) {
    historyMessage.textContent = error.status === 401
      ? "Sign in to view protected workflow history."
      : `Workflow history could not be loaded: ${error.message}`;
  } finally {
    refreshHistoryButton.disabled = false;
    refreshHistoryButton.textContent = "Refresh history";
  }
}

workflowForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(workflowForm);
  const question = String(formData.get("question") || "").trim();
  const productIdText = String(formData.get("product_id") || "").trim();
  const body = { question };
  if (productIdText) body.product_id = Number(productIdText);

  runWorkflowButton.disabled = true;
  runWorkflowButton.textContent = "Running agents...";
  try {
    const workflow = await requestJson(
      MULTI_AGENT_WORKFLOWS_URL,
      jsonRequest("POST", body),
    );
    renderWorkflow(workflow);
    await loadHistory();
  } catch (error) {
    renderWorkflowError("Multi-Agent workflow failed", error);
  } finally {
    runWorkflowButton.disabled = false;
    runWorkflowButton.textContent = "Run coordinated review";
  }
});

loadLatestButton.addEventListener("click", async () => {
  loadLatestButton.disabled = true;
  loadLatestButton.textContent = "Loading...";
  try {
    const workflow = await requestJson(`${MULTI_AGENT_WORKFLOWS_URL}/latest`);
    renderWorkflow(workflow);
  } catch (error) {
    renderWorkflowError("Latest workflow unavailable", error);
  } finally {
    loadLatestButton.disabled = false;
    loadLatestButton.textContent = "Get latest workflow";
  }
});

reviewForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!activeWorkflowId) {
    renderWorkflowError("Human review failed", new Error("Load a workflow before submitting a decision."));
    return;
  }
  const formData = new FormData(reviewForm);
  const body = {
    decision: String(formData.get("decision") || ""),
    reason: String(formData.get("reason") || "").trim(),
  };
  submitReviewButton.disabled = true;
  submitReviewButton.textContent = "Submitting...";
  try {
    const workflow = await requestJson(
      `${MULTI_AGENT_WORKFLOWS_URL}/${encodeURIComponent(activeWorkflowId)}/review`,
      jsonRequest("POST", body),
    );
    renderWorkflow(workflow, { scroll: false });
    reviewForm.reset();
    await loadHistory();
  } catch (error) {
    window.alert(`Human review could not be submitted: ${error.message}`);
  } finally {
    submitReviewButton.disabled = false;
    submitReviewButton.textContent = "Submit human decision";
  }
});

refreshStatusButton.addEventListener("click", loadStatus);
refreshHistoryButton.addEventListener("click", loadHistory);

loadStatus();
loadProducts();
loadHistory();
