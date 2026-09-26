(function () {
  "use strict";

  const API_ORIGIN = "http://localhost:8102";
  const MCP_STATUS_API = `${API_ORIGIN}/api/inventory/mcp/status`;
  const MCP_CALL_API = `${API_ORIGIN}/api/inventory/mcp/tools/call`;

  const statusLine = document.getElementById("mcpStatusLine");
  const toolSelect = document.getElementById("mcpToolSelect");
  const argLimitField = document.getElementById("mcpArgLimit");
  const argLimitInput = document.getElementById("mcpArgLimitInput");
  const argProductIdField = document.getElementById("mcpArgProductId");
  const argProductIdInput = document.getElementById("mcpArgProductIdInput");
  const argSupplierIdField = document.getElementById("mcpArgSupplierId");
  const argSupplierIdInput = document.getElementById("mcpArgSupplierIdInput");
  const callButton = document.getElementById("mcpCallButton");
  const output = document.getElementById("mcpOutput");

  const TOOL_ARGS = {
    ryan_get_low_stock_items: ["limit"],
    ryan_get_product_inventory: ["product_id"],
    ryan_get_supplier_details: ["supplier_id"],
    ryan_calculate_restock_order: ["product_id"],
  };

  function showArgFieldsFor(tool) {
    const needed = TOOL_ARGS[tool] || [];
    argLimitField.hidden = !needed.includes("limit");
    argProductIdField.hidden = !needed.includes("product_id");
    argSupplierIdField.hidden = !needed.includes("supplier_id");
  }

  function collectArguments(tool) {
    const needed = TOOL_ARGS[tool] || [];
    const args = {};

    if (needed.includes("limit")) {
      const value = Number(argLimitInput.value);
      if (Number.isFinite(value)) args.limit = value;
    }
    if (needed.includes("product_id")) {
      args.product_id = Number(argProductIdInput.value);
    }
    if (needed.includes("supplier_id")) {
      args.supplier_id = Number(argSupplierIdInput.value);
    }
    return args;
  }

  async function refreshStatus() {
    if (!statusLine) return;
    try {
      const response = await fetch(MCP_STATUS_API, {
        method: "GET",
        headers: { Accept: "application/json" },
        credentials: "include",
      });
      const data = await response.json();

      if (!data.enabled) {
        statusLine.textContent = "MCP is disabled in this environment.";
      } else if (!data.available) {
        statusLine.textContent = "MCP server is unreachable right now.";
      } else {
        statusLine.textContent = `MCP connected — ${data.tool_count} tool(s) available.`;
      }
    } catch (err) {
      statusLine.textContent = "Could not check MCP status.";
    }
  }

  async function callTool(tool, args) {
    const response = await fetch(MCP_CALL_API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ tool, arguments: args }),
    });
    const payload = await response.json();
    return { status: response.status, payload };
  }

  function renderResult(status, payload) {
    if (!output) return;
    output.value = JSON.stringify(payload, null, 2);

    if (payload && payload.success === false && payload.error) {
      output.value = `[HTTP ${status}] ${payload.error.code}: ${payload.error.message}\n\n` + output.value;
    } else if (payload && payload.error && !("success" in payload)) {
      // Route-level rejection (MCP_DISABLED, TOOL_NOT_ALLOWED, INVALID_ARGUMENT)
      output.value = `[HTTP ${status}] ${payload.error.code}: ${payload.error.message}\n\n` + output.value;
    }
  }

  toolSelect?.addEventListener("change", () => {
    showArgFieldsFor(toolSelect.value);
  });

  callButton?.addEventListener("click", async () => {
    const tool = toolSelect.value;
    const args = collectArguments(tool);

    output.value = "Running...";
    callButton.disabled = true;

    try {
      const { status, payload } = await callTool(tool, args);
      renderResult(status, payload);
    } catch (err) {
      output.value = "The MCP request failed. Is the backend reachable?";
      console.error("MCP tool call failed:", err);
    } finally {
      callButton.disabled = false;
    }
  });

  document.addEventListener("DOMContentLoaded", () => {
    showArgFieldsFor(toolSelect.value);
    refreshStatus();
  });
})();