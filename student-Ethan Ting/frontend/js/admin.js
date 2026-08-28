const AUTH_API_URL = "http://localhost:6002";

const customerTableBody = document.querySelector("#customerTableBody");
const customerFormPanel = document.querySelector("#customerFormPanel");
const customerForm = document.querySelector("#customerForm");
const customerPasswordField = document.querySelector("#customerPasswordField");
const customerPassword = document.querySelector("#customerPassword");
const customerSearch = document.querySelector("#customerSearch");
const adminMessage = document.querySelector("#adminMessage");

let customers = [];


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
    cell.colSpan = 4;
    cell.textContent = "No customers match your search.";
    row.append(cell);
    customerTableBody.append(row);
    return;
  }

  for (const customer of matchingCustomers) {
    const row = document.createElement("tr");
    const nameCell = document.createElement("td");
    const emailCell = document.createElement("td");
    const statusCell = document.createElement("td");
    const actionCell = document.createElement("td");
    const statusBadge = document.createElement("span");
    const actions = document.createElement("div");

    nameCell.textContent = customer.full_name;
    emailCell.textContent = customer.email;

    statusBadge.className = customer.is_active === 1
      ? "statusBadge statusBadge--active"
      : "statusBadge statusBadge--disabled";
    statusBadge.textContent = customer.is_active === 1 ? "Active" : "Disabled";
    statusCell.append(statusBadge);

    actions.className = "tableActions";
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
    row.append(nameCell, emailCell, statusCell, actionCell);
    customerTableBody.append(row);
  }
}


function openCreateForm() {
  customerForm.reset();
  customerForm.elements.customerId.value = "";
  customerPasswordField.hidden = false;
  customerPassword.required = true;
  document.querySelector("#customerFormTitle").textContent = "Create customer";
  customerFormPanel.hidden = false;
  document.querySelector("#customerName").focus();
}


function openEditForm(customer) {
  customerForm.elements.customerId.value = customer.id;
  customerForm.elements.full_name.value = customer.full_name;
  customerForm.elements.email.value = customer.email;
  customerPassword.value = "";
  customerPassword.required = false;
  customerPasswordField.hidden = true;
  document.querySelector("#customerFormTitle").textContent = "Edit customer";
  customerFormPanel.hidden = false;
  customerFormPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}


async function loadCustomers() {
  const result = await authRequest("/api/admin/customers");
  customers = result.users;
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

  const customerId = customerForm.elements.customerId.value;
  const payload = {
    full_name: customerForm.elements.full_name.value,
    email: customerForm.elements.email.value,
  };

  if (!customerId) {
    payload.password = customerForm.elements.password.value;
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


document.querySelector("#newCustomerButton").addEventListener("click", openCreateForm);
document.querySelector("#cancelCustomerButton").addEventListener("click", () => {
  customerFormPanel.hidden = true;
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
