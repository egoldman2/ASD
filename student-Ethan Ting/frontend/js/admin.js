const AUTH_API_URL = "http://localhost:6002";

const customerTableBody = document.querySelector("#customerTableBody");
const customerFormPanel = document.querySelector("#customerFormPanel");
const customerForm = document.querySelector("#customerForm");
const customerPasswordField = document.querySelector("#customerPasswordField");
const customerPassword = document.querySelector("#customerPassword");
const customerSearch = document.querySelector("#customerSearch");
const adminMessage = document.querySelector("#adminMessage");
const loyaltyAdjustmentPanel = document.querySelector("#loyaltyAdjustmentPanel");
const loyaltyAdjustmentForm = document.querySelector("#loyaltyAdjustmentForm");
const adminLoyaltyHistoryBody = document.querySelector("#adminLoyaltyHistoryBody");
const loyaltyCustomerId = document.querySelector("#loyaltyCustomerId");
const pointsChangeInput = document.querySelector("#pointsChange");
const pointsReasonInput = document.querySelector("#pointsReason");
const customerIdInput = document.querySelector("#customerId");
const customerNameInput = document.querySelector("#customerName");
const customerEmailInput = document.querySelector("#customerEmail");

let customers = [];
let loyaltyAccounts = [];


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


function showMessage(message, success = false) {
  adminMessage.textContent = message;
  adminMessage.classList.toggle("success", success);
}


function updateSummary() {
  document.querySelector("#totalCustomers").textContent = customers.length;
  document.querySelector("#activeCustomers").textContent = customers.filter(
    (customer) => customer.is_active === 1
  ).length;
  document.querySelector("#disabledCustomers").textContent = customers.filter(
    (customer) => customer.is_active === 0
  ).length;
  document.querySelector("#totalLoyaltyPoints").textContent = loyaltyAccounts.reduce(
    (total, loyalty) => total + loyalty.points_balance,
    0
  ).toLocaleString("en-AU");
}


function formatDate(dateValue) {
  return new Intl.DateTimeFormat("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${dateValue.replace(" ", "T")}Z`));
}


function renderLoyaltyHistory(transactions) {
  adminLoyaltyHistoryBody.replaceChildren();

  if (transactions.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 3;
    cell.textContent = "No points activity yet.";
    row.append(cell);
    adminLoyaltyHistoryBody.append(row);
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
    adminLoyaltyHistoryBody.append(row);
  }
}


function createActionButton(label, className, action) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.textContent = label;
  button.addEventListener("click", action);
  return button;
}


function renderCustomers() {
  const searchTerm = customerSearch.value.trim().toLowerCase();
  const matchingCustomers = customers.filter((customer) => (
    customer.full_name.toLowerCase().includes(searchTerm)
    || customer.email.toLowerCase().includes(searchTerm)
  ));

  customerTableBody.replaceChildren();

  if (matchingCustomers.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 6;
    cell.textContent = "No customers match your search.";
    row.append(cell);
    customerTableBody.append(row);
    return;
  }

  for (const customer of matchingCustomers) {
    const row = document.createElement("tr");
    const nameCell = document.createElement("td");
    const emailCell = document.createElement("td");
    const tierCell = document.createElement("td");
    const pointsCell = document.createElement("td");
    const statusCell = document.createElement("td");
    const actionCell = document.createElement("td");
    const statusBadge = document.createElement("span");
    const actions = document.createElement("div");

    nameCell.textContent = customer.full_name;
    emailCell.textContent = customer.email;
    tierCell.textContent = customer.loyalty?.tier || "Bronze";
    pointsCell.textContent = (customer.loyalty?.points_balance || 0).toLocaleString("en-AU");

    statusBadge.className = customer.is_active === 1
      ? "statusBadge statusBadge--active"
      : "statusBadge statusBadge--disabled";
    statusBadge.textContent = customer.is_active === 1 ? "Active" : "Disabled";
    statusCell.append(statusBadge);

    actions.className = "tableActions";
    actions.append(createActionButton(
      "Adjust points",
      "actionButton",
      () => openLoyaltyForm(customer)
    ));
    actions.append(createActionButton(
      "Edit",
      "actionButton",
      () => openEditForm(customer)
    ));

    if (customer.is_active === 1) {
      actions.append(createActionButton(
        "Disable",
        "actionButton actionButton--danger",
        () => disableCustomer(customer)
      ));
    } else {
      actions.append(createActionButton(
        "Reactivate",
        "actionButton",
        () => reactivateCustomer(customer)
      ));
    }

    actionCell.append(actions);
    row.append(nameCell, emailCell, tierCell, pointsCell, statusCell, actionCell);
    customerTableBody.append(row);
  }
}


async function openLoyaltyForm(customer) {
  loyaltyAdjustmentForm.reset();
  loyaltyCustomerId.value = customer.id;
  document.querySelector("#loyaltyCustomerName").textContent = (
    `${customer.full_name} currently has ${customer.loyalty?.points_balance || 0} points.`
  );
  loyaltyAdjustmentPanel.hidden = false;
  loyaltyAdjustmentPanel.scrollIntoView({ behavior: "smooth", block: "start" });

  try {
    const result = await authRequest(
      `/api/admin/loyalty/${customer.id}/history`
    );
    renderLoyaltyHistory(result.transactions);
    document.querySelector("#pointsChange").focus();
  } catch (error) {
    showMessage(error.message);
  }
}


function openCreateForm() {
  customerForm.reset();
  customerIdInput.value = "";
  customerPasswordField.hidden = false;
  customerPassword.required = true;
  document.querySelector("#customerFormTitle").textContent = "Create customer";
  customerFormPanel.hidden = false;
  document.querySelector("#customerName").focus();
}


function openEditForm(customer) {
  customerForm.reset();
  customerIdInput.value = customer.id;
  customerPassword.value = "";
  customerPassword.required = false;
  customerPasswordField.hidden = true;
  document.querySelector("#customerFormTitle").textContent = "Edit customer";
  customerFormPanel.hidden = false;
  customerNameInput.value = customer.full_name;
  customerEmailInput.value = customer.email;
  customerFormPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}


async function loadCustomers() {
  const [customerResult, loyaltyResult] = await Promise.all([
    authRequest("/api/admin/customers"),
    authRequest("/api/admin/loyalty"),
  ]);
  loyaltyAccounts = loyaltyResult.loyalty_accounts;
  const loyaltyByUserId = new Map(
    loyaltyAccounts.map((loyalty) => [loyalty.user_id, loyalty])
  );
  customers = customerResult.users.map((customer) => ({
    ...customer,
    loyalty: loyaltyByUserId.get(customer.id),
  }));
  updateSummary();
  renderCustomers();
}


async function disableCustomer(customer) {
  const confirmed = window.confirm(
    `Disable ${customer.full_name}'s account? They will no longer be able to sign in.`
  );

  if (!confirmed) {
    return;
  }

  try {
    await authRequest(`/api/admin/customers/${customer.id}`, {
      method: "DELETE",
    });
    await loadCustomers();
    showMessage("Customer account disabled.", true);
  } catch (error) {
    showMessage(error.message);
  }
}


async function reactivateCustomer(customer) {
  try {
    await authRequest(`/api/admin/customers/${customer.id}`, {
      method: "PUT",
      body: JSON.stringify({ is_active: 1 }),
    });
    await loadCustomers();
    showMessage("Customer account reactivated.", true);
  } catch (error) {
    showMessage(error.message);
  }
}


customerForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const customerId = customerIdInput.value;
  const payload = {
    full_name: customerNameInput.value,
    email: customerEmailInput.value,
  };

  if (!customerId) {
    payload.password = customerPassword.value;
  }

  try {
    await authRequest(
      customerId
        ? `/api/admin/customers/${customerId}`
        : "/api/admin/customers",
      {
        method: customerId ? "PUT" : "POST",
        body: JSON.stringify(payload),
      }
    );
    customerFormPanel.hidden = true;
    await loadCustomers();
    showMessage(customerId ? "Customer updated." : "Customer created.", true);
  } catch (error) {
    showMessage(error.message);
  }
});


loyaltyAdjustmentForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const customerId = loyaltyCustomerId.value;
  const pointsChange = Number(pointsChangeInput.value);
  const reason = pointsReasonInput.value.trim();
  const customer = customers.find((item) => String(item.id) === customerId);

  if (!Number.isInteger(pointsChange) || pointsChange === 0) {
    showMessage("Enter a whole number other than zero.");
    return;
  }

  const actionText = pointsChange > 0
    ? `Add ${pointsChange} points to ${customer.full_name}?`
    : `Remove ${Math.abs(pointsChange)} points from ${customer.full_name}?`;

  if (!window.confirm(actionText)) {
    return;
  }

  try {
    await authRequest(`/api/admin/loyalty/${customerId}/adjustments`, {
      method: "POST",
      body: JSON.stringify({
        points_change: pointsChange,
        reason,
      }),
    });
    loyaltyAdjustmentPanel.hidden = true;
    await loadCustomers();
    showMessage("Loyalty points updated.", true);
  } catch (error) {
    showMessage(error.message);
  }
});


document.querySelector("#newCustomerButton").addEventListener("click", openCreateForm);
document.querySelector("#cancelCustomerButton").addEventListener("click", () => {
  customerFormPanel.hidden = true;
});
document.querySelector("#cancelLoyaltyButton").addEventListener("click", () => {
  loyaltyAdjustmentPanel.hidden = true;
});
customerSearch.addEventListener("input", renderCustomers);
async function startAdminPage() {
  try {
    const sessionResult = await authRequest("/api/session");

    if (sessionResult.user.role !== "admin") {
      window.location.replace("customer.html");
      return;
    }

    document.querySelector("#userGreeting").textContent = (
      `Signed in as ${sessionResult.user.full_name}.`
    );
    await loadCustomers();
  } catch (error) {
    if (error.status === 401 || error.status === 403) {
      window.location.replace("index.html");
      return;
    }
    showMessage(error.message);
  }
}


startAdminPage();
