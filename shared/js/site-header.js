const SITE_NAVIGATION = [
  {key: "catalogue", label: "Catalogue", href: "http://localhost:8001"},
  {key: "support", label: "Support", href: "http://localhost:8005"},
];

const SITE_SECTION_BY_PORT = {
  "8000": "",
  "8001": "catalogue",
  "8003": "account",
  "8004": "",
  "8005": "support",
};


function currentSiteSection(fallbackSection) {
  if (Object.prototype.hasOwnProperty.call(SITE_SECTION_BY_PORT, window.location.port)) {
    return SITE_SECTION_BY_PORT[window.location.port];
  }

  return fallbackSection;
}


function navigationLink(item, activeSection) {
  const activeClass = item.key === activeSection ? " active" : "";
  const currentPage = item.key === activeSection ? ' aria-current="page"' : "";

  return `<a href="${item.href}" class="navLink${activeClass}"${currentPage}>${item.label}</a>`;
}


function siteHeaderMarkup(activeSection) {
  const accountActiveClass = activeSection === "account" ? " active" : "";

  return `
    <div class="navContainer">
      <div class="navLogo">
        <a href="http://localhost:8000" class="logoLink" aria-label="ASD 2026 home">
          <span class="logoMain">ASD 2026</span>
        </a>
      </div>

      <button class="mobileMenuButton" type="button" aria-controls="mainNavigation" aria-expanded="false" data-mobile-menu-trigger>
        <span class="mobileMenuButtonBar" aria-hidden="true"></span>
        <span class="mobileMenuButtonBar" aria-hidden="true"></span>
        <span class="visuallyHidden">Menu</span>
      </button>

      <nav id="mainNavigation" class="navLinks" aria-label="Main navigation">
        ${SITE_NAVIGATION.map((item) => navigationLink(item, activeSection)).join("")}
        <a href="http://localhost:8001" class="navLink navSearchLink" aria-label="Search products">
          <svg class="navSearchIcon" viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="10.5" cy="10.5" r="6.5"></circle>
            <path d="m15.5 15.5 5 5"></path>
          </svg>
          <span class="navSearchLabel">Search</span>
        </a>

        <div class="accountMenu" data-account-menu>
          <button class="navLink accountMenuButton${accountActiveClass}" type="button" aria-expanded="false" aria-haspopup="true" data-account-trigger>
            <span class="accountMenuIcon" aria-hidden="true"></span>
            <span>Account</span>
          </button>
          <div class="accountMenuPanel" aria-label="Account options">
            <div class="accountMenuHeader">
              <p class="accountMenuWelcome" data-account-welcome>Welcome to ASD 2026</p>
              <div class="accountMenuActions">
                <a class="accountMenuAction accountMenuActionPrimary" href="http://localhost:8003" data-account-sign-in>Sign in</a>
                <a class="accountMenuAction accountMenuActionSecondary" href="http://localhost:8003/?view=register" data-account-register>Create account</a>
                <a class="accountMenuAction accountMenuActionPrimary" href="http://localhost:8003/customer.html" data-account-primary hidden>My account</a>
                <button class="accountMenuAction accountMenuActionSecondary" type="button" data-account-logout hidden>Log out</button>
              </div>
            </div>
            <div class="accountMenuLinks">
              <a class="accountMenuItem" href="http://localhost:8003" data-account-profile>
                <svg class="accountMenuItemIcon" viewBox="0 0 24 24" aria-hidden="true">
                  <circle cx="12" cy="7" r="4"></circle>
                  <path d="M4.5 21c.8-5 3.3-7 7.5-7s6.7 2 7.5 7"></path>
                </svg>
                <span>My account</span>
              </a>
              <a class="accountMenuItem" href="http://localhost:8004">
                <svg class="accountMenuItemIcon" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M4 7h16v14H4z"></path>
                  <path d="M7 3h10l3 4H4z"></path>
                </svg>
                <span>My orders</span>
              </a>
              <a class="accountMenuItem" href="http://localhost:8004">
                <svg class="accountMenuItemIcon" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M4 7h16v14H4z"></path>
                  <path d="M7 3h10l3 4H4z"></path>
                  <path d="M15 14H8m0 0 3-3m-3 3 3 3"></path>
                </svg>
                <span>My returns</span>
              </a>
            </div>
          </div>
        </div>
      </nav>
    </div>
  `;
}


for (const header of document.querySelectorAll("[data-site-header]")) {
  const activeSection = currentSiteSection(header.dataset.active || "");
  header.dataset.active = activeSection;
  header.innerHTML = siteHeaderMarkup(activeSection);
}
