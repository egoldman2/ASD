const MCP_STATUS_URL = "http://localhost:5000/api/chufeng/mcp/status";
const MCP_TOOLS_URL = "http://localhost:5000/api/chufeng/mcp/tools";
const MCP_CALL_URL = "http://localhost:5000/api/chufeng/mcp/tools/call";

const statusDot = document.querySelector("#mcpStatusDot");
const statusTitle = document.querySelector("#mcpStatusTitle");
const statusMessage = document.querySelector("#mcpStatusMessage");
const toolCount = document.querySelector("#mcpToolCount");
const refreshButton = document.querySelector("#refreshMcpButton");
const toolButtons = [...document.querySelectorAll(".mcpToolButton")];
const toolPanels = [...document.querySelectorAll(".mcpToolPanel")];
const toolForms = [...document.querySelectorAll(".mcpForm")];
const resultSection = document.querySelector("#mcpResultSection");
const resultStatus = document.querySelector("#mcpResultStatus");
const friendlyResult = document.querySelector("#mcpFriendlyResult");
const evidenceTool = document.querySelector("#mcpEvidenceTool");
const requestOutput = document.querySelector("#mcpRequestOutput");
const responseOutput = document.querySelector("#mcpResponseOutput");
const cartItems = document.querySelector("#mcpCartItems");
const addCartItemButton = document.querySelector("#addMcpCartItem");
const mcpModeToggle = document.querySelector("#mcpModeToggle");
const mcpModeState = document.querySelector("#mcpModeState");
const mcpWorkspace = document.querySelector(".mcpWorkspace");

const MCP_MODE_STORAGE_KEY = "chufeng_mcp_mode_enabled";
let cartRowSequence = 0;

function isMcpModeEnabled() {
  return mcpModeToggle.checked;
}

function requestHeaders(includeJson = false) {
  const headers = { "X-MCP-Mode": isMcpModeEnabled() ? "on" : "off" };
  if (includeJson) headers["Content-Type"] = "application/json";
  return headers;
}

function formatCurrency(value) {
  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency: "AUD",
  }).format(value);
}

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    throw new Error(`The backend returned an invalid response (${response.status}).`);
  }
}

function setConnectionState(state, title, message, count = 0) {
  statusDot.className = `mcpStatusDot mcpStatusDot--${state}`;
  statusTitle.textContent = title;
  statusMessage.textContent = message;
  toolCount.textContent = `${count} ${count === 1 ? "tool" : "tools"}`;
}

async function loadMcpStatus() {
  if (!isMcpModeEnabled()) {
    setConnectionState(
      "offline",
      "MCP mode disabled",
      "Enable MCP mode to check the connection and run tools.",
    );
    return;
  }

  refreshButton.disabled = true;
  refreshButton.textContent = "Checking...";
  setConnectionState("checking", "Checking MCP status...", "Contacting the Chufeng backend.");

  try {
    const statusResponse = await fetch(MCP_STATUS_URL, {
      headers: requestHeaders(),
    });
    const status = await readJson(statusResponse);
    if (!statusResponse.ok || status.success !== true) {
      throw new Error(status.error?.message || "Unable to check MCP status.");
    }

    if (!status.enabled) {
      setConnectionState(
        "offline",
        "MCP integration disabled",
        status.error?.message || "Enable MCP in the backend configuration.",
      );
      return;
    }
    if (!status.available) {
      setConnectionState(
        "offline",
        "MCP server unavailable",
        status.error?.message || "Start the local shared MCP server and try again.",
      );
      return;
    }

    const toolsResponse = await fetch(MCP_TOOLS_URL, {
      headers: requestHeaders(),
    });
    const tools = await readJson(toolsResponse);
    if (!toolsResponse.ok || tools.success !== true) {
      throw new Error(tools.error?.message || "Unable to load MCP tools.");
    }
    setConnectionState(
      "online",
      "MCP connected",
      "Live read-only catalogue tools are ready.",
      tools.count,
    );
  } catch (error) {
    console.error("Unable to check MCP status:", error);
    setConnectionState("offline", "MCP connection failed", error.message);
  } finally {
    refreshButton.disabled = false;
    refreshButton.textContent = "Refresh status";
  }
}

function selectToolPanel(panelId) {
  toolButtons.forEach((button) => {
    const selected = button.dataset.toolPanel === panelId;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-selected", String(selected));
  });
  toolPanels.forEach((panel) => {
    panel.hidden = panel.id !== panelId;
  });
}

function integerValue(formData, name) {
  const value = Number(formData.get(name));
  if (!Number.isInteger(value)) {
    throw new Error(`${name.replaceAll("_", " ")} must be a whole number.`);
  }
  return value;
}

function argumentsForForm(form) {
  const formData = new FormData(form);
  const tool = form.dataset.mcpTool;

  if (tool === "chufeng_search_products") {
    return {
      query: String(formData.get("query") || "").trim(),
      limit: integerValue(formData, "limit"),
    };
  }

  if (tool === "chufeng_get_product_details") {
    return { product_id: integerValue(formData, "product_id") };
  }

  if (tool === "chufeng_check_product_stock") {
    return {
      product_id: integerValue(formData, "product_id"),
      quantity: integerValue(formData, "quantity"),
    };
  }

  const items = [...cartItems.querySelectorAll(".mcpCartRow")].map((row) => ({
    product_id: Number(row.querySelector("[data-cart-product]").value),
    quantity: Number(row.querySelector("[data-cart-quantity]").value),
  }));
  if (items.some((item) => !Number.isInteger(item.product_id) || !Number.isInteger(item.quantity))) {
    throw new Error("Every cart row requires a whole product ID and quantity.");
  }
  return { items };
}

function productSummary(product) {
  const article = document.createElement("article");
  article.className = "mcpProductResult";
  const heading = document.createElement("h3");
  heading.textContent = product.name;
  const details = document.createElement("p");
  details.textContent = `${product.category} · ${formatCurrency(product.price)} · ${product.stock_quantity} in stock`;
  const description = document.createElement("p");
  description.textContent = product.description || "No description available.";
  article.append(heading, details, description);
  return article;
}

function renderFriendlyResult(tool, payload) {
  friendlyResult.replaceChildren();
  const result = payload.result;

  if (tool === "chufeng_search_products") {
    if (!result.products.length) {
      friendlyResult.textContent = "No products matched those filters.";
      return;
    }
    friendlyResult.append(...result.products.map(productSummary));
    return;
  }
  if (tool === "chufeng_get_product_details") {
    friendlyResult.append(productSummary(result.product));
    return;
  }
  if (tool === "chufeng_check_product_stock") {
    const heading = document.createElement("h3");
    heading.textContent = result.available ? "Requested stock is available" : "Not enough stock";
    const description = document.createElement("p");
    description.textContent = result.available
      ? `${result.product_name} has ${result.available_quantity} units available.`
      : `${result.product_name} has ${result.available_quantity} units available and is short by ${result.shortfall}.`;
    friendlyResult.append(heading, description);
    return;
  }

  const heading = document.createElement("h3");
  heading.textContent = `Proposed total: ${formatCurrency(result.total)}`;
  const availability = document.createElement("p");
  availability.textContent = result.all_items_available
    ? "All proposed items are currently available."
    : "One or more proposed items do not have enough stock.";
  const list = document.createElement("ul");
  result.items.forEach((item) => {
    const line = document.createElement("li");
    line.textContent = `${item.product_name} × ${item.quantity}: ${formatCurrency(item.subtotal)}`;
    list.append(line);
  });
  friendlyResult.append(heading, availability, list);
}

function showToolResult(tool, argumentsObject, payload, ok) {
  resultSection.hidden = false;
  evidenceTool.textContent = tool;
  requestOutput.textContent = JSON.stringify({ tool, arguments: argumentsObject }, null, 2);
  responseOutput.textContent = JSON.stringify(payload, null, 2);
  resultStatus.textContent = ok ? "Verified live result" : "Request failed";
  resultStatus.className = `mcpResultStatus ${ok ? "mcpResultStatus--success" : "mcpResultStatus--error"}`;

  if (ok && payload.success === true) {
    renderFriendlyResult(tool, payload);
  } else {
    friendlyResult.textContent = payload.error?.message || "The MCP request failed.";
  }
  resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function callMcpTool(form) {
  const tool = form.dataset.mcpTool;
  const submitButton = form.querySelector("button[type='submit']");
  let argumentsObject;

  if (!isMcpModeEnabled()) {
    showToolResult(
      tool,
      {},
      {
        error: {
          code: "MCP_DISABLED",
          message: "Enable MCP mode before running a tool.",
        },
      },
      false,
    );
    return;
  }

  try {
    argumentsObject = argumentsForForm(form);
  } catch (error) {
    showToolResult(tool, {}, { error: { message: error.message } }, false);
    return;
  }

  submitButton.disabled = true;
  const originalText = submitButton.textContent;
  submitButton.textContent = "Calling MCP...";

  try {
    const response = await fetch(MCP_CALL_URL, {
      method: "POST",
      headers: requestHeaders(true),
      body: JSON.stringify({ tool, arguments: argumentsObject }),
    });
    const payload = await readJson(response);
    showToolResult(tool, argumentsObject, payload, response.ok && payload.success === true);
  } catch (error) {
    console.error("Unable to call MCP tool:", error);
    showToolResult(tool, argumentsObject, { error: { message: error.message } }, false);
  } finally {
    submitButton.disabled = !isMcpModeEnabled();
    submitButton.textContent = originalText;
  }
}

function renderMcpMode() {
  const enabled = isMcpModeEnabled();
  mcpModeState.textContent = enabled ? "ON" : "OFF";
  mcpModeState.classList.toggle("mcpModeState--on", enabled);
  mcpModeState.classList.toggle("mcpModeState--off", !enabled);
  mcpWorkspace.classList.toggle("mcpWorkspace--disabled", !enabled);
  mcpWorkspace.setAttribute("aria-disabled", String(!enabled));

  toolButtons.forEach((button) => {
    button.disabled = !enabled;
  });
  toolForms.forEach((form) => {
    form.querySelectorAll("input, button").forEach((control) => {
      control.disabled = !enabled;
    });
  });
  refreshButton.disabled = !enabled;

  if (!enabled) {
    setConnectionState(
      "offline",
      "MCP mode disabled",
      "Enable MCP mode to check the connection and run tools.",
    );
  }
}

function loadMcpMode() {
  const savedMode = localStorage.getItem(MCP_MODE_STORAGE_KEY);
  mcpModeToggle.checked = savedMode === null ? true : savedMode === "true";
  renderMcpMode();
}

function addCartRow(productId = "", quantity = "1") {
  cartRowSequence += 1;
  const row = document.createElement("div");
  row.className = "mcpCartRow";

  const productLabel = document.createElement("label");
  productLabel.setAttribute("for", `mcpCartProduct${cartRowSequence}`);
  productLabel.textContent = "Product ID";
  const productInput = document.createElement("input");
  productInput.id = `mcpCartProduct${cartRowSequence}`;
  productInput.type = "number";
  productInput.min = "1";
  productInput.step = "1";
  productInput.required = true;
  productInput.value = productId;
  productInput.dataset.cartProduct = "";

  const quantityLabel = document.createElement("label");
  quantityLabel.setAttribute("for", `mcpCartQuantity${cartRowSequence}`);
  quantityLabel.textContent = "Quantity";
  const quantityInput = document.createElement("input");
  quantityInput.id = `mcpCartQuantity${cartRowSequence}`;
  quantityInput.type = "number";
  quantityInput.min = "1";
  quantityInput.max = "99";
  quantityInput.step = "1";
  quantityInput.required = true;
  quantityInput.value = quantity;
  quantityInput.dataset.cartQuantity = "";

  const removeButton = document.createElement("button");
  removeButton.type = "button";
  removeButton.className = "mcpRemoveButton";
  removeButton.textContent = "Remove";
  removeButton.addEventListener("click", () => {
    if (cartItems.children.length > 1) row.remove();
  });

  productLabel.append(productInput);
  quantityLabel.append(quantityInput);
  row.append(productLabel, quantityLabel, removeButton);
  cartItems.append(row);
}

toolButtons.forEach((button) => {
  button.addEventListener("click", () => selectToolPanel(button.dataset.toolPanel));
});
toolForms.forEach((form) => {
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    callMcpTool(form);
  });
});
refreshButton.addEventListener("click", loadMcpStatus);
addCartItemButton.addEventListener("click", () => addCartRow());
mcpModeToggle.addEventListener("change", () => {
  localStorage.setItem(MCP_MODE_STORAGE_KEY, String(isMcpModeEnabled()));
  renderMcpMode();
  if (isMcpModeEnabled()) loadMcpStatus();
});

addCartRow("1", "2");
addCartRow("5", "1");
loadMcpMode();
if (isMcpModeEnabled()) loadMcpStatus();
