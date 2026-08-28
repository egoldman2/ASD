const AUTH_API_URL = "http://localhost:6002";

const loginForm = document.querySelector("#loginForm");
const loginButton = document.querySelector("#loginButton");
const loginMessage = document.querySelector("#loginMessage");


function redirectForRole(user) {
  const destination = user.role === "admin"
    ? "admin.html"
    : "customer.html";

  window.location.replace(destination);
}


async function checkExistingSession() {
  try {
    const response = await fetch(`${AUTH_API_URL}/api/session`, {
      credentials: "include",
    });

    if (response.ok) {
      const result = await response.json();
      redirectForRole(result.user);
    }
  } catch (error) {
    // The login form remains available if the backend is still starting.
  }
}


loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  loginMessage.textContent = "";
  loginMessage.classList.remove("success");
  loginButton.disabled = true;
  loginButton.textContent = "Signing in...";

  const loginDetails = {
    email: loginForm.elements.email.value,
    password: loginForm.elements.password.value,
  };

  try {
    const response = await fetch(`${AUTH_API_URL}/api/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
      body: JSON.stringify(loginDetails),
    });
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || "Login failed.");
    }

    loginMessage.classList.add("success");
    loginMessage.textContent = `Welcome, ${result.user.full_name}.`;
    redirectForRole(result.user);
  } catch (error) {
    loginMessage.textContent = error.message === "Failed to fetch"
      ? "The login service is unavailable. Please try again."
      : error.message;
  } finally {
    loginButton.disabled = false;
    loginButton.textContent = "Sign in";
  }
});


checkExistingSession();
