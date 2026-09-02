const AUTH_API_URL = "http://localhost:6002";

const profileForm = document.querySelector("#profileForm");
const profileMessage = document.querySelector("#profileMessage");
const profileName = document.querySelector("#profileName");
const profileEmail = document.querySelector("#profileEmail");
const loyaltyMessage = document.querySelector("#loyaltyMessage");
const loyaltyHistoryBody = document.querySelector("#loyaltyHistoryBody");


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


function formatDate(dateValue) {
  return new Intl.DateTimeFormat("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${dateValue.replace(" ", "T")}Z`));
}


function renderLoyaltyHistory(transactions) {
  loyaltyHistoryBody.replaceChildren();

  if (transactions.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 3;
    cell.textContent = "No points activity yet.";
    row.append(cell);
    loyaltyHistoryBody.append(row);
    return;
  }

  for (const transaction of transactions) {
    const row = document.createElement("tr");
    const dateCell = document.createElement("td");
    const reasonCell = document.createElement("td");
    const pointsCell = document.createElement("td");

    dateCell.textContent = formatDate(transaction.created_at);
    reasonCell.textContent = transaction.reason;
    pointsCell.className = transaction.points_change > 0
      ? "pointsChange pointsChange--positive"
      : "pointsChange pointsChange--negative";
    pointsCell.textContent = transaction.points_change > 0
      ? `+${transaction.points_change}`
      : String(transaction.points_change);

    row.append(dateCell, reasonCell, pointsCell);
    loyaltyHistoryBody.append(row);
  }
}


async function loadLoyalty() {
  const [loyaltyResult, historyResult] = await Promise.all([
    authRequest("/api/loyalty"),
    authRequest("/api/loyalty/history"),
  ]);
  const loyalty = loyaltyResult.loyalty;
  const tierBadge = document.querySelector("#loyaltyTierBadge");
  const progress = document.querySelector("#loyaltyProgress");

  document.querySelector("#loyaltyPoints").textContent = (
    loyalty.points_balance.toLocaleString("en-AU")
  );
  tierBadge.textContent = loyalty.tier;
  tierBadge.dataset.tier = loyalty.tier.toLowerCase();

  if (loyalty.next_tier === null) {
    document.querySelector("#loyaltyProgressMessage").textContent = (
      "You have reached our highest membership tier."
    );
    document.querySelector("#loyaltyProgressCount").textContent = "Gold";
    progress.max = loyalty.points_balance || 1;
    progress.value = loyalty.points_balance;
  } else {
    const tierStart = loyalty.tier === "Silver" ? 500 : 0;
    const tierTarget = loyalty.tier === "Silver" ? 1000 : 500;
    document.querySelector("#loyaltyProgressMessage").textContent = (
      `${loyalty.points_to_next_tier} points until ${loyalty.next_tier}`
    );
    document.querySelector("#loyaltyProgressCount").textContent = (
      `${loyalty.points_balance} / ${tierTarget}`
    );
    progress.max = tierTarget - tierStart;
    progress.value = loyalty.points_balance - tierStart;
  }

  renderLoyaltyHistory(historyResult.transactions);
  loyaltyMessage.textContent = "";
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
  profileName.value = user.full_name;
  profileEmail.value = user.email;
}


profileForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  try {
    const result = await authRequest("/api/profile", {
      method: "PUT",
      body: JSON.stringify({
        full_name: profileName.value,
        email: profileEmail.value,
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

    await Promise.all([loadProfile(), loadLoyalty()]);
  } catch (error) {
    if (error.status === 401 || error.status === 403) {
      window.location.replace("index.html");
      return;
    }
    loyaltyMessage.textContent = error.message;
  }
}


startCustomerPage();
