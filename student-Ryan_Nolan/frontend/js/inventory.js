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

  const productForm = document.getElementById("productForm");
  const productIdField = document.getElementById("productId");
  const nameField = document.getElementById("productName");
  const categoryField = document.getElementById("productCategory");
  const descriptionField = document.getElementById("productDescription");
  const priceField = document.getElementById("productPrice");
  const unitCostField = document.getElementById("productUnitCost");
  const stockField = document.getElementById("productStock");
  const supplierField = document.getElementById("productSupplier");
  const reorderThresholdField = document.getElementById("productReorderThreshold");
  const reorderQuantityField = document.getElementById("productReorderQuantity");
  const cancelButton = document.getElementById("cancelProductButton");

  const aiForm = document.getElementById("aiForm");
  const aiQuestion = document.getElementById("aiQuestion");
  const aiOutput = document.getElementById("aiOutput");
  const askAiButton = document.getElementById("askAiButton");

  const reorderForm = document.getElementById("reorderForm");
  const reorderProductIdField = document.getElementById("reorderProductId");
  const reorderProductNameDisplay = document.getElementById("reorderProductName");
  const reorderQuantityInput = document.getElementById("reorderQuantityInput");

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

  async function saveProduct(payload, id) {
    const url = id ? `${PRODUCTS_API}/${id}` : PRODUCTS_API;
    const method = id ? "PUT" : "POST";

    const response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Failed to save product (${response.status})`);
    }
    return response.json();
  }

  async function deleteProduct(id) {
    const response = await fetch(`${PRODUCTS_API}/${id}`, { method: "DELETE" });
    if (!response.ok) {
      throw new Error(`Failed to delete product (${response.status})`);
    }
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
        const belowThreshold = product.stock_quantity <= product.reorder_threshold;
        const outOfStock = product.stock_quantity <= 0;
        const suggestedReorder = product.reorder_quantity - product.stock_quantity;
        const bufferRemaining = product.stock_quantity - product.reorder_threshold;

        return `
        <article class="productCard" data-id="${product.id}">
          <div class="productCardBody">
            <div class="productCardHeader">
              <h3 class="productName">${escapeHtml(product.name)}</h3>
              ${stockBadge(product)}
            </div>
            <p class="productMeta">${escapeHtml(product.category)} &middot; ${formatCurrency(product.price)}</p>
            <p class="productMeta">Unit Cost: ${formatCurrency(product.unit_cost)}</p>
            <p class="productMeta">Supplier: ${escapeHtml(supplierName(product.supplier_id))}</p>
            <p class="productMeta">${escapeHtml(formatDate(product.last_restocked_at))}<br></p>

            ${product.description ? `<p class="productDescription">${escapeHtml(product.description)}</p>` : ""}

            <table class="stockTable">
              <thead>
                <tr>
                  <th>Current</th>
                  <th>Reorder At</th>
                  <th>Target</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>${escapeHtml(product.stock_quantity)}</td>
                  <td>${escapeHtml(product.reorder_threshold)}</td>
                  <td>${escapeHtml(product.reorder_quantity)}</td>
                </tr>
              </tbody>
            </table>

            ${outOfStock
              ? `<p class="productMeta priorityReorderNotice">Priority Reorder: ${escapeHtml(suggestedReorder)} units (${formatCurrency(suggestedReorder * product.unit_cost)})</p>`
              : belowThreshold
                ? `<p class="productMeta reorderNotice">Suggested reorder: ${escapeHtml(suggestedReorder)} units (${formatCurrency(suggestedReorder * product.unit_cost)})</p>`
                : `<p class="productMeta inStockNotice">Reorder In: ${escapeHtml(bufferRemaining)} units</p>`}

          </div>
          <div class="productCardActions">
            <button type="button" class="filterButton reorderProductButton${outOfStock ? " reorderProductButton--urgent" : belowThreshold ? " reorderProductButton--due" : ""}" data-id="${product.id}">Reorder</button>
            <button type="button" class="filterButton editProductButton" data-id="${product.id}">Edit</button>
            <button type="button" class="filterButton deleteProductButton" data-id="${product.id}">Delete</button>
          </div>
        </article>
      `;
      })
      .join("");
  }

  function populateSupplierSelect() {
    if (!supplierField) return;

    const current = supplierField.value;
    supplierField.innerHTML =
      '<option value="">Unassigned</option>' +
      suppliers.map((s) => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join("");
    supplierField.value = current;
  }

  function fillReorderForm(product) {
    if (!reorderForm) return;
    reorderProductIdField.value = product.id;
    reorderProductNameDisplay.textContent = product.name;

    const suggested = Math.max(product.reorder_quantity - product.stock_quantity, 1);
    reorderQuantityInput.value = suggested;
    reorderUnitCost = product.unit_cost || 0;
    updateReorderCostDisplay();

    const detailsEl = reorderForm.closest("details");
    if (detailsEl) detailsEl.open = true;
  }

  function fillForm(product) {
    if (!productForm) return;

    productIdField.value = product.id;
    nameField.value = product.name || "";
    categoryField.value = product.category || "";
    descriptionField.value = product.description || "";
    priceField.value = product.price ?? "";

    if (unitCostField) unitCostField.value = product.unit_cost ?? "";

    stockField.value = product.stock_quantity ?? "";
    supplierField.value = product.supplier_id || "";
    reorderThresholdField.value = product.reorder_threshold ?? 10;
    reorderQuantityField.value = product.reorder_quantity ?? 50;

    const detailsEl = productForm.closest("details");
    if (detailsEl) detailsEl.open = true;
  }

  function resetForm() {
    if (!productForm) return;
      productForm.reset();
      productIdField.value = "";
      reorderThresholdField.value = 10;
      reorderQuantityField.value = 50;
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

  async function loadSuppliersForSelect() {
    try {
      const data = await fetchSuppliers();
      suppliers = Array.isArray(data) ? data : data.suppliers || [];
      populateSupplierSelect();
    } catch (err) {
      // Non-fatal: product list/cards still work without the dropdown populated
      console.error("Could not load suppliers for dropdown:", err);
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

  productForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearNotice();

    const payload = {
      name: nameField.value.trim(),
      category: categoryField.value.trim(),
      description: descriptionField.value.trim() || null,
      price: Number(priceField.value),
      unit_cost: unitCostField ? Number(unitCostField.value) || 0 : 0,
      stock_quantity: Number(stockField.value),
      supplier_id: supplierField.value || null,
      reorder_threshold: Number(reorderThresholdField.value) || 0,
      reorder_quantity: Number(reorderQuantityField.value) || 0,
    };

    if (!payload.name || !payload.category) {
      showNotice("Product name and category are required.", true);
      return;
    }
    if (!Number.isFinite(payload.price) || payload.price < 0) {
      showNotice("Enter a valid, non-negative price.", true);
      return;
    }
    if (!Number.isFinite(payload.stock_quantity) || payload.stock_quantity < 0) {
      showNotice("Enter a valid, non-negative stock quantity.", true);
      return;
    }

    const id = productIdField.value || null;

    try {
      await saveProduct(payload, id);
      showNotice(id ? "Product updated." : "Product added.", false);
      resetForm();
      loadProducts(currentSearch, currentFilter);
    } catch (err) {
      showNotice(err.message || "Could not save product.", true);
    }
  });

  cancelButton?.addEventListener("click", () => {
    resetForm();
    clearNotice();
  });

  grid?.addEventListener("click", async (event) => {
    const editBtn = event.target.closest(".editProductButton");
    const deleteBtn = event.target.closest(".deleteProductButton");
    const reorderBtn = event.target.closest(".reorderProductButton");

    if (reorderBtn) {
      const id = reorderBtn.dataset.id;
      const product = products.find((p) => String(p.id) === String(id));
      if (product) {
        fillReorderForm(product);
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
      return;
    }

    if (editBtn) {
      const id = editBtn.dataset.id;
      const product = products.find((p) => String(p.id) === String(id));
      if (product) {
        fillForm(product);
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
      return;
    }

    if (deleteBtn) {
      const id = deleteBtn.dataset.id;
      const confirmed = window.confirm("Delete this product?");
      if (!confirmed) return;

      try {
        await deleteProduct(id);
        showNotice("Product deleted.", false);
        loadProducts(currentSearch, currentFilter);
      } catch (err) {
        showNotice(err.message || "Could not delete product.", true);
      }
    }
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

  reorderForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearNotice();

    const id = reorderProductIdField.value;
    const product = products.find((p) => String(p.id) === String(id));
    if (!product) {
      showNotice("Could not find that product.", true);
      return;
    }

    const amount = Number(reorderQuantityInput.value);
    if (!Number.isFinite(amount) || amount <= 0) {
      showNotice("Enter a valid quantity greater than zero.", true);
      return;
    }

    const payload = {
      name: product.name,
      category: product.category,
      description: product.description,
      price: product.price,
      unit_cost: product.unit_cost,
      stock_quantity: product.stock_quantity + amount,
      supplier_id: product.supplier_id,
      reorder_threshold: product.reorder_threshold,
      reorder_quantity: product.reorder_quantity,
    };

  try {
    await saveProduct(payload, id);
    showNotice(`${product.name} restocked (+${amount} units).`, false);
    reorderForm.reset();
    reorderProductNameDisplay.textContent = "";
    reorderCostDisplay.textContent = "";
    reorderUnitCost = 0;
    loadProducts(currentSearch, currentFilter);
  } catch (err) {
    showNotice(err.message || "Could not process reorder.", true);
  }
  });

  let reorderUnitCost = 0;

  function updateReorderCostDisplay() {
    if (!reorderCostDisplay) return;
    const qty = Number(reorderQuantityInput.value) || 0;
    reorderCostDisplay.textContent = formatCurrency(qty * reorderUnitCost);
  }

  const reorderCostDisplay = document.getElementById("reorderCostDisplay");
  reorderQuantityInput?.addEventListener("input", updateReorderCostDisplay);

  document.addEventListener("DOMContentLoaded", async () => {
    await loadSuppliersForSelect();
    loadProducts("", "all");
  });
})();