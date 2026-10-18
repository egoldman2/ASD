(function () {
  "use strict";

  const API_ORIGIN = "http://localhost:8102";
  const BASE_API = `${API_ORIGIN}/api/inventory/multi-agent`;

  const statusLine = document.getElementById("maStatusLine");
  const form = document.getElementById("maForm");
  const questionInput = document.getElementById("maQuestion");
  const productIdInput = document.getElementById("maProductId");
  const timeLimitLabel = document.getElementById("maTimeLimit");
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

  const POLL_INTERVAL_MS = 5000;
  const POLL_LIMIT_MINUTES = 150;
  const POLL_LIMIT_MS = POLL_LIMIT_MINUTES * 60 * 1000;

  let currentWorkflowId = null;

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function elapsedText(startMs) {
    const seconds = Math.floor((Date.now() - startMs) / 1000);
    return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, "0")}s`;
  }

  function showFailure(message, details) {
    workflowLine.textContent = `Workflow failed: ${message}`;
    workflowLine.style.color = "#b00020";
    workflowLine.style.fontWeight = "600";
    if (details !== undefined) {
      jsonBlock.textContent = "Failure details:\n" + JSON.stringify(details, null, 2);
    }
  }

  function clearFailureStyle() {
    workflowLine.style.color = "";
    workflowLine.style.fontWeight = "";
  }

  async function waitForJob(jobId) {
    const startMs = Date.now();
    while (Date.now() - startMs < POLL_LIMIT_MS) {
      await sleep(POLL_INTERVAL_MS);
      let result;
      try {
        result = await send("GET", `${BASE_API}/jobs/${encodeURIComponent(jobId)}`);
      } catch (err) {
        workflowLine.textContent =
          `Waiting for the agents (${elapsedText(startMs)})... retrying status check.`;
        continue;
      }
      const { status, payload } = result;
      if (status !== 200) {
        return { error: errorText(status, payload), details: payload, elapsed: elapsedText(startMs) };
      }
      if (payload.status === "completed") return { workflow: payload.workflow };
      if (payload.status === "failed") {
        return { error: errorText(502, payload), details: payload, elapsed: elapsedText(startMs) };
      }

      const stage = payload.status === "recovering"
        ? "Connection to the server dropped, waiting for the result in its history. " +
          "If the server terminal shows a 502, the run has failed"
        : "Running Planner → Worker → Reviewer";
      workflowLine.textContent = `${stage} (${elapsedText(startMs)})...`;
    }
    return {
      error: `Stopped waiting after ${POLL_LIMIT_MINUTES} minutes. Check the Multi-Agent server log.`,
      elapsed: elapsedText(startMs),
    };
  }

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
    clearFailureStyle();
    runButton.disabled = true;
    workflowLine.textContent =
      "Running Planner → Worker → Reviewer. This can take several minutes...";

    try {
      const { status, payload } = await send("POST", `${BASE_API}/workflows`, requestBody);
      if (status !== 202) {
        showFailure(errorText(status, payload), payload);
        return;
      }
      const outcome = await waitForJob(payload.job_id);
      if (outcome.workflow) {
        renderWorkflow(outcome.workflow);
      } else {
        showFailure(`${outcome.error} (after ${outcome.elapsed})`, outcome.details);
      }
    } catch (err) {
      showFailure(`could not reach the backend (${err && err.message ? err.message : err}).`);
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

  document.addEventListener("DOMContentLoaded", () => {
    if (timeLimitLabel) {
      timeLimitLabel.textContent = `Maximum wait: ${POLL_LIMIT_MINUTES} minutes per run.`;
    }
    refreshStatus();
  });
})();