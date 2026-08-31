"use strict";

const LOGIN_URL = (() => {
  const login = new URL("http://localhost:8003/index.html");
  login.searchParams.set("return_url", "http://localhost:8005/staff.html");
  return login.href;
})();
const CUSTOMER_URL = "customer.html";

const CATEGORY_VALUES = [
  "unclassified", "order", "return", "payment", "product", "delivery", "account", "other",
];
const PRIORITY_VALUES = ["unclassified", "low", "medium", "high", "urgent"];
const STATUS_VALUES = ["needs_triage", "open", "pending", "solved"];

const state = {
  page: document.body?.dataset.adminPage || "queue",
  ticketId: null,
  ticket: null,
  analysis: null,
};

class SupportApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = "SupportApiError";
    this.status = status;
    this.payload = payload;
  }
}

function byId(id) {
  return document.getElementById(id);
}

function text(value, fallback = "—") {
  if (value === null || value === undefined || String(value).trim() === "") {
    return fallback;
  }
  return String(value);
}

function trimmed(value) {
  return value === null || value === undefined ? "" : String(value).trim();
}

function createElement(tagName, className, content) {
  const element = document.createElement(tagName);
  if (className) {
    element.className = className;
  }
  if (content !== undefined) {
    element.textContent = content;
  }
  return element;
}

function payloadMessage(payload, fallback) {
  if (!payload || typeof payload !== "object") {
    return fallback;
  }
  return text(payload.error || payload.message, fallback);
}

async function requestJSON(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Accept", "application/json");
  if (options.body !== undefined && options.body !== null) {
    headers.set("Content-Type", "application/json");
  }

  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers,
      credentials: "include",
    });
  } catch (error) {
    throw new SupportApiError("The support service could not be reached.", 0, null);
  }

  let payload = null;
  if (response.status !== 204) {
    const responseText = await response.text();
    if (responseText) {
      try {
        payload = JSON.parse(responseText);
      } catch (error) {
        payload = null;
      }
    }
  }

  if (!response.ok) {
    const fallback = response.status === 503
      ? "The support service is temporarily unavailable."
      : "The support request could not be completed.";
    throw new SupportApiError(payloadMessage(payload, fallback), response.status, payload);
  }

  return payload || {};
}

function extractUser(payload) {
  return payload?.user || null;
}

function extractTickets(payload) {
  return Array.isArray(payload?.tickets) ? payload.tickets : [];
}

function extractTicket(payload) {
  return payload?.ticket && typeof payload.ticket === "object" ? payload.ticket : null;
}

function ticketId(ticket) {
  return trimmed(ticket?.id);
}

function customerName(ticket) {
  return trimmed(ticket?.customer_name_snapshot) || "Unknown customer";
}

function customerEmail(ticket) {
  return trimmed(ticket?.customer_email_snapshot);
}

function ticketAssignee(ticket) {
  return trimmed(ticket?.assigned_to);
}

function ticketCategory(ticket) {
  return (trimmed(ticket?.category) || "unclassified").toLowerCase();
}

function ticketPriority(ticket) {
  return (trimmed(ticket?.priority) || "unclassified").toLowerCase();
}

function ticketStatus(ticket) {
  return (trimmed(ticket?.status) || "needs_triage").toLowerCase();
}

function label(value, fallback = "Unclassified") {
  const source = trimmed(value).replace(/[_-]+/g, " ");
  if (!source) {
    return fallback;
  }
  return source.replace(/\b\w/g, (character) => character.toUpperCase());
}

function statusClass(value) {
  const normalized = ticketStatus({ status: value });
  return STATUS_VALUES.includes(normalized) ? normalized : "unknown";
}

function formatTimestamp(value) {
  const raw = trimmed(value);
  if (!raw) {
    return "Not available";
  }
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) {
    return raw;
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

function setText(id, value, fallback = "—") {
  const element = byId(id);
  if (element) {
    element.textContent = text(value, fallback);
  }
}

function setHidden(id, hidden) {
  const element = byId(id);
  if (element) {
    element.hidden = hidden;
  }
}

function redirectTo(url) {
  try {
    window.location.replace(url);
  } catch (error) {
    // Some test DOMs do not implement navigation. The production browser does.
  }
}

function showBootState(title, message, tone = "loading", actionLabel, action) {
  const region = byId("admin-boot-state");
  if (!region) {
    return;
  }
  region.className = `adminState adminState--${tone}`;
  region.replaceChildren();
  region.appendChild(createElement("strong", "", title));
  region.appendChild(createElement("p", "", message));
  if (actionLabel && action) {
    const button = createElement("button", "button button--secondary", actionLabel);
    button.type = "button";
    button.addEventListener("click", action);
    region.appendChild(button);
  }
}

function showWorkspace(show) {
  const workspace = byId("admin-workspace");
  if (workspace) {
    workspace.hidden = !show;
  }
  setHidden("admin-boot-state", show);
}

function stateRegion(id, title, message, tone = "loading", actionLabel, action) {
  const region = byId(id);
  if (!region) {
    return;
  }
  region.className = `adminState adminState--${tone}`;
  region.setAttribute("role", tone === "error" ? "alert" : "status");
  region.replaceChildren();
  region.appendChild(createElement("strong", "", title));
  region.appendChild(createElement("p", "", message));
  if (actionLabel && action) {
    const button = createElement("button", "button button--secondary", actionLabel);
    button.type = "button";
    button.addEventListener("click", action);
    region.appendChild(button);
  }
  region.hidden = false;
}

function feedback(id, message, tone = "success") {
  const region = byId(id);
  if (!region) {
    return;
  }
  region.className = `adminFeedback adminFeedback--${tone}`;
  region.setAttribute("role", tone === "error" ? "alert" : "status");
  region.textContent = message;
  region.hidden = false;
}

function clearFeedback(id) {
  const region = byId(id);
  if (region) {
    region.textContent = "";
    region.hidden = true;
  }
}

function handleRequestError(error, regionId, retryAction) {
  if (error.status === 401) {
    stateRegion(regionId, "Session expired", "Your staff session has expired. Redirecting to sign in…", "error");
    redirectTo(LOGIN_URL);
    return;
  }
  if (error.status === 403) {
    stateRegion(regionId, "Staff access required", "This workspace is restricted to administrators. Returning to customer support…", "error");
    redirectTo(CUSTOMER_URL);
    return;
  }
  const title = error.status === 503 || error.status === 0
    ? "Support service unavailable"
    : "We could not complete that request";
  stateRegion(regionId, title, error.message, "error", retryAction ? "Try again" : undefined, retryAction);
}

function queryParamsFromForm(form) {
  const params = new URLSearchParams();
  const formData = new FormData(form);
  for (const [key, value] of formData.entries()) {
    const cleanValue = trimmed(value);
    if (cleanValue) {
      params.set(key, cleanValue);
    }
  }
  return params;
}

function renderQueueSummary(payload, tickets) {
  const region = byId("queue-summary");
  if (!region) {
    return;
  }
  region.replaceChildren();
  const counts = payload?.status_counts || {};
  const values = [
    ["Open", counts.open],
    ["Pending", counts.pending],
    ["Solved", counts.solved],
  ];
  const fragment = document.createDocumentFragment();
  values.forEach(([name, count]) => {
    const item = createElement("span", "adminSummaryPill");
    item.appendChild(createElement("strong", "", text(count, "0")));
    item.appendChild(document.createTextNode(` ${name}`));
    fragment.appendChild(item);
  });
  if (!values.some(([, count]) => count !== undefined)) {
    const item = createElement("span", "adminSummaryPill", `${tickets.length} matching`);
    fragment.appendChild(item);
  }
  region.appendChild(fragment);
}

function renderTicketRow(ticket) {
  const id = ticketId(ticket);
  const item = createElement("li", "adminTicketListItem");
  const link = createElement("a", "adminTicketRow");
  link.href = `staff-ticket.html?ticket=${encodeURIComponent(id)}`;
  link.setAttribute("aria-label", `Open ticket ${text(id, "without number")}: ${text(ticket?.subject, "Untitled ticket")}`);

  const primary = createElement("div", "adminTicketPrimary");
  primary.appendChild(createElement("strong", "", `#${text(id, "?")} · ${text(ticket?.subject, "Untitled ticket")}`));
  const meta = createElement("span", "adminTicketMeta", `${customerName(ticket)}${customerEmail(ticket) ? ` · ${customerEmail(ticket)}` : ""}`);
  primary.appendChild(meta);

  const category = createElement("span", "adminTicketCell", label(ticketCategory(ticket)));
  category.dataset.label = "Category";
  const assignee = createElement("span", "adminTicketCell", ticketAssignee(ticket) || "Unassigned");
  assignee.dataset.label = "Assignee";
  const updated = createElement("time", "adminTicketCell", formatTimestamp(ticket?.updated_at || ticket?.created_at));
  updated.dataset.label = "Updated";
  if (ticket?.updated_at || ticket?.created_at) {
    updated.dateTime = text(ticket.updated_at || ticket.created_at, "");
  }
  const badge = createElement("span", `adminStatusBadge adminStatusBadge--${statusClass(ticket?.status)}`, label(ticket?.status, "Open"));
  badge.dataset.label = "Status";

  link.appendChild(primary);
  link.appendChild(category);
  link.appendChild(assignee);
  link.appendChild(updated);
  link.appendChild(badge);
  item.appendChild(link);
  return item;
}

async function loadQueue() {
  const form = byId("queue-filters");
  const params = form ? queryParamsFromForm(form) : new URLSearchParams();
  const query = params.toString();
  const path = `/api/support/admin/tickets${query ? `?${query}` : ""}`;
  const loading = byId("queue-loading");
  if (loading) {
    loading.hidden = false;
  }
  setHidden("queue-state", false);
  stateRegion("queue-state", "Loading tickets…", "Refreshing the administrator queue.", "loading");
  setHidden("ticket-list", true);
  try {
    const payload = await requestJSON(path);
    const tickets = extractTickets(payload);
    const list = byId("ticket-list");
    if (list) {
      list.replaceChildren();
      const fragment = document.createDocumentFragment();
      tickets.forEach((ticket) => fragment.appendChild(renderTicketRow(ticket)));
      list.appendChild(fragment);
      list.hidden = tickets.length === 0;
    }
    setText("queue-count", `${text(payload?.count, String(tickets.length))} matching`);
    renderQueueSummary(payload, tickets);
    if (tickets.length === 0) {
      stateRegion("queue-state", "No tickets found", "Try a different ticket number, search phrase, or filter combination.", "empty");
    } else {
      setHidden("queue-state", true);
    }
  } catch (error) {
    handleRequestError(error, "queue-state", loadQueue);
  } finally {
    if (loading) {
      loading.hidden = true;
    }
  }
}

function bindQueue() {
  const form = byId("queue-filters");
  if (!form || form.dataset.bound === "true") {
    return;
  }
  form.dataset.bound = "true";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    loadQueue();
  });
  form.addEventListener("reset", () => {
    window.setTimeout(loadQueue, 0);
  });
}

function setSelectValue(id, value, allowedValues) {
  const select = byId(id);
  if (!select) {
    return;
  }
  const normalized = trimmed(value).toLowerCase() || allowedValues[0];
  if (!Array.from(select.options).some((option) => option.value === normalized)) {
    const option = createElement("option", "", label(normalized));
    option.value = normalized;
    select.appendChild(option);
  }
  select.value = normalized;
}

function safeEmailHref(email) {
  const value = trimmed(email);
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
    return "";
  }
  return `mailto:${encodeURIComponent(value)}`;
}

function renderMessages(ticket) {
  const list = byId("message-thread");
  if (!list) {
    return;
  }
  list.replaceChildren();
  const messages = Array.isArray(ticket?.messages) ? ticket.messages : [];
  setText("message-count", `${messages.length} message${messages.length === 1 ? "" : "s"}`);
  if (!messages.length) {
    list.appendChild(createElement("li", "adminMessageEmpty", "No messages have been added to this ticket."));
    return;
  }
  const fragment = document.createDocumentFragment();
  messages.forEach((message) => {
    const sender = trimmed(message?.sender_role).toLowerCase() === "staff" ? "staff" : "customer";
    const item = createElement("li", `adminMessage adminMessage--${sender}`);
    const meta = createElement("div", "adminMessageMeta");
    meta.appendChild(createElement("strong", "", text(message?.author_name, sender === "staff" ? "Support staff" : "Customer")));
    meta.appendChild(createElement("span", "", label(sender)));
    const timestamp = createElement("time", "", formatTimestamp(message?.created_at));
    if (message?.created_at) {
      timestamp.dateTime = text(message.created_at, "");
    }
    meta.appendChild(timestamp);
    item.appendChild(meta);
    item.appendChild(createElement("p", "", text(message?.message, "No message text available.")));
    fragment.appendChild(item);
  });
  list.appendChild(fragment);
}

function renderCustomerEmail(email) {
  const region = byId("ticket-customer-email");
  if (!region) {
    return;
  }
  region.replaceChildren();
  const value = trimmed(email);
  if (!value) {
    region.textContent = "Not provided";
    return;
  }
  const href = safeEmailHref(value);
  if (!href) {
    region.textContent = value;
    return;
  }
  const link = createElement("a", "", value);
  link.href = href;
  region.appendChild(link);
}

function renderTicket(ticket) {
  state.ticket = ticket;
  const id = ticketId(ticket);
  setText("ticket-number", `Ticket #${text(id, "?")}`);
  setText("ticket-subject", ticket?.subject, "Untitled ticket");
  setText("ticket-customer-name", customerName(ticket));
  renderCustomerEmail(customerEmail(ticket));
  setText("ticket-created", formatTimestamp(ticket?.created_at));
  setText("ticket-updated", formatTimestamp(ticket?.updated_at));

  const status = byId("ticket-status");
  if (status) {
    status.className = `adminStatusBadge adminStatusBadge--${statusClass(ticket?.status)}`;
    status.textContent = label(ticket?.status, "Open");
  }
  setSelectValue("ticket-category", ticketCategory(ticket), CATEGORY_VALUES);
  setSelectValue("ticket-priority", ticketPriority(ticket), PRIORITY_VALUES);
  setSelectValue("ticket-status-select", ticketStatus(ticket), STATUS_VALUES);
  const assignee = byId("ticket-assignee");
  if (assignee) {
    assignee.value = ticketAssignee(ticket);
  }
  renderMessages(ticket);
  setHidden("ticket-detail-state", true);
  setHidden("ticket-detail-content", false);
}

function triagePayload() {
  return {
    category: trimmed(byId("ticket-category")?.value).toLowerCase(),
    priority: trimmed(byId("ticket-priority")?.value).toLowerCase(),
    status: trimmed(byId("ticket-status-select")?.value).toLowerCase(),
    assigned_to: trimmed(byId("ticket-assignee")?.value),
  };
}

function hasTicket(value) {
  return value && ticketId(value) !== "";
}

async function saveTriage(event) {
  event.preventDefault();
  clearFeedback("triage-feedback");
  const values = triagePayload();
  if (!CATEGORY_VALUES.includes(values.category)) {
    feedback("triage-feedback", "Select a valid category.", "error");
    return;
  }
  if (!PRIORITY_VALUES.includes(values.priority)) {
    feedback("triage-feedback", "Select a valid priority.", "error");
    return;
  }
  if (!STATUS_VALUES.includes(values.status)) {
    feedback("triage-feedback", "Select a valid status.", "error");
    return;
  }
  const button = byId("save-triage-button");
  const loading = byId("triage-loading");
  if (button) button.disabled = true;
  if (loading) loading.hidden = false;
  try {
    const payload = await requestJSON(`/api/support/admin/tickets/${encodeURIComponent(state.ticketId)}`, {
      method: "PUT",
      body: JSON.stringify(values),
    });
    const updated = extractTicket(payload);
    if (hasTicket(updated)) {
      renderTicket(updated);
    } else if (state.ticket) {
      renderTicket({ ...state.ticket, ...values });
    }
    feedback("triage-feedback", "Ticket triage updated.");
  } catch (error) {
    if (error.status === 401 || error.status === 403) {
      handleRequestError(error, "ticket-detail-state");
    } else {
      feedback("triage-feedback", error.message, "error");
    }
  } finally {
    if (button) button.disabled = false;
    if (loading) loading.hidden = true;
  }
}

async function sendReply(event) {
  event.preventDefault();
  clearFeedback("reply-feedback");
  const textarea = byId("staff-reply");
  const message = trimmed(textarea?.value);
  if (!message) {
    feedback("reply-feedback", "Message is required.", "error");
    textarea?.focus();
    return;
  }
  if (message.length > 2000) {
    feedback("reply-feedback", "Message must be 2000 characters or fewer.", "error");
    textarea?.focus();
    return;
  }
  const button = byId("reply-button");
  const loading = byId("reply-loading");
  if (button) button.disabled = true;
  if (loading) loading.hidden = false;
  try {
    const payload = await requestJSON(`/api/support/admin/tickets/${encodeURIComponent(state.ticketId)}/messages`, {
      method: "POST",
      body: JSON.stringify({ message }),
    });
    const returnedTicket = extractTicket(payload);
    if (hasTicket(returnedTicket)) {
      renderTicket(returnedTicket);
    } else {
      await loadTicket();
    }
    if (textarea) textarea.value = "";
    feedback("reply-feedback", "Reply sent to the customer.");
  } catch (error) {
    if (error.status === 401 || error.status === 403) {
      handleRequestError(error, "ticket-detail-state");
    } else {
      feedback("reply-feedback", error.message, "error");
    }
  } finally {
    if (button) button.disabled = false;
    if (loading) loading.hidden = true;
  }
}

function normaliseAnalysis(payload) {
  const raw = payload?.analysis;
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const analysis = {
    summary: trimmed(raw.summary),
    category: trimmed(raw.category).toLowerCase(),
    sentiment: trimmed(raw.sentiment).toLowerCase(),
    priority: trimmed(raw.priority).toLowerCase(),
    draftResponse: trimmed(raw.draft_response),
  };
  if (!analysis.summary || !CATEGORY_VALUES.includes(analysis.category)
    || !PRIORITY_VALUES.includes(analysis.priority) || !analysis.draftResponse) {
    return null;
  }
  return {
    ...analysis,
    model: text(payload?.model, "Support AI"),
    workflow: payload?.workflow || {},
  };
}

function workflowStep(workflow, key, fallback) {
  return text(workflow?.[key], fallback);
}

function renderAnalysis(analysis) {
  const region = byId("ai-result");
  if (!region) {
    return;
  }
  region.replaceChildren();
  const article = createElement("article", "adminAiResult");
  const header = createElement("div", "adminAiResultHeader");
  header.appendChild(createElement("h3", "", "Suggestions (read-only)"));
  header.appendChild(createElement("span", "adminAiModel", analysis.model));
  article.appendChild(header);
  article.appendChild(createElement("p", "adminAiSuggestionNotice", "Review the analysis below. Applying it changes only category and priority after an explicit administrator action."));

  const facts = createElement("dl", "adminAiFacts");
  [["Suggested category", label(analysis.category)], ["Suggested priority", label(analysis.priority)], ["Sentiment", label(analysis.sentiment)]].forEach(([name, value]) => {
    const wrapper = createElement("div", "");
    wrapper.appendChild(createElement("dt", "", name));
    wrapper.appendChild(createElement("dd", "", value));
    facts.appendChild(wrapper);
  });
  article.appendChild(facts);

  const summarySection = createElement("section", "adminAiSection");
  summarySection.appendChild(createElement("h4", "", "Summary"));
  summarySection.appendChild(createElement("p", "", analysis.summary));
  article.appendChild(summarySection);

  const draftSection = createElement("section", "adminAiSection");
  draftSection.appendChild(createElement("h4", "", "Draft response for review"));
  draftSection.appendChild(createElement("p", "adminAiDraft", analysis.draftResponse));
  article.appendChild(draftSection);

  const workflow = createElement("ol", "adminWorkflow");
  [["Plan", workflowStep(analysis.workflow, "plan", "Prepare a minimal ticket context.")],
    ["Act", workflowStep(analysis.workflow, "act", "Request a structured advisory analysis.")],
    ["Observe", workflowStep(analysis.workflow, "observe", "Validate the response and classifications.")],
    ["Adapt", workflowStep(analysis.workflow, "adapt", "Keep the result for staff review.")]].forEach(([name, value]) => {
    const item = createElement("li", "");
    item.appendChild(createElement("strong", "", name));
    item.appendChild(createElement("span", "", value));
    workflow.appendChild(item);
  });
  article.appendChild(workflow);
  region.appendChild(article);
  region.hidden = false;
  const apply = byId("apply-ai-suggestions");
  if (apply) {
    apply.hidden = false;
    apply.disabled = false;
    apply.textContent = "Apply category & priority suggestions";
  }
}

async function analyseTicket() {
  const button = byId("analyse-ticket-button");
  const result = byId("ai-result");
  const aiState = byId("ai-state");
  if (button) button.disabled = true;
  if (result) {
    result.replaceChildren();
    result.hidden = true;
  }
  state.analysis = null;
  setHidden("apply-ai-suggestions", true);
  if (aiState) {
    aiState.hidden = false;
    aiState.className = "adminState adminState--loading";
    aiState.replaceChildren(createElement("strong", "", "Analysing ticket…"), createElement("p", "", "Preparing a read-only suggestion."));
  }
  try {
    const payload = await requestJSON(`/api/support/admin/tickets/${encodeURIComponent(state.ticketId)}/ai-analysis`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    const analysis = normaliseAnalysis(payload);
    if (!analysis) {
      throw new SupportApiError("The AI assistant returned an incomplete suggestion.", 502, payload);
    }
    state.analysis = analysis;
    renderAnalysis(analysis);
    if (aiState) aiState.hidden = true;
  } catch (error) {
    if (error.status === 401 || error.status === 403) {
      handleRequestError(error, "ticket-detail-state");
    } else if (aiState) {
      aiState.hidden = false;
      aiState.className = "adminState adminState--error";
      aiState.replaceChildren(createElement("strong", "", "AI analysis unavailable"), createElement("p", "", error.message));
    }
  } finally {
    if (button) button.disabled = false;
  }
}

async function applySuggestions() {
  if (!state.analysis || !state.ticket) {
    return;
  }
  const button = byId("apply-ai-suggestions");
  const aiState = byId("ai-state");
  if (button) button.disabled = true;
  if (aiState) {
    aiState.hidden = false;
    aiState.className = "adminState adminState--loading";
    aiState.replaceChildren(createElement("strong", "", "Applying suggestions…"), createElement("p", "", "Saving the reviewed category and priority."));
  }
  const values = {
    apply_ai_suggestions: {
      category: state.analysis.category,
      priority: state.analysis.priority,
    },
  };
  try {
    const payload = await requestJSON(`/api/support/admin/tickets/${encodeURIComponent(state.ticketId)}`, {
      method: "PUT",
      body: JSON.stringify(values),
    });
    const updated = extractTicket(payload);
    renderTicket(hasTicket(updated) ? updated : {
      ...state.ticket,
      category: state.analysis.category,
      priority: state.analysis.priority,
    });
    if (aiState) {
      aiState.className = "adminState adminState--success";
      aiState.replaceChildren(createElement("strong", "", "Suggestions applied"), createElement("p", "", "Category and priority were updated after your explicit approval."));
    }
    if (button) {
      button.textContent = "Suggestions applied";
      button.disabled = true;
    }
    feedback("detail-feedback", "AI category and priority suggestions applied.");
  } catch (error) {
    if (error.status === 401 || error.status === 403) {
      handleRequestError(error, "ticket-detail-state");
    } else if (aiState) {
      aiState.className = "adminState adminState--error";
      aiState.replaceChildren(createElement("strong", "", "Suggestions were not applied"), createElement("p", "", error.message));
    }
    if (button) button.disabled = false;
  }
}

async function deleteTicket() {
  const id = text(state.ticketId, "this ticket");
  const confirmed = window.confirm(`Delete ticket #${id} and its entire conversation? This cannot be undone.`);
  if (!confirmed) {
    return;
  }
  const button = byId("delete-ticket-button");
  const loading = byId("delete-loading");
  if (button) button.disabled = true;
  if (loading) loading.hidden = false;
  clearFeedback("delete-feedback");
  try {
    await requestJSON(`/api/support/admin/tickets/${encodeURIComponent(state.ticketId)}`, { method: "DELETE" });
    setHidden("ticket-detail-content", true);
    stateRegion("ticket-detail-state", `Ticket #${id} deleted`, "The ticket and its conversation were permanently removed.", "success", "Back to queue", () => {
      window.location.href = "staff.html";
    });
  } catch (error) {
    if (error.status === 401 || error.status === 403) {
      handleRequestError(error, "ticket-detail-state");
    } else {
      feedback("delete-feedback", error.message, "error");
    }
  } finally {
    if (button) button.disabled = false;
    if (loading) loading.hidden = true;
  }
}

async function loadTicket() {
  setHidden("ticket-detail-content", true);
  stateRegion("ticket-detail-state", "Loading ticket…", "Retrieving the selected conversation.", "loading");
  try {
    const payload = await requestJSON(`/api/support/admin/tickets/${encodeURIComponent(state.ticketId)}`);
    const ticket = extractTicket(payload);
    if (!hasTicket(ticket)) {
      throw new SupportApiError("The support service returned no ticket data.", 502, payload);
    }
    renderTicket(ticket);
    if (state.analysis) {
      renderAnalysis(state.analysis);
    }
  } catch (error) {
    handleRequestError(error, "ticket-detail-state", loadTicket);
  }
}

function bindDetail() {
  const replyForm = byId("reply-form");
  if (replyForm && replyForm.dataset.bound !== "true") {
    replyForm.dataset.bound = "true";
    replyForm.addEventListener("submit", sendReply);
  }
  const triageForm = byId("triage-form");
  if (triageForm && triageForm.dataset.bound !== "true") {
    triageForm.dataset.bound = "true";
    triageForm.addEventListener("submit", saveTriage);
  }
  const analyseButton = byId("analyse-ticket-button");
  if (analyseButton && analyseButton.dataset.bound !== "true") {
    analyseButton.dataset.bound = "true";
    analyseButton.addEventListener("click", analyseTicket);
  }
  const deleteButton = byId("delete-ticket-button");
  if (deleteButton && deleteButton.dataset.bound !== "true") {
    deleteButton.dataset.bound = "true";
    deleteButton.addEventListener("click", deleteTicket);
  }
  const applyButton = byId("apply-ai-suggestions");
  if (applyButton && applyButton.dataset.bound !== "true") {
    applyButton.dataset.bound = "true";
    applyButton.addEventListener("click", applySuggestions);
  }
}

async function startAdminPage() {
  showWorkspace(false);
  showBootState("Checking staff access…", "Verifying your signed-in session.", "loading");
  try {
    const payload = await requestJSON("/api/support/customer/session");
    const user = extractUser(payload);
    if (payload?.authenticated === false || !user) {
      redirectTo(LOGIN_URL);
      return;
    }
    if (trimmed(user.role).toLowerCase() !== "admin") {
      redirectTo(CUSTOMER_URL);
      return;
    }
    setText("admin-user-context", `Signed in as ${trimmed(user.full_name) || "administrator"}.`);
    showWorkspace(true);
    if (state.page === "detail") {
      const requestedId = new URLSearchParams(window.location.search).get("ticket") || "";
      if (!/^\d+$/.test(requestedId)) {
        stateRegion("ticket-detail-state", "Ticket number required", "Open a ticket from the staff queue to view its conversation.", "empty", "Back to queue", () => {
          window.location.href = "staff.html";
        });
        return;
      }
      state.ticketId = requestedId;
      bindDetail();
      await loadTicket();
    } else {
      bindQueue();
      await loadQueue();
    }
  } catch (error) {
    if (error.status === 401) {
      redirectTo(LOGIN_URL);
      return;
    }
    if (error.status === 403) {
      redirectTo(CUSTOMER_URL);
      return;
    }
    showBootState(
      error.status === 503 || error.status === 0 ? "Support service unavailable" : "Staff access could not be verified",
      error.message,
      "error",
      "Try again",
      startAdminPage,
    );
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", startAdminPage, { once: true });
} else {
  startAdminPage();
}
