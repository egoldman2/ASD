const AUTH_API_URL = "http://localhost:6002";

const profileForm = document.querySelector("#profileForm");
const profileMessage = document.querySelector("#profileMessage");


async function authRequest(path, options = {}) {
  const response = await fetch(`${AUTH_API_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  const result = await response.json();

  if (!response.ok) {
    const error = new Error(result.error || "The request failed.");
    error.status = response.status;
    throw error;
  }

  return result;
}


function showProfileMessage(message, success = false) {
  profileMessage.textContent = message;
  profileMessage.classList.toggle("success", success);
}


async function loadProfile() {
  const result = await authRequest("/api/profile");
  const user = result.user;

  document.querySelector("#customerGreeting").textContent = (
    `Welcome, ${user.full_name}`
  );
  profileForm.elements.full_name.value = user.full_name;
  profileForm.elements.email.value = user.email;
}


profileForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  try {
    const result = await authRequest("/api/profile", {
      method: "PUT",
      body: JSON.stringify({
        full_name: profileForm.elements.full_name.value,
        email: profileForm.elements.email.value,
      }),
    });
    document.querySelector("#customerGreeting").textContent = (
      `Welcome, ${result.user.full_name}`
    );
    showProfileMessage("Your profile was updated.", true);
  } catch (error) {
    showProfileMessage(error.message);
  }
});


async function startCustomerPage() {
  try {
    const sessionResult = await authRequest("/api/session");

    if (sessionResult.user.role === "admin") {
      window.location.replace("admin.html");
      return;
    }

    await loadProfile();
  } catch (error) {
    window.location.replace("index.html");
  }
}


startCustomerPage();
