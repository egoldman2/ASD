// The shared Flask API is served from localhost:5000 while this frontend uses
// localhost:8005. CORS is configured by the shared app for these local origins.
htmx.config.selfRequestsOnly = false;

document.addEventListener("htmx:beforeSwap", (event) => {
  const form = event.detail.requestConfig?.elt;

  if (form?.matches(".ticketForm") && event.detail.xhr.status >= 400) {
    event.detail.shouldSwap = true;
    event.detail.isError = false;
  }
});

document.addEventListener("htmx:afterRequest", (event) => {
  const form = event.detail.requestConfig?.elt;

  if (form?.matches(".ticketForm") && event.detail.xhr.status === 201) {
    form.reset();
  }
});

function loadSelectedTicket() {
  const ticketDetailRegion = document.querySelector("#ticket-detail-region");

  if (!ticketDetailRegion) {
    return;
  }

  const ticketId = new URLSearchParams(window.location.search).get("ticket") || "1011";
  htmx.ajax("GET", `http://localhost:5000/support-ui/staff/tickets/${ticketId}`, {
    target: "#ticket-detail-region",
    swap: "innerHTML",
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", loadSelectedTicket);
} else {
  loadSelectedTicket();
}
