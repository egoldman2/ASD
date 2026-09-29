(function () {
  "use strict";

  const API_ORIGIN = "http://localhost:8102";
  const MCP_STATUS_API = `${API_ORIGIN}/api/inventory/mcp/status`;
  const MCP_CALL_API = `${API_ORIGIN}/api/inventory/mcp/tools/call`;

  const statusLine = document.getElementById("mcpStatusLine");
  const toolSelect = document.getElementById("mcpToolSelect");
  const argLabel = document.getElementById("mcpArgLabel");
  const argInput = document.getElementById("mcpArgInput");
  const callButton = document.getElementById("mcpCallButton");
  const output = document.getElementById("mcpOutput");

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  const TOOL_ARGS = {
    ryan_get_low_stock_items: ["limit"],
    ryan_get_product_inventory: ["product_id"],
    ryan_get_supplier_details: ["supplier_id"],
    ryan_calculate_restock_order: ["product_id"],
  };

  const ARG_LABELS = {
    limit: "Limit",
    product_id: "Product ID",
    supplier_id: "Supplier ID",
  };

  const ARG_DEFAULTS = {
    limit: 20,
    product_id: "",
    supplier_id: "",
  };

  function currentArgKey(tool) {
    return (TOOL_ARGS[tool] || [])[0] || "limit";
  }

  function showArgFieldsFor(tool) {
    const key = currentArgKey(tool);
    argLabel.textContent = ARG_LABELS[key];
    argInput.value = ARG_DEFAULTS[key];
    argInput.min = 1;
    argInput.max = key === "limit" ? 50 : "";
  }

  function collectArguments(tool) {
    const key = currentArgKey(tool);
    const value = Number(argInput.value);
    const args = {};
    if (Number.isFinite(value)) args[key] = value;
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

  function humanSummary(payload) {
    if (!payload || payload.success !== true || !payload.result) return null;

    const tool = payload.tool;
    const result = payload.result;

    if (tool === "ryan_get_low_stock_items") {
      return `${result.count} product(s) need reordering.`;
    }
    if (tool === "ryan_get_product_inventory" && result.product) {
      const p = result.product;
      return p.needs_reorder
        ? `${p.name} needs reordering: ${p.stock_quantity} in stock, threshold ${p.reorder_threshold}.`
        : `${p.name} is adequately stocked: ${p.stock_quantity} in stock, threshold ${p.reorder_threshold}.`;
    }
    if (tool === "ryan_get_supplier_details" && result.supplier) {
      return `${result.supplier.name} supplies ${result.product_count} product(s).`;
    }
    if (tool === "ryan_calculate_restock_order") {
      return result.needs_reorder
        ? `Suggested order: ${result.suggested_order_quantity} unit(s) of ${result.product_name} for AUD ${result.estimated_order_cost}.`
        : `${result.product_name} does not currently need a restock order.`;
    }
    return null;
  }

  function buildTable(headers, rows) {
    const thead =
      "<tr>" + headers.map((h) => `<th>${escapeHtml(h)}</th>`).join("") + "</tr>";
    const tbody = rows
      .map(
        (row) =>
          "<tr>" +
          row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("") +
          "</tr>"
      )
      .join("");
    return `<table class="stockTable"><thead>${thead}</thead><tbody>${tbody}</tbody></table>`;
  }

  function resultTableHtml(payload) {
    if (!payload || payload.success !== true || !payload.result) return "";
    const tool = payload.tool;
    const result = payload.result;

    if (tool === "ryan_get_low_stock_items" && Array.isArray(result.products)) {
      const headers = ["Product", "Stock", "Threshold", "Reorder Qty", "Supplier"];
      const rows = result.products.map((p) => [
        p.name,
        p.stock_quantity,
        p.reorder_threshold,
        p.reorder_quantity,
        p.supplier_name,
      ]);
      return buildTable(headers, rows);
    }

    if (tool === "ryan_get_product_inventory" && result.product) {
      const p = result.product;
      return buildTable(
        ["Field", "Value"],
        [
          ["Name", p.name],
          ["Category", p.category],
          ["Status", p.status],
          ["Stock", p.stock_quantity],
          ["Reorder Threshold", p.reorder_threshold],
          ["Reorder Quantity", p.reorder_quantity],
          ["Needs Reorder", p.needs_reorder],
          ["Supplier", p.supplier_name],
          ["Last Restocked", p.last_restocked_at || "Never"],
        ]
      );
    }

    if (tool === "ryan_get_supplier_details" && result.supplier) {
      const headers = ["Product", "Stock", "Needs Reorder"];
      const rows = (result.products || []).map((p) => [
        p.name,
        p.stock_quantity,
        p.needs_reorder,
      ]);
      return (
        `<p><strong>${escapeHtml(result.supplier.name)}</strong> ` +
        `(${escapeHtml(result.supplier.contact_name || "no contact")})</p>` +
        buildTable(headers, rows)
      );
    }

    if (tool === "ryan_calculate_restock_order") {
      return buildTable(
        ["Field", "Value"],
        [
          ["Product", result.product_name],
          ["Stock", result.stock_quantity],
          ["Needs Reorder", result.needs_reorder],
          ["Suggested Order Qty", result.suggested_order_quantity],
          ["Projected Stock", result.projected_stock_after_order],
          ["Estimated Cost (AUD)", result.estimated_order_cost],
          ["Supplier", result.supplier_name],
        ]
      );
    }

    return "";
  }

  function getOrCreateTableContainer() {
    let container = document.getElementById("mcpResultTable");
    if (!container) {
      container = document.createElement("div");
      container.id = "mcpResultTable";
      output.insertAdjacentElement("afterend", container);
    }
    return container;
  }

  function renderResult(status, payload) {
    if (!output) return;

    const summary = humanSummary(payload);
    const tableHtml = resultTableHtml(payload);
    const structuredJson = JSON.stringify(payload, null, 2);

    let text = "";
    if (payload && payload.success === false && payload.error) {
      text = `[HTTP ${status}] ${payload.error.code}: ${payload.error.message}`;
    } else if (payload && payload.error && !("success" in payload)) {
      // Route-level rejection (MCP_DISABLED, TOOL_NOT_ALLOWED, INVALID_ARGUMENT)
      text = `[HTTP ${status}] ${payload.error.code}: ${payload.error.message}`;
    } else if (summary) {
      text = summary;
    }

    output.value = (text ? text + "\n\n" : "") + "Structured result:\n" + structuredJson;
    getOrCreateTableContainer().innerHTML = tableHtml;
  }

  toolSelect?.addEventListener("change", () => {
    showArgFieldsFor(toolSelect.value);
  });

  callButton?.addEventListener("click", async () => {
    const tool = toolSelect.value;
    const args = collectArguments(tool);

    output.value = "Running...";
    getOrCreateTableContainer().innerHTML = "";
    callButton.disabled = true;

    try {
      const { status, payload } = await callTool(tool, args);
      renderResult(status, payload);
    } catch (err) {
      output.value = "The MCP request failed. Is the backend reachable?";
      getOrCreateTableContainer().innerHTML = "";
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