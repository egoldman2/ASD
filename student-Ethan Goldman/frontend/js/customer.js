const LOGIN_PAGE_URL = "http://localhost:8003/index.html";
const CUSTOMER_RETURN_URL = "http://localhost:8005/customer.html";
const MAX_SUBJECT_LENGTH = 160;
const MAX_MESSAGE_LENGTH = 2000;

class ApiError extends Error {
  constructor(status, payload) {
    super(readServerMessage(payload));
    this.name = "ApiError";
    this.status = status;
  }
}

function readText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function readServerMessage(payload) {
  if (!payload || typeof payload !== "object") return "";
  const message = payload.error || payload.message;
  return typeof message === "string" ? message.trim().slice(0, 240) : "";
}

async function readPayload(response) {
  const body = await response.text();
  if (!body) return {};
  try {
    return JSON.parse(body);
  } catch (error) {
    return {};
  }
}

async function requestJson(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      ...options,
      credentials: "include",
      headers: { Accept: "application/json", ...(options.headers || {}) },
    });
  } catch (error) {
    throw new ApiError(0, {});
  }
  const payload = await readPayload(response);
  if (!response.ok) throw new ApiError(response.status, payload);
  return payload;
}

function makeElement(tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function clearElement(element) {
  element.replaceChildren();
}

function renderState(container, variant, title, message, retry) {
  clearElement(container);
  container.className = `customerState customerState--${variant}`;
  container.dataset.state = variant;
  container.append(makeElement("strong", "", title), makeElement("p", "", message));
  if (retry) {
    const retryButton = makeElement("button", "button button--secondary customerState__action", "Try again");
    retryButton.type = "button";
    retryButton.addEventListener("click", retry);
    container.appendChild(retryButton);
  }
}

function addLoginLink(container) {
  const link = makeElement("a", "customerState__link", "Sign in again");
  link.href = loginPageUrl();
  container.appendChild(link);
}

function showFeedback(container, variant, title, message, includeLoginLink = false) {
  clearElement(container);
  container.className = `customerFeedback customerFeedback--${variant}`;
  container.dataset.state = variant;
  container.hidden = false;
  container.setAttribute("role", variant === "success" ? "status" : "alert");
  container.append(makeElement("strong", "", title), makeElement("span", "", message));
  if (includeLoginLink) addLoginLink(container);
}

function clearFeedback(container) {
  clearElement(container);
  container.removeAttribute("class");
  container.removeAttribute("data-state");
  container.hidden = true;
}

function loginPageUrl() {
  const loginUrl = new URL(LOGIN_PAGE_URL);
  loginUrl.searchParams.set("return_url", CUSTOMER_RETURN_URL);
  return loginUrl.href;
}

function redirectToLogin() {
  window.location.replace(loginPageUrl());
}

function normalizeTicketId(value) {
  const text = String(value ?? "").trim();
  return /^\d{1,20}$/.test(text) ? text : "";
}

function extractUser(payload) {
  const user = payload?.user;
  if (!user || typeof user !== "object") return null;
  return {
    role: readText(user.role).toLowerCase(),
    name: readText(user.full_name),
    email: readText(user.email),
  };
}

function extractTickets(payload) {
  return Array.isArray(payload?.tickets) ? payload.tickets : [];
}

function extractTicket(payload) {
  return payload?.ticket && typeof payload.ticket === "object" ? payload.ticket : null;
}

function statusLabel(status) {
  const normalized = readText(status).toLowerCase();
  if (normalized === "needs_triage") return "Needs triage";
  if (normalized === "open") return "Open";
  if (normalized === "pending") return "Waiting for your reply";
  if (normalized === "solved") return "Solved";
  return "In progress";
}

function statusClass(status) {
  const normalized = readText(status).toLowerCase();
  return ["open", "pending", "solved"].includes(normalized) ? normalized : "open";
}

function formatDate(value) {
  const text = readText(value);
  if (!text) return "Recently updated";
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return "Recently updated";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function setFormBusy(form, busy, loadingElement) {
  form.querySelectorAll("input, textarea, button").forEach((control) => { control.disabled = busy; });
  if (loadingElement) loadingElement.hidden = !busy;
}

function errorCopy(error, context) {
  if (error.status === 401) return { variant: "auth-expired", title: "Your session has expired", message: "Sign in again to continue managing your support conversations." };
  if (error.status === 403) return { variant: "forbidden", title: "Support access is not available", message: "This account does not have permission to use the customer support area." };
  if (error.status === 404) return { variant: "not-found", title: "Conversation not found", message: "That conversation is no longer available to this account." };
  if (error.status === 400) return { variant: "validation", title: context === "reply" ? "Reply needs attention" : "Please check your details", message: error.message || "Review the information and try again." };
  if (error.status === 503 || error.status === 0) return { variant: "unavailable", title: "Support is temporarily unavailable", message: "Please try again in a moment." };
  return { variant: "error", title: "Something went wrong", message: "We could not complete that request. Please try again." };
}

function renderRequestError(container, error, context, retry) {
  const copy = errorCopy(error, context);
  renderState(container, copy.variant, copy.title, copy.message, retry);
  if (copy.variant === "auth-expired") addLoginLink(container);
}

function renderFormError(container, error, context) {
  const copy = errorCopy(error, context);
  showFeedback(container, copy.variant, copy.title, copy.message, copy.variant === "auth-expired");
}

function renderTicketList(container, tickets, countElement) {
  clearElement(container);
  container.removeAttribute("class");
  container.removeAttribute("data-state");
  const validTickets = tickets.filter((ticket) => normalizeTicketId(ticket && ticket.id));
  countElement.textContent = `${validTickets.length} ${validTickets.length === 1 ? "conversation" : "conversations"}`;
  if (!validTickets.length) {
    renderState(container, "empty", "No support conversations yet", "When you need help, start a new conversation and it will appear here.");
    return;
  }

  const list = makeElement("ul", "customerTicketList");
  list.setAttribute("aria-label", "Your support conversations");
  validTickets.forEach((ticket) => {
    const id = normalizeTicketId(ticket.id);
    const item = makeElement("li", "customerTicketList__item");
    const button = makeElement("button", "customerTicketCard");
    button.type = "button";
    button.dataset.ticketId = id;
    button.setAttribute("aria-controls", "ticket-detail-region");
    const header = makeElement("span", "customerTicketCard__header");
    header.append(makeElement("span", "customerTicketCard__number", `Ticket #${id}`), makeElement("span", `ticketStatus ticketStatus--${statusClass(ticket.status)}`, statusLabel(ticket.status)));
    button.append(header, makeElement("strong", "customerTicketCard__subject", readText(ticket.subject) || "Support conversation"), makeElement("span", "customerTicketCard__updated", formatDate(ticket.updated_at || ticket.created_at)));
    item.appendChild(button);
    list.appendChild(item);
  });
  container.appendChild(list);
}

function renderMessages(list, messages) {
  const safeMessages = Array.isArray(messages) ? messages : [];
  if (!safeMessages.length) {
    list.appendChild(makeElement("li", "messageThread__empty", "No messages in this conversation yet."));
    return;
  }
  safeMessages.forEach((message) => {
    if (!message || typeof message !== "object") return;
    const senderRole = readText(message.sender_role).toLowerCase() === "customer" ? "customer" : "staff";
    const item = makeElement("li", `messageThread__item messageThread__item--${senderRole}`);
    const meta = makeElement("div", "messageThread__meta");
    meta.append(makeElement("strong", "", senderRole === "customer" ? "You" : "Support team"), makeElement("span", "", senderRole === "customer" ? "Your message" : "Support reply"));
    const createdAt = readText(message.created_at);
    if (createdAt) {
      const time = makeElement("time", "", formatDate(createdAt));
      time.dateTime = createdAt;
      meta.appendChild(time);
    }
    item.append(meta, makeElement("p", "", readText(message.message || message.body)));
    list.appendChild(item);
  });
}

function renderTicketDetail(container, ticket, ticketId, onReply) {
  clearElement(container);
  container.className = "customerTicketDetail";
  container.dataset.ticketId = ticketId;
  container.hidden = false;
  const heading = makeElement("div", "customerTicketDetail__heading");
  const headingText = makeElement("div");
  headingText.append(makeElement("p", "customerTicketDetail__eyebrow", `Ticket #${ticketId}`), makeElement("h3", "customerTicketDetail__subject", readText(ticket.subject) || "Support conversation"));
  const closeButton = makeElement("button", "button button--secondary customerTicketDetail__close", "Close");
  closeButton.type = "button";
  closeButton.addEventListener("click", () => { container.hidden = true; container.removeAttribute("data-ticket-id"); });
  heading.append(headingText, closeButton);
  container.appendChild(heading);
  const status = makeElement("p", `customerTicketDetail__status ticketStatus ticketStatus--${statusClass(ticket.status)}`, statusLabel(ticket.status));
  status.setAttribute("aria-label", `Status: ${statusLabel(ticket.status)}`);
  container.appendChild(status);
  const metadata = makeElement("dl", "customerTicketDetail__metadata");
  [["Created", ticket.created_at], ["Last updated", ticket.updated_at || ticket.created_at]].forEach(([label, value]) => {
    const row = makeElement("div");
    row.append(makeElement("dt", "", label), makeElement("dd", "", formatDate(value)));
    metadata.appendChild(row);
  });
  container.appendChild(metadata);
  const conversation = makeElement("section", "customerConversation");
  conversation.setAttribute("aria-labelledby", "customer-conversation-title");
  conversation.appendChild(makeElement("h4", "customerConversation__title", "Conversation"));
  const messageList = makeElement("ol", "messageThread");
  renderMessages(messageList, ticket.messages);
  conversation.appendChild(messageList);
  container.appendChild(conversation);
  const feedback = makeElement("div", "customerFeedback");
  feedback.hidden = true;
  container.appendChild(feedback);
  const form = makeElement("form", "messageComposer customerReplyForm");
  form.noValidate = true;
  const label = makeElement("label", "", "Reply to support");
  const textarea = makeElement("textarea");
  textarea.id = `customer-reply-${ticketId}`;
  label.htmlFor = textarea.id;
  textarea.name = "message";
  textarea.rows = 4;
  textarea.maxLength = MAX_MESSAGE_LENGTH;
  textarea.required = true;
  textarea.setAttribute("aria-label", "Reply to support");
  const actions = makeElement("div", "messageComposer__actions");
  const submit = makeElement("button", "button", "Send reply");
  submit.type = "submit";
  const loading = makeElement("span", "customerLoading", "Sending reply…");
  loading.hidden = true;
  loading.setAttribute("role", "status");
  actions.append(submit, loading);
  form.append(label, textarea, actions);
  form.addEventListener("submit", (event) => onReply(event, form, textarea, feedback, loading, ticketId));
  container.appendChild(form);
}

function initializeCustomerDashboard() {
  const app = document.querySelector("[data-customer-app]");
  if (!app) return;
  const sessionRegion = app.querySelector("#session-region");
  const dashboard = app.querySelector("#customer-dashboard");
  const nameElement = app.querySelector("#current-user-name");
  const emailElement = app.querySelector("#current-user-email");
  const form = app.querySelector("#new-ticket-form");
  const formFeedback = app.querySelector("#ticket-form-feedback");
  const createLoading = app.querySelector("#ticket-create-loading");
  const listRegion = app.querySelector("#ticket-list-region");
  const countElement = app.querySelector("#ticket-count");
  const detailRegion = app.querySelector("#ticket-detail-region");

  async function loadTickets() {
    renderState(listRegion, "loading", "Loading your tickets…", "Your conversations will appear here.");
    countElement.textContent = "";
    try {
      const payload = await requestJson("/api/support/customer/tickets");
      renderTicketList(listRegion, extractTickets(payload), countElement);
    } catch (error) {
      renderRequestError(listRegion, error, "list", loadTickets);
    }
  }

  async function loadTicket(ticketId) {
    const safeTicketId = normalizeTicketId(ticketId);
    detailRegion.hidden = false;
    if (!safeTicketId) {
      renderState(detailRegion, "not-found", "Conversation not found", "That conversation is no longer available to this account.");
      return;
    }
    renderState(detailRegion, "loading", "Loading conversation…", "Your messages will appear here.");
    try {
      const payload = await requestJson(`/api/support/customer/tickets/${encodeURIComponent(safeTicketId)}`);
      const ticket = extractTicket(payload);
      if (!ticket || typeof ticket !== "object") throw new ApiError(404, {});
      renderTicketDetail(detailRegion, ticket, safeTicketId, submitReply);
    } catch (error) {
      renderRequestError(detailRegion, error, "detail", () => loadTicket(safeTicketId));
      detailRegion.hidden = false;
    }
  }

  async function submitReply(event, replyForm, textarea, feedback, loading, ticketId) {
    event.preventDefault();
    const message = textarea.value.trim();
    if (!message) {
      showFeedback(feedback, "validation", "Reply needs attention", "Message is required.");
      textarea.focus();
      return;
    }
    if (message.length > MAX_MESSAGE_LENGTH) {
      showFeedback(feedback, "validation", "Reply needs attention", `Message must be ${MAX_MESSAGE_LENGTH} characters or fewer.`);
      textarea.focus();
      return;
    }
    setFormBusy(replyForm, true, loading);
    clearFeedback(feedback);
    try {
      const payload = await requestJson(`/api/support/customer/tickets/${encodeURIComponent(ticketId)}/messages`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message }) });
      const returnedTicket = extractTicket(payload);
      if (returnedTicket && typeof returnedTicket === "object" && (returnedTicket.messages || returnedTicket.subject)) renderTicketDetail(detailRegion, returnedTicket, ticketId, submitReply);
      else await loadTicket(ticketId);
      const updatedFeedback = detailRegion.querySelector(".customerFeedback");
      if (updatedFeedback) showFeedback(updatedFeedback, "success", "Reply sent", "Your message was added to the conversation.");
      await loadTickets();
    } catch (error) {
      renderFormError(feedback, error, "reply");
    } finally {
      setFormBusy(replyForm, false, loading);
    }
  }

  async function submitNewTicket(event) {
    event.preventDefault();
    const subjectControl = form.elements.subject;
    const messageControl = form.elements.message;
    const subject = subjectControl.value.trim();
    const message = messageControl.value.trim();
    if (subject.length < 5 || subject.length > MAX_SUBJECT_LENGTH) {
      showFeedback(formFeedback, "validation", "Please check the subject", `Subject must be between 5 and ${MAX_SUBJECT_LENGTH} characters.`);
      subjectControl.focus();
      return;
    }
    if (!message) {
      showFeedback(formFeedback, "validation", "Please add a message", "Message is required.");
      messageControl.focus();
      return;
    }
    if (message.length > MAX_MESSAGE_LENGTH) {
      showFeedback(formFeedback, "validation", "Please shorten the message", `Message must be ${MAX_MESSAGE_LENGTH} characters or fewer.`);
      messageControl.focus();
      return;
    }
    setFormBusy(form, true, createLoading);
    clearFeedback(formFeedback);
    try {
      const payload = await requestJson("/api/support/customer/tickets", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ subject, message }) });
      const newTicket = extractTicket(payload);
      form.reset();
      showFeedback(formFeedback, "success", "Conversation started", "Your support request was sent successfully.");
      await loadTickets();
      const createdId = newTicket && normalizeTicketId(newTicket.id);
      if (createdId) await loadTicket(createdId);
    } catch (error) {
      renderFormError(formFeedback, error, "create");
    } finally {
      setFormBusy(form, false, createLoading);
    }
  }

  listRegion.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-ticket-id]");
    if (button && listRegion.contains(button)) loadTicket(button.dataset.ticketId);
  });
  form.addEventListener("submit", submitNewTicket);
  form.addEventListener("reset", () => clearFeedback(formFeedback));

  async function loadSession() {
    renderState(sessionRegion, "loading", "Checking your sign-in…", "We are securely loading your support account.");
    dashboard.hidden = true;
    try {
      const payload = await requestJson("/api/support/customer/session");
      const user = extractUser(payload);
      if (!user) throw new ApiError(503, {});
      if (user.role === "admin") {
        window.location.replace("staff.html");
        return;
      }
      nameElement.textContent = user.name || "Account holder";
      emailElement.textContent = user.email || "Email unavailable";
      sessionRegion.hidden = true;
      dashboard.hidden = false;
      await loadTickets();
    } catch (error) {
      if (error.status === 401) {
        renderRequestError(sessionRegion, error, "session");
        redirectToLogin();
        return;
      }
      renderRequestError(sessionRegion, error, "session", loadSession);
    }
  }
  loadSession();
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initializeCustomerDashboard);
else initializeCustomerDashboard();
