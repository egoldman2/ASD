const ACCOUNT_API_URL = "http://localhost:6002";
const LOGIN_URL = "login.html";

fetch(`${ACCOUNT_API_URL}/api/session`, { credentials: "include" })
  .then((response) => (response.ok ? response.json() : null))
  .then((result) => {
    const user = result && result.user;
    if (!user || user.role !== "admin") {
      window.location.replace(LOGIN_URL);
    }
  })
  .catch(() => {
    window.location.replace(LOGIN_URL);
  });