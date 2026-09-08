const AUTH_API_URL = "http://localhost:6002";

const customerTableBody = document.querySelector("#customerTableBody");
const administratorTableBody = document.querySelector("#administratorTableBody");
const customerFormPanel = document.querySelector("#customerFormPanel");
const customerForm = document.querySelector("#customerForm");
const accountRoleInput = document.querySelector("#accountRole");
const customerPasswordField = document.querySelector("#customerPasswordField");
const customerPassword = document.querySelector("#customerPassword");
const customerSearch = document.querySelector("#customerSearch");
const administratorSearch = document.querySelector("#administratorSearch");
const customerAccountsPanel = document.querySelector("#customerAccountsPanel");
const administratorAccountsPanel = document.querySelector("#administratorAccountsPanel");
const viewCustomersButton = document.querySelector("#viewCustomersButton");
const viewAdministratorsButton = document.querySelector("#viewAdministratorsButton");
const adminMessage = document.querySelector("#adminMessage");
const customerIdInput = document.querySelector("#customerId");
const customerNameInput = document.querySelector("#customerName");
const customerEmailInput = document.querySelector("#customerEmail");
const customerInsightForm = document.querySelector("#customerInsightForm");
const customerInsightQuestion = document.querySelector("#customerInsightQuestion");
const askCustomerInsightButton = document.querySelector("#askCustomerInsightButton");
const customerInsightMessage = document.querySelector("#customerInsightMessage");
const customerInsightResult = document.querySelector("#customerInsightResult");
const customerInsightAnalysis = document.querySelector("#customerInsightAnalysis");
const customerInsightAnswer = document.querySelector("#customerInsightAnswer");
const customerInsightMeta = document.querySelector("#customerInsightMeta");
const customerChangeProposal = document.querySelector("#customerChangeProposal");
const confirmCustomerChangeButton = document.querySelector("#confirmCustomerChangeButton");
const cancelCustomerChangeButton = document.querySelector("#cancelCustomerChangeButton");

let customers = [];
let administrators = [];
let pendingCustomerChange = null;


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


function showCustomerInsightMessage(message, success = false) {
  customerInsightMessage.textContent = message;
  customerInsightMessage.classList.toggle("success", success);
}


function renderCustomerInsight(result) {
  pendingCustomerChange = result.proposal || null;
  customerInsightAnswer.textContent = result.answer;
  customerInsightMeta.textContent = (
    `${result.model} · ${result.customers_analyzed} customer records · Read-only analysis`
  );
  customerInsightAnalysis.hidden = Boolean(pendingCustomerChange);
  customerInsightResult.classList.toggle(
    "aiInsightResult--proposal",
    Boolean(pendingCustomerChange)
  );

  if (pendingCustomerChange) {
    const current = pendingCustomerChange.current;
    const changes = pendingCustomerChange.changes;
    document.querySelector("#proposalCustomerSummary").textContent = (
      `${current.full_name} · ${current.email}`
    );
    const nameRow = document.querySelector("#proposalNameRow");
    const emailRow = document.querySelector("#proposalEmailRow");

    nameRow.hidden = !changes.full_name;
    emailRow.hidden = !changes.email;

    if (changes.full_name) {
      document.querySelector("#proposalCurrentName").textContent = current.full_name;
      document.querySelector("#proposalNewName").textContent = changes.full_name;
    }
    if (changes.email) {
      document.querySelector("#proposalCurrentEmail").textContent = current.email;
      document.querySelector("#proposalNewEmail").textContent = changes.email;
    }

    document.querySelector("#proposalAiMeta").textContent = (
      `${result.model} analysed ${result.customers_analyzed} allow-listed customer records. `
      + "The proposal endpoint did not write to the database."
    );
    customerChangeProposal.hidden = false;
  } else {
    customerChangeProposal.hidden = true;
  }

  customerInsightResult.hidden = false;
}


function cancelCustomerChangeProposal(message = "Change proposal cancelled. Nothing was saved.") {
  pendingCustomerChange = null;
  customerChangeProposal.hidden = true;
  customerInsightResult.hidden = true;
  customerInsightResult.classList.remove("aiInsightResult--proposal");
  showCustomerInsightMessage(message, true);
}


function updateSummary() {
  document.querySelector("#totalCustomers").textContent = customers.length;
  document.querySelector("#activeCustomers").textContent = customers.filter(
    (customer) => customer.is_active === 1
  ).length;
  document.querySelector("#disabledCustomers").textContent = customers.filter(
    (customer) => customer.is_active === 0
  ).length;
  document.querySelector("#totalAdministrators").textContent = administrators.length;
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
    nameCell.dataset.label = "Customer";
    emailCell.dataset.label = "Email";
    statusCell.dataset.label = "Status";
    actionCell.dataset.label = "Actions";

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


function renderAdministrators() {
  const searchTerm = administratorSearch.value.trim().toLowerCase();
  const matchingAdministrators = administrators.filter((administrator) => (
    administrator.full_name.toLowerCase().includes(searchTerm)
    || administrator.email.toLowerCase().includes(searchTerm)
  ));

  administratorTableBody.replaceChildren();

  if (matchingAdministrators.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 4;
    cell.textContent = "No administrators match your search.";
    row.append(cell);
    administratorTableBody.append(row);
    return;
  }

  for (const administrator of matchingAdministrators) {
    const row = document.createElement("tr");
    const nameCell = document.createElement("td");
    const emailCell = document.createElement("td");
    const statusCell = document.createElement("td");
    const actionCell = document.createElement("td");
    const statusBadge = document.createElement("span");
    const actions = document.createElement("div");

    nameCell.textContent = administrator.full_name;
    emailCell.textContent = administrator.email;
    nameCell.dataset.label = "Administrator";
    emailCell.dataset.label = "Email";
    statusCell.dataset.label = "Status";
    actionCell.dataset.label = "Actions";
    statusBadge.className = administrator.is_active === 1
      ? "statusBadge statusBadge--active"
      : "statusBadge statusBadge--disabled";
    statusBadge.textContent = administrator.is_active === 1 ? "Active" : "Disabled";
    statusCell.append(statusBadge);

    actions.className = "tableActions";
    actions.append(createActionButton(
      "Edit",
      "actionButton",
      () => openEditForm(administrator, "admin")
    ));

    actionCell.append(actions);
    row.append(nameCell, emailCell, statusCell, actionCell);
    administratorTableBody.append(row);
  }
}


function openCreateForm(role = "customer") {
  customerForm.reset();
  customerIdInput.value = "";
  accountRoleInput.value = role;
  customerPasswordField.hidden = false;
  customerPassword.required = true;
  const accountType = role === "admin" ? "administrator" : "customer";
  document.querySelector("#accountFormEyebrow").textContent = `${accountType} details`;
  document.querySelector("#customerFormTitle").textContent = `Create ${accountType}`;
  document.querySelector("#saveCustomerButton").textContent = `Save ${accountType}`;
  customerFormPanel.hidden = false;
  document.querySelector("#customerName").focus();
}


function openEditForm(customer, role = "customer") {
  customerForm.reset();
  customerIdInput.value = customer.id;
  accountRoleInput.value = role;
  customerPassword.value = "";
  customerPassword.required = false;
  customerPasswordField.hidden = true;
  const accountType = role === "admin" ? "administrator" : "customer";
  document.querySelector("#accountFormEyebrow").textContent = `${accountType} details`;
  document.querySelector("#customerFormTitle").textContent = `Edit ${accountType}`;
  document.querySelector("#saveCustomerButton").textContent = `Save ${accountType}`;
  customerFormPanel.hidden = false;
  customerNameInput.value = customer.full_name;
  customerEmailInput.value = customer.email;
  customerFormPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}


async function loadCustomers() {
  const [customerResult, administratorResult] = await Promise.all([
    authRequest("/api/admin/customers"),
    authRequest("/api/admin/administrators"),
  ]);
  customers = customerResult.users;
  administrators = administratorResult.users;
  updateSummary();
  renderCustomers();
  renderAdministrators();
}


function showAccountView(role) {
  const showingAdministrators = role === "admin";

  customerAccountsPanel.hidden = showingAdministrators;
  administratorAccountsPanel.hidden = !showingAdministrators;
  viewCustomersButton.classList.toggle("active", !showingAdministrators);
  viewAdministratorsButton.classList.toggle("active", showingAdministrators);
  viewCustomersButton.setAttribute("aria-selected", String(!showingAdministrators));
  viewAdministratorsButton.setAttribute("aria-selected", String(showingAdministrators));
  customerFormPanel.hidden = true;
  showMessage("");
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
  const role = accountRoleInput.value === "admin" ? "admin" : "customer";
  const accountType = role === "admin" ? "Administrator" : "Customer";
  const endpoint = role === "admin" ? "administrators" : "customers";
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
        ? `/api/admin/${endpoint}/${customerId}`
        : `/api/admin/${endpoint}`,
      {
        method: customerId ? "PUT" : "POST",
        body: JSON.stringify(payload),
      }
    );
    customerFormPanel.hidden = true;
    await loadCustomers();
    showMessage(
      customerId ? `${accountType} updated.` : `${accountType} created.`,
      true
    );
  } catch (error) {
    showMessage(error.message);
  }
});


customerInsightForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const question = customerInsightQuestion.value.trim();
  if (!question) {
    customerInsightResult.hidden = true;
    showCustomerInsightMessage("Enter a customer or loyalty question.");
    return;
  }

  askCustomerInsightButton.disabled = true;
  askCustomerInsightButton.textContent = "Analysing...";
  pendingCustomerChange = null;
  customerChangeProposal.hidden = true;
  customerInsightResult.hidden = true;
  showCustomerInsightMessage(
    "Ollama is reviewing the allow-listed customer records...",
    true
  );

  try {
    const result = await authRequest("/api/admin/ai/customer-insight", {
      method: "POST",
      body: JSON.stringify({ question }),
    });
    renderCustomerInsight(result);
    showCustomerInsightMessage(
      result.proposal
        ? ""
        : "Analysis complete. Review the evidence before taking any action.",
      true
    );
  } catch (error) {
    customerInsightResult.hidden = true;
    showCustomerInsightMessage(error.message);
  } finally {
    askCustomerInsightButton.disabled = false;
    askCustomerInsightButton.textContent = "Ask AI";
  }
});


confirmCustomerChangeButton.addEventListener("click", async () => {
  if (!pendingCustomerChange) {
    return;
  }

  confirmCustomerChangeButton.disabled = true;
  confirmCustomerChangeButton.textContent = "Saving...";

  try {
    await authRequest(
      `/api/admin/customers/${pendingCustomerChange.customer_id}`,
      {
        method: "PUT",
        body: JSON.stringify(pendingCustomerChange.changes),
      }
    );
    await loadCustomers();
    pendingCustomerChange = null;
    customerChangeProposal.hidden = true;
    customerInsightResult.hidden = true;
    customerInsightResult.classList.remove("aiInsightResult--proposal");
    showCustomerInsightMessage(
      "Customer changes saved.",
      true
    );
    showMessage("Customer updated from an approved AI proposal.", true);
  } catch (error) {
    showCustomerInsightMessage(error.message);
  } finally {
    confirmCustomerChangeButton.disabled = false;
    confirmCustomerChangeButton.textContent = "Save customer changes";
  }
});


cancelCustomerChangeButton.addEventListener("click", () => {
  cancelCustomerChangeProposal();
});


for (const promptButton of document.querySelectorAll("[data-insight-question]")) {
  promptButton.addEventListener("click", () => {
    customerInsightQuestion.value = promptButton.dataset.insightQuestion;
    customerInsightQuestion.focus();
  });
}


document.querySelector("#newCustomerButton").addEventListener("click", () => {
  openCreateForm("customer");
});
document.querySelector("#newAdministratorButton").addEventListener("click", () => {
  openCreateForm("admin");
});
viewCustomersButton.addEventListener("click", () => showAccountView("customer"));
viewAdministratorsButton.addEventListener("click", () => showAccountView("admin"));
document.querySelector("#cancelCustomerButton").addEventListener("click", () => {
  customerFormPanel.hidden = true;
});
customerSearch.addEventListener("input", renderCustomers);
administratorSearch.addEventListener("input", renderAdministrators);
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
