const ACCOUNT_API_URL = "http://localhost:6002";


function accountPageUrl(role) {
  return role === "admin"
    ? "http://localhost:8003/admin.html"
    : "http://localhost:8003/customer.html";
}


async function configureAccountMenu(menu) {
  const trigger = menu.querySelector("[data-account-trigger]");
  const welcomeMessage = menu.querySelector("[data-account-welcome]");
  const signInAction = menu.querySelector("[data-account-sign-in]");
  const registerAction = menu.querySelector("[data-account-register]");
  const primaryAction = menu.querySelector("[data-account-primary]");
  const profileAction = menu.querySelector("[data-account-profile]");
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
    const accountUrl = accountPageUrl(result.user.role);

    welcomeMessage.textContent = `Welcome, ${result.user.full_name}`;
    signInAction.hidden = true;
    registerAction.hidden = true;
    primaryAction.hidden = false;
    primaryAction.href = accountUrl;
    profileAction.hidden = true;
    logoutAction.hidden = false;
  } catch (error) {
    welcomeMessage.textContent = "Welcome to ASD 2026";
    signInAction.hidden = false;
    registerAction.hidden = false;
    primaryAction.hidden = true;
    profileAction.hidden = false;
    profileAction.href = "http://localhost:8003";
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


for (const navContainer of document.querySelectorAll(".appleNav .navContainer")) {
  const menuButton = navContainer.querySelector("[data-mobile-menu-trigger]");
  const navigation = navContainer.querySelector(".navLinks");

  function setMobileMenuOpen(open) {
    navContainer.classList.toggle("mobileOpen", open);
    menuButton.setAttribute("aria-expanded", String(open));
  }

  menuButton.addEventListener("click", () => {
    setMobileMenuOpen(!navContainer.classList.contains("mobileOpen"));
  });

  navigation.addEventListener("click", (event) => {
    if (event.target.closest("a")) {
      setMobileMenuOpen(false);
    }
  });

  document.addEventListener("click", (event) => {
    if (!navContainer.contains(event.target)) {
      setMobileMenuOpen(false);
    }
  });

  navContainer.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      setMobileMenuOpen(false);
      menuButton.focus();
    }
  });
}
