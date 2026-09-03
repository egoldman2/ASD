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
