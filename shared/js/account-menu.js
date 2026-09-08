const ACCOUNT_API_URL = "http://localhost:6002";


function accountPageUrl(role) {
  return role === "admin"
    ? "http://localhost:8003/admin.html"
    : "http://localhost:8003/customer.html";
}


function configureRoleNavigation(role) {
  const isAdmin = role === "admin";

  for (const link of document.querySelectorAll("[data-admin-navigation]")) {
    link.hidden = !isAdmin;
  }
}


async function configureAccountMenu(menu) {
  const trigger = menu.querySelector("[data-account-trigger]");
  const triggerLabel = menu.querySelector("[data-account-label]");
  const welcomeMessage = menu.querySelector("[data-account-welcome]");
  const signInAction = menu.querySelector("[data-account-sign-in]");
  const registerAction = menu.querySelector("[data-account-register]");
  const accountActions = menu.querySelector("[data-account-actions]");
  const accountLinks = menu.querySelector("[data-account-links]");
  const primaryAction = menu.querySelector("[data-account-primary]");
  const profileAction = menu.querySelector("[data-account-profile]");
  const loyaltyAction = menu.querySelector("[data-account-loyalty]");
  const ordersAction = menu.querySelector("[data-account-orders]");
  const returnsAction = menu.querySelector("[data-account-returns]");
  const logoutAction = menu.querySelector("[data-account-logout]");
  const authenticatedLinks = menu.querySelectorAll(
    "[data-account-authenticated-link]",
  );

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
    const isAdmin = result.user.role === "admin";
    configureRoleNavigation(result.user.role);

    triggerLabel.textContent = isAdmin ? "Admin" : "Account";
    welcomeMessage.textContent = `Welcome, ${result.user.full_name}`;
    signInAction.hidden = true;
    registerAction.hidden = true;
    primaryAction.hidden = isAdmin;
    primaryAction.href = accountUrl;
    primaryAction.textContent = isAdmin ? "Account management" : "My account";
    profileAction.hidden = true;
    loyaltyAction.hidden = true;
    ordersAction.hidden = isAdmin;
    ordersAction.querySelector("span").textContent = "My orders";
    returnsAction.hidden = isAdmin;
    accountLinks.hidden = isAdmin;
    accountActions.classList.toggle("accountMenuActions--single", isAdmin);
    logoutAction.hidden = false;
  } catch (error) {
    configureRoleNavigation(null);
    triggerLabel.textContent = "Account";
    welcomeMessage.textContent = "Welcome to ASD 2026";
    signInAction.hidden = false;
    registerAction.hidden = false;
    primaryAction.hidden = true;
    primaryAction.textContent = "My account";
    accountLinks.hidden = true;
    accountActions.classList.remove("accountMenuActions--single");
    profileAction.hidden = true;
    profileAction.href = "http://localhost:8003";
    for (const link of authenticatedLinks) {
      link.hidden = true;
    }
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
