const AUTH_API_URL = "http://localhost:6002";

const loginForm = document.querySelector("#loginForm");
const loginButton = document.querySelector("#loginButton");
const loginMessage = document.querySelector("#loginMessage");
const registerForm = document.querySelector("#registerForm");
const registerButton = document.querySelector("#registerButton");
const registerMessage = document.querySelector("#registerMessage");
const loginPanel = document.querySelector("#loginPanel");
const registerPanel = document.querySelector("#registerPanel");


function redirectForRole(user) {
  const destination = user.role === "admin"
    ? "admin.html"
    : "customer.html";

  window.location.replace(destination);
}


function requestErrorMessage(error, serviceName) {
  return error.message === "Failed to fetch"
    ? `The ${serviceName} service is unavailable. Please try again.`
    : error.message;
}


function showAuthView(view) {
  const showingRegistration = view === "register";

  loginPanel.hidden = showingRegistration;
  registerPanel.hidden = !showingRegistration;
  loginMessage.textContent = "";
  registerMessage.textContent = "";

  const firstField = showingRegistration
    ? registerForm.elements.full_name
    : loginForm.elements.email;
  firstField.focus();
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
    loginMessage.textContent = requestErrorMessage(error, "login");
  } finally {
    loginButton.disabled = false;
    loginButton.textContent = "Sign in";
  }
});


registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  registerMessage.textContent = "";
  registerMessage.classList.remove("success");

  const registrationDetails = {
    full_name: registerForm.elements.full_name.value,
    email: registerForm.elements.email.value,
    password: registerForm.elements.password.value,
    password_confirmation: registerForm.elements.password_confirmation.value,
  };

  if (registrationDetails.password !== registrationDetails.password_confirmation) {
    registerMessage.textContent = "Passwords do not match.";
    registerForm.elements.password_confirmation.focus();
    return;
  }

  registerButton.disabled = true;
  registerButton.textContent = "Creating account...";

  try {
    const response = await fetch(`${AUTH_API_URL}/api/register`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
      body: JSON.stringify(registrationDetails),
    });
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || "Account creation failed.");
    }

    registerMessage.classList.add("success");
    registerMessage.textContent = `Welcome, ${result.user.full_name}.`;
    redirectForRole(result.user);
  } catch (error) {
    registerMessage.textContent = requestErrorMessage(error, "registration");
  } finally {
    registerButton.disabled = false;
    registerButton.textContent = "Create account";
  }
});


const requestedView = new URLSearchParams(window.location.search).get("view");
showAuthView(requestedView === "register" ? "register" : "login");

checkExistingSession();
