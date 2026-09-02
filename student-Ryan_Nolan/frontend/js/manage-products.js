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
  const stockField = document.getElementById("productStock");
  const supplierField = document.getElementById("productSupplier");
  const reorderThresholdField = document.getElementById("productReorderThreshold");
  const reorderQuantityField = document.getElementById("productReorderQuantity");
  const cancelButton = document.getElementById("cancelProductButton");

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
            <p class="productMeta">Stock: ${escapeHtml(product.stock_quantity)} (reorder at ${escapeHtml(product.reorder_threshold)})</p>
            <p class="productMeta">Supplier: ${escapeHtml(supplierName(product.supplier_id))}</p>
            ${product.description ? `<p class="productDescription">${escapeHtml(product.description)}</p>` : ""}
          </div>
          <div class="productCardActions">
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

  function fillForm(product) {
    productIdField.value = product.id;
    nameField.value = product.name || "";
    categoryField.value = product.category || "";
    descriptionField.value = product.description || "";
    priceField.value = product.price ?? "";
    stockField.value = product.stock_quantity ?? "";
    supplierField.value = product.supplier_id || "";
    reorderThresholdField.value = product.reorder_threshold ?? 10;
    reorderQuantityField.value = product.reorder_quantity ?? 50;
  }

  function resetForm() {
    productForm.reset();
    productIdField.value = "";
    reorderThresholdField.value = 10;
    reorderQuantityField.value = 50;
  }

  async function loadProducts(search, filter) {
    grid.innerHTML = '<p class="productMessage">Loading products...</p>';
    clearNotice();
    try {
      const data = await fetchProducts(search, filter);
      products = Array.isArray(data) ? data : data.products || [];
      renderProducts(products);
    } catch (err) {
      grid.innerHTML = '<p class="productMessage">Could not load products.</p>';
      showNotice(err.message || "Something went wrong loading products.", true);
    }
  }

  async function loadSuppliersForSelect() {
    try {
      const data = await fetchSuppliers();
      suppliers = Array.isArray(data) ? data : data.suppliers || [];
      populateSupplierSelect();
    } catch (err) {
      // Non-fatal: product list still works without the dropdown populated
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

  document.addEventListener("DOMContentLoaded", async () => {
    await loadSuppliersForSelect();
    loadProducts("", "all");
  });
})();