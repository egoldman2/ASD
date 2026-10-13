(function () {
  "use strict";

  const API_ORIGIN = "http://localhost:8102";
  const BASE_API = `${API_ORIGIN}/api/inventory/multi-agent`;

  const statusLine = document.getElementById("maStatusLine");
  const form = document.getElementById("maForm");
  const questionInput = document.getElementById("maQuestion");
  const productIdInput = document.getElementById("maProductId");
  const runButton = document.getElementById("maRunButton");
  const workflowLine = document.getElementById("maWorkflowLine");
  const planOutput = document.getElementById("maPlan");
  const workerOutput = document.getElementById("maWorker");
  const reviewerOutput = document.getElementById("maReviewer");
  const reviewForm = document.getElementById("maReviewForm");
  const decisionSelect = document.getElementById("maDecision");
  const reasonInput = document.getElementById("maReason");
  const reviewButton = document.getElementById("maReviewButton");
  const reviewLine = document.getElementById("maReviewLine");
  const jsonBlock = document.getElementById("maJson");

  let currentWorkflowId = null;

  async function send(method, url, body) {
    const options = {
      method,
      headers: { Accept: "application/json" },
      credentials: "include",
    };
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    const response = await fetch(url, options);
    const payload = await response.json();
    return { status: response.status, payload };
  }

  function errorText(status, payload) {
    const err = (payload && payload.error) || {};
    return `[HTTP ${status}] ${err.code || "ERROR"}: ${err.message || "Request failed."}`;
  }

  function clearResult() {
    workflowLine.textContent = "";
    planOutput.value = "";
    workerOutput.value = "";
    reviewerOutput.value = "";
    reviewLine.textContent = "";
    jsonBlock.textContent = "";
    reviewForm.hidden = true;
    currentWorkflowId = null;
  }

  function renderWorkflow(workflow) {
    currentWorkflowId = workflow.workflow_id;
    workflowLine.textContent = `Workflow ${workflow.workflow_id}: ${workflow.status}`;
    planOutput.value = (workflow.planner_result && workflow.planner_result.plan) || "";
    workerOutput.value = (workflow.worker_result && workflow.worker_result.output) || "";
    reviewerOutput.value = (workflow.reviewer_result && workflow.reviewer_result.review) || "";

    const human = workflow.human_review;
    if (human) {
      reviewLine.textContent =
        `Human review: ${human.decision} by ${human.reviewed_by} at ${human.reviewed_at}. Reason: ${human.reason}`;
    }
    reviewForm.hidden = workflow.status !== "awaiting_human_review";
    jsonBlock.textContent = JSON.stringify(workflow, null, 2);
  }

  async function refreshStatus() {
    try {
      const { payload } = await send("GET", `${BASE_API}/status`);
      if (!payload.enabled) {
        statusLine.textContent = "Multi-Agent is disabled in this environment.";
      } else if (!payload.available) {
        statusLine.textContent = "Multi-Agent server is unreachable right now.";
      } else {
        statusLine.textContent = `Multi-Agent connected: ${payload.service}.`;
      }
    } catch (err) {
      statusLine.textContent = "Could not check Multi-Agent status.";
    }
  }

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();

    const question = questionInput.value.trim();
    if (!question) return;

    const requestBody = { question };
    const productId = productIdInput.value.trim();
    if (productId) requestBody.product_id = Number.parseInt(productId, 10);

    clearResult();
    runButton.disabled = true;
    workflowLine.textContent =
      "Running Planner → Worker → Reviewer. This can take several minutes...";

    try {
      const { status, payload } = await send("POST", `${BASE_API}/workflows`, requestBody);
      if (status === 201) {
        renderWorkflow(payload);
      } else {
        workflowLine.textContent = errorText(status, payload);
      }
    } catch (err) {
      workflowLine.textContent = "The Multi-Agent workflow is unavailable right now.";
      console.error("Multi-Agent workflow failed:", err);
    } finally {
      runButton.disabled = false;
    }
  });

  reviewForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!currentWorkflowId) return;

    const reason = reasonInput.value.trim();
    if (!reason) return;

    reviewButton.disabled = true;
    reviewLine.textContent = "Submitting review...";

    try {
      const { status, payload } = await send(
        "POST",
        `${BASE_API}/workflows/${encodeURIComponent(currentWorkflowId)}/review`,
        { decision: decisionSelect.value, reason }
      );
      if (status === 200) {
        renderWorkflow(payload);
      } else {
        reviewLine.textContent = errorText(status, payload);
      }
    } catch (err) {
      reviewLine.textContent = "Could not submit the review.";
      console.error("Human review failed:", err);
    } finally {
      reviewButton.disabled = false;
    }
  });

  document.addEventListener("DOMContentLoaded", refreshStatus);
})();