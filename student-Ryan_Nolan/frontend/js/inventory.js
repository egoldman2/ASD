const API_ORIGIN = "http://127.0.0.1:5000";
const PRODUCTS_API = `${API_ORIGIN}/api/inventory/products`;
const SUPPLIERS_API = `${API_ORIGIN}/api/inventory/suppliers`;
const ASSISTANT_API = `${API_ORIGIN}/api/inventory/assistant`;

(function () {
  "use strict";

  const grid = document.getElementById("productGrid");
  const notice = document.getElementById("catalogueNotice");
  const searchForm = document.getElementById("searchForm");
  const searchInput = document.getElementById("searchInput");
  const filterBar = document.querySelector(".filterBar");

  const aiForm = document.getElementById("aiForm");
  const aiQuestion = document.getElementById("aiQuestion");
  const aiOutput = document.getElementById("aiOutput");
  const askAiButton = document.getElementById("askAiButton");

  let products = [];
  let suppliers = [];
  let currentSearch = "";
  let currentFilter = "all";

  function showNotice(message, isError) {
    if (!notice) return;
    notice.textContent = message;
    notice.hidden = false;
    notice.classList.toggle("catalogueNotice--error", Boolean(isError));
  }

  function clearNotice() {
    if (!notice) return;
    notice.hidden = true;
    notice.textContent = "";
  }

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  function formatCurrency(value) {
    const num = Number(value);
    return Number.isFinite(num) ? `$${num.toFixed(2)}` : "";
  }

  function formatDate(value) {
    if (!value) return "Never restocked";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Never restocked";
    return `Last restocked ${date.toLocaleDateString()}`;
  }

  async function fetchProducts(search, filter) {
    const url = new URL(PRODUCTS_API, window.location.origin);
    if (search) url.searchParams.set("search", search);
    if (filter && filter !== "all") url.searchParams.set("filter", filter);

    const response = await fetch(url.toString(), {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      throw new Error(`Failed to load products (${response.status})`);
    }
    return response.json();
  }

  async function fetchSuppliers() {
    const response = await fetch(SUPPLIERS_API, {
      method: "GET",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      throw new Error(`Failed to load suppliers (${response.status})`);
    }
    return response.json();
  }

  async function askAssistant(message) {
    const response = await fetch(ASSISTANT_API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });

    if (!response.ok) {
      throw new Error(`Assistant request failed (${response.status})`);
    }
    return response.json();
  }

  function supplierName(supplierId) {
    const supplier = suppliers.find((s) => String(s.id) === String(supplierId));
    return supplier ? supplier.name : "Unassigned";
  }

  function stockBadge(product) {
    if (product.stock_quantity <= 0) return '<span class="badge badge--out">Out of stock</span>';
    if (product.stock_quantity <= product.reorder_threshold)
      return '<span class="badge badge--low">Low stock</span>';
    return '<span class="badge badge--ok">In stock</span>';
  }

  function renderProducts(list) {
    if (!grid) return;

    if (!list.length) {
      grid.innerHTML = '<p class="productMessage">No products found.</p>';
      return;
    }

    grid.innerHTML = list
      .map((product) => {
        return `
        <article class="productCard" data-id="${product.id}">
          <div class="productCardBody">
            <div class="productCardHeader">
              <h3 class="productName">${escapeHtml(product.name)}</h3>
              ${stockBadge(product)}
            </div>
            <p class="productMeta">${escapeHtml(product.category)} &middot; ${formatCurrency(product.price)}</p>
            <p class="productMeta">Stock: ${escapeHtml(product.stock_quantity)} (reorder at ${escapeHtml(product.reorder_threshold)}, qty ${escapeHtml(product.reorder_quantity)})</p>
            <p class="productMeta">Supplier: ${escapeHtml(supplierName(product.supplier_id))}</p>
            <p class="productMeta">${escapeHtml(formatDate(product.last_restocked_at))}</p>
          </div>
        </article>
      `;
      })
      .join("");
  }

  async function loadProducts(search, filter) {
    grid.innerHTML = '<p class="productMessage">Loading inventory...</p>';
    clearNotice();
    try {
      const data = await fetchProducts(search, filter);
      products = Array.isArray(data) ? data : data.products || [];
      renderProducts(products);
    } catch (err) {
      grid.innerHTML = '<p class="productMessage">Could not load inventory.</p>';
      showNotice(err.message || "Something went wrong loading inventory.", true);
    }
  }

  async function loadSuppliers() {
    try {
      const data = await fetchSuppliers();
      suppliers = Array.isArray(data) ? data : data.suppliers || [];
    } catch (err) {
      // Non-fatal: product cards just show "Unassigned" if this fails
      console.error("Could not load suppliers:", err);
    }
  }

  searchForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    currentSearch = searchInput.value.trim();
    loadProducts(currentSearch, currentFilter);
  });

  filterBar?.addEventListener("click", (event) => {
    const button = event.target.closest(".filterButton[data-filter]");
    if (!button) return;

    filterBar.querySelectorAll(".filterButton").forEach((btn) => btn.classList.remove("active"));
    button.classList.add("active");

    currentFilter = button.dataset.filter;
    loadProducts(currentSearch, currentFilter);
  });

  aiForm?.addEventListener("submit", async (event) => {
    event.preventDefault();

    const message = aiQuestion.value.trim();
    if (!message) return;

    aiOutput.value = "";
    aiOutput.placeholder = "Thinking...";
    askAiButton.disabled = true;

    try {
      const data = await askAssistant(message);
      aiOutput.value = data.reply || data.message || "No response from assistant.";
    } catch (err) {
      aiOutput.value = "";
      aiOutput.placeholder = "The assistant is unavailable right now. Please try again.";
      console.error("Assistant error:", err);
    } finally {
      askAiButton.disabled = false;
    }
  });

  document.addEventListener("DOMContentLoaded", async () => {
    await loadSuppliers();
    loadProducts("", "all");
  });
})();