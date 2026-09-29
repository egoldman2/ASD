const ACCOUNT_API_URL = "http://localhost:6002";
const LOGIN_URL = "login.html";

function redirectToLogin() {
  window.location.replace(LOGIN_URL);
}

const nativeFetch = window.fetch.bind(window);

window.fetch = async function (...args) {
  const response = await nativeFetch(...args);
  if (response.status === 401) {
    redirectToLogin();
  }
  return response;
};

// Still check on page load, so a signed-out visit redirects immediately
// rather than waiting for the first API call to fail.
window
  .fetch(`${ACCOUNT_API_URL}/api/session`, { credentials: "include" })
  .then((response) => (response.ok ? response.json() : null))
  .then((result) => {
    const user = result && result.user;
    if (!user || user.role !== "admin") {
      redirectToLogin();
    }
  })
  .catch(() => {
    redirectToLogin();
  });