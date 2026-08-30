const AUTH_API_URL = "http://localhost:6002";

const loginForm = document.querySelector("#loginForm");
const loginButton = document.querySelector("#loginButton");
const loginMessage = document.querySelector("#loginMessage");
const registerForm = document.querySelector("#registerForm");
const registerButton = document.querySelector("#registerButton");
const registerMessage = document.querySelector("#registerMessage");
const loginPanel = document.querySelector("#loginPanel");
const registerPanel = document.querySelector("#registerPanel");
const loginEmail = document.querySelector("#loginEmail");
const loginPassword = document.querySelector("#loginPassword");
const registerName = document.querySelector("#registerName");
const registerEmail = document.querySelector("#registerEmail");
const registerPassword = document.querySelector("#registerPassword");
const registerPasswordConfirmation = document.querySelector(
  "#registerPasswordConfirmation"
);


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
    ? registerName
    : loginEmail;
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
    email: loginEmail.value,
    password: loginPassword.value,
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
    full_name: registerName.value,
    email: registerEmail.value,
    password: registerPassword.value,
    password_confirmation: registerPasswordConfirmation.value,
  };

  if (registrationDetails.password !== registrationDetails.password_confirmation) {
    registerMessage.textContent = "Passwords do not match.";
    registerPasswordConfirmation.focus();
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
