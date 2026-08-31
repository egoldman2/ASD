"use strict";

const SUPPORT_LOGIN_URL = "http://localhost:8003/index.html";

function supportLoginUrl() {
  const login = new URL(SUPPORT_LOGIN_URL);
  login.searchParams.set("return_url", "http://localhost:8005/");
  return login.href;
}

function showEntryFailure(message) {
  const state = document.querySelector("#support-entry-state");
  const header = document.querySelector("#support-entry-header");
  const fallback = document.querySelector("#support-entry-fallback");
  const login = document.querySelector("#support-login-link");
  state.className = "customerState customerState--unavailable";
  state.replaceChildren();
  const title = document.createElement("strong");
  title.textContent = "Support access could not be verified";
  const detail = document.createElement("p");
  detail.textContent = message;
  state.append(title, detail);
  header.hidden = false;
  fallback.hidden = false;
  login.href = supportLoginUrl();
}

async function routeSupportUser() {
  try {
    const response = await fetch("/api/support/customer/session", {
      credentials: "include",
      headers: { Accept: "application/json" },
    });
    if (response.status === 401) {
      window.location.replace(supportLoginUrl());
      return;
    }
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.user) {
      throw new Error("The support service is temporarily unavailable. Please try again.");
    }
    window.location.replace(payload.user.role === "admin" ? "staff.html" : "customer.html");
  } catch (error) {
    showEntryFailure(error.message || "The support service is temporarily unavailable. Please try again.");
  }
}

routeSupportUser();
