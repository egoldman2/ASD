const AUTH_API_URL = "http://localhost:6002";

const loyaltyTableBody = document.querySelector("#loyaltyTableBody");
const loyaltySearch = document.querySelector("#loyaltySearch");
const loyaltyMessage = document.querySelector("#loyaltyMessage");
const loyaltyAdjustmentPanel = document.querySelector("#loyaltyAdjustmentPanel");
const loyaltyAdjustmentForm = document.querySelector("#loyaltyAdjustmentForm");
const loyaltyCustomerId = document.querySelector("#loyaltyCustomerId");
const pointsChangeInput = document.querySelector("#pointsChange");
const pointsReasonInput = document.querySelector("#pointsReason");
const loyaltyHistoryBody = document.querySelector("#adminLoyaltyHistoryBody");

let loyaltyAccounts = [];


async function authRequest(path, options = {}) {
  const response = await fetch(`${AUTH_API_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      ...(options.body ? {"Content-Type": "application/json"} : {}),
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


function showMessage(message, success = false) {
  loyaltyMessage.textContent = message;
  loyaltyMessage.classList.toggle("success", success);
}


function formatDate(dateValue) {
  return new Intl.DateTimeFormat("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${dateValue.replace(" ", "T")}Z`));
}


function statusBadge(isActive) {
  const badge = document.createElement("span");
  badge.className = isActive === 1
    ? "statusBadge statusBadge--active"
    : "statusBadge statusBadge--disabled";
  badge.textContent = isActive === 1 ? "Active" : "Disabled";
  return badge;
}


function updateSummary() {
  document.querySelector("#totalLoyaltyMembers").textContent = loyaltyAccounts.length;
  document.querySelector("#totalLoyaltyPoints").textContent = loyaltyAccounts.reduce(
    (total, account) => total + account.points_balance,
    0
  ).toLocaleString("en-AU");

  for (const tier of ["bronze", "silver", "gold"]) {
    const count = loyaltyAccounts.filter(
      (account) => account.tier.toLowerCase() === tier
    ).length;
    document.querySelector(`#${tier}Members`).textContent = count;
  }
}


function renderHistory(transactions) {
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
    dateCell.dataset.label = "Date";
    reasonCell.dataset.label = "Reason";
    pointsCell.dataset.label = "Points";
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


function renderAccounts() {
  const searchTerm = loyaltySearch.value.trim().toLowerCase();
  const matchingAccounts = loyaltyAccounts.filter((account) => (
    account.full_name.toLowerCase().includes(searchTerm)
    || account.email.toLowerCase().includes(searchTerm)
  ));

  loyaltyTableBody.replaceChildren();

  if (matchingAccounts.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 6;
    cell.textContent = "No loyalty accounts match your search.";
    row.append(cell);
    loyaltyTableBody.append(row);
    return;
  }

  for (const account of matchingAccounts) {
    const row = document.createElement("tr");
    const nameCell = document.createElement("td");
    const emailCell = document.createElement("td");
    const tierCell = document.createElement("td");
    const pointsCell = document.createElement("td");
    const statusCell = document.createElement("td");
    const actionCell = document.createElement("td");
    const manageButton = document.createElement("button");

    nameCell.textContent = account.full_name;
    emailCell.textContent = account.email;
    const tierBadge = document.createElement("span");
    tierBadge.className = "loyaltyTierBadge";
    tierBadge.dataset.tier = account.tier.toLowerCase();
    tierBadge.textContent = account.tier;
    tierCell.append(tierBadge);
    pointsCell.textContent = account.points_balance.toLocaleString("en-AU");
    nameCell.dataset.label = "Customer";
    emailCell.dataset.label = "Email";
    tierCell.dataset.label = "Tier";
    pointsCell.dataset.label = "Points";
    statusCell.dataset.label = "Status";
    actionCell.dataset.label = "Actions";
    statusCell.append(statusBadge(account.is_active));
    manageButton.type = "button";
    manageButton.className = "actionButton";
    manageButton.textContent = "Manage points";
    manageButton.addEventListener("click", () => openAdjustment(account));
    actionCell.append(manageButton);

    row.append(nameCell, emailCell, tierCell, pointsCell, statusCell, actionCell);
    loyaltyTableBody.append(row);
  }
}


async function openAdjustment(account) {
  loyaltyAdjustmentForm.reset();
  loyaltyCustomerId.value = account.user_id;
  document.querySelector("#loyaltyCustomerName").textContent = (
    `${account.full_name} currently has ${account.points_balance.toLocaleString("en-AU")} points.`
  );
  loyaltyAdjustmentPanel.hidden = false;
  loyaltyAdjustmentPanel.scrollIntoView({behavior: "smooth", block: "start"});

  try {
    const result = await authRequest(
      `/api/admin/loyalty/${account.user_id}/history`
    );
    renderHistory(result.transactions);
    pointsChangeInput.focus();
  } catch (error) {
    showMessage(error.message);
  }
}


async function loadLoyaltyAccounts() {
  const result = await authRequest("/api/admin/loyalty");
  loyaltyAccounts = result.loyalty_accounts;
  updateSummary();
  renderAccounts();
}


loyaltyAdjustmentForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const userId = loyaltyCustomerId.value;
  const pointsChange = Number(pointsChangeInput.value);
  const reason = pointsReasonInput.value.trim();
  const account = loyaltyAccounts.find(
    (item) => String(item.user_id) === userId
  );

  if (!Number.isInteger(pointsChange) || pointsChange === 0) {
    showMessage("Enter a whole number other than zero.");
    return;
  }

  const actionText = pointsChange > 0
    ? `Add ${pointsChange} points to ${account.full_name}?`
    : `Remove ${Math.abs(pointsChange)} points from ${account.full_name}?`;

  if (!window.confirm(actionText)) {
    return;
  }

  try {
    await authRequest(`/api/admin/loyalty/${userId}/adjustments`, {
      method: "POST",
      body: JSON.stringify({
        points_change: pointsChange,
        reason,
      }),
    });
    loyaltyAdjustmentPanel.hidden = true;
    await loadLoyaltyAccounts();
    showMessage("Loyalty points updated.", true);
  } catch (error) {
    showMessage(error.message);
  }
});


document.querySelector("#cancelLoyaltyButton").addEventListener("click", () => {
  loyaltyAdjustmentPanel.hidden = true;
});
loyaltySearch.addEventListener("input", renderAccounts);


async function startLoyaltyPage() {
  try {
    const sessionResult = await authRequest("/api/session");

    if (sessionResult.user.role !== "admin") {
      window.location.replace("customer.html");
      return;
    }

    document.querySelector("#userGreeting").textContent = (
      `Signed in as ${sessionResult.user.full_name}.`
    );
    await loadLoyaltyAccounts();
  } catch (error) {
    if (error.status === 401 || error.status === 403) {
      window.location.replace("index.html");
      return;
    }
    showMessage(error.message);
  }
}


startLoyaltyPage();
