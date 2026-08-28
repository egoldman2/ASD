const ACCOUNT_API_URL = "http://localhost:6002";


function accountPageUrl(role) {
  return role === "admin"
    ? "http://localhost:8003/admin.html"
    : "http://localhost:8003/customer.html";
}


async function configureAccountMenu(menu) {
  const trigger = menu.querySelector("[data-account-trigger]");
  const primaryAction = menu.querySelector("[data-account-primary]");
  const logoutAction = menu.querySelector("[data-account-logout]");

  function setOpen(open) {
    if (open) {
      menu.classList.remove("dismissed");
    }
    menu.classList.toggle("open", open);
    trigger.setAttribute("aria-expanded", String(open));
  }

  menu.addEventListener("mouseleave", () => {
    menu.classList.remove("dismissed");
  });

  trigger.addEventListener("click", () => {
    setOpen(!menu.classList.contains("open"));
  });

  document.addEventListener("click", (event) => {
    if (!menu.contains(event.target)) {
      setOpen(false);
    }
  });

  menu.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      setOpen(false);
      menu.classList.add("dismissed");
      trigger.focus();
    }
  });

  try {
    const response = await fetch(`${ACCOUNT_API_URL}/api/session`, {
      credentials: "include",
    });

    if (!response.ok) {
      throw new Error("Signed out");
    }

    const result = await response.json();
    primaryAction.textContent = "My account";
    primaryAction.href = accountPageUrl(result.user.role);
    logoutAction.hidden = false;
  } catch (error) {
    primaryAction.textContent = "Sign in";
    primaryAction.href = "http://localhost:8003";
    logoutAction.hidden = true;
  }

  logoutAction.addEventListener("click", async () => {
    logoutAction.disabled = true;
    logoutAction.textContent = "Logging out...";

    try {
      await fetch(`${ACCOUNT_API_URL}/api/logout`, {
        method: "POST",
        credentials: "include",
      });
    } finally {
      window.location.replace("http://localhost:8003");
    }
  });
}


for (const menu of document.querySelectorAll("[data-account-menu]")) {
  configureAccountMenu(menu);
}
