const API_ORIGIN = "http://127.0.0.1:5000";
const PRODUCTS_API = `${API_ORIGIN}/api/inventory/products`;
const SUPPLIERS_API = `${API_ORIGIN}/api/inventory/suppliers`;
const ASSISTANT_API = `${API_ORIGIN}/api/inventory/assistant`;

(function () {
  "use strict";

  const API_BASE = SUPPLIERS_API;

  const grid = document.getElementById("supplierGrid");
  const notice = document.getElementById("catalogueNotice");
  const searchForm = document.getElementById("searchForm");
  const searchInput = document.getElementById("searchInput");

  const supplierForm = document.getElementById("supplierForm");
  const supplierIdField = document.getElementById("supplierId");
  const nameField = document.getElementById("supplierName");
  const contactField = document.getElementById("supplierContact");
  const emailField = document.getElementById("supplierEmail");
  const phoneField = document.getElementById("supplierPhone");
  const addressField = document.getElementById("supplierAddress");
  const cancelButton = document.getElementById("cancelSupplierButton");

  let suppliers = [];
  let currentSearch = "";

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

  async function fetchSuppliers(search) {
    const url = new URL(API_BASE, window.location.origin);
    if (search) url.searchParams.set("search", search);

    const response = await fetch(url.toString(), {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      throw new Error(`Failed to load suppliers (${response.status})`);
    }
    return response.json();
  }

  async function saveSupplier(payload, id) {
    const url = id ? `${API_BASE}/${id}` : API_BASE;
    const method = id ? "PUT" : "POST";

    const response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Failed to save supplier (${response.status})`);
    }
    return response.json();
  }

  async function deleteSupplier(id) {
    const response = await fetch(`${API_BASE}/${id}`, { method: "DELETE" });
    if (!response.ok) {
      throw new Error(`Failed to delete supplier (${response.status})`);
    }
  }

  function renderSuppliers(list) {
    if (!grid) return;

    if (!list.length) {
      grid.innerHTML = '<p class="productMessage">No suppliers found.</p>';
      return;
    }

    grid.innerHTML = list
      .map((supplier) => {
        const contactLine = [supplier.contact_name, supplier.phone, supplier.email]
          .filter(Boolean)
          .map(escapeHtml)
          .join(" &middot; ");

        return `
        <article class="productCard" data-id="${supplier.id}">
          <div class="productCardBody">
            <h3 class="productName">${escapeHtml(supplier.name)}</h3>
            ${contactLine ? `<p class="productMeta">${contactLine}</p>` : ""}
            ${supplier.address ? `<p class="productDescription">${escapeHtml(supplier.address)}</p>` : ""}
          </div>
          <div class="productCardActions">
            <button type="button" class="filterButton editSupplierButton" data-id="${supplier.id}">Edit</button>
            <button type="button" class="filterButton deleteSupplierButton" data-id="${supplier.id}">Delete</button>
          </div>
        </article>
      `;
      })
      .join("");
  }

  function fillForm(supplier) {
    supplierIdField.value = supplier.id;
    nameField.value = supplier.name || "";
    contactField.value = supplier.contact_name || "";
    emailField.value = supplier.email || "";
    phoneField.value = supplier.phone || "";
    addressField.value = supplier.address || "";

    const detailsEl = supplierForm.closest("details");
    if (detailsEl) detailsEl.open = true;
  }

  function resetForm() {
    supplierForm.reset();
    supplierIdField.value = "";
  }

  async function loadSuppliers(search) {
    grid.innerHTML = '<p class="productMessage">Loading suppliers...</p>';
    clearNotice();
    try {
      const data = await fetchSuppliers(search);
      suppliers = Array.isArray(data) ? data : data.suppliers || [];
      renderSuppliers(suppliers);
    } catch (err) {
      grid.innerHTML = '<p class="productMessage">Could not load suppliers.</p>';
      showNotice(err.message || "Something went wrong loading suppliers.", true);
    }
  }

  searchForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    currentSearch = searchInput.value.trim();
    loadSuppliers(currentSearch);
  });

  supplierForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearNotice();

    const payload = {
      name: nameField.value.trim(),
      contact_name: contactField.value.trim() || null,
      email: emailField.value.trim() || null,
      phone: phoneField.value.trim() || null,
      address: addressField.value.trim() || null,
    };

    if (!payload.name) {
      showNotice("Supplier name is required.", true);
      return;
    }

    const id = supplierIdField.value || null;

    try {
      await saveSupplier(payload, id);
      showNotice(id ? "Supplier updated." : "Supplier added.", false);
      resetForm();
      loadSuppliers(currentSearch);
    } catch (err) {
      showNotice(err.message || "Could not save supplier.", true);
    }
  });

  cancelButton?.addEventListener("click", () => {
    resetForm();
    clearNotice();
  });

  grid?.addEventListener("click", async (event) => {
    const editBtn = event.target.closest(".editSupplierButton");
    const deleteBtn = event.target.closest(".deleteSupplierButton");

    if (editBtn) {
      const id = editBtn.dataset.id;
      const supplier = suppliers.find((s) => String(s.id) === String(id));
      if (supplier) {
        fillForm(supplier);
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
      return;
    }

    if (deleteBtn) {
      const id = deleteBtn.dataset.id;
      const confirmed = window.confirm("Delete this supplier?");
      if (!confirmed) return;

      try {
        await deleteSupplier(id);
        showNotice("Supplier deleted.", false);
        loadSuppliers(currentSearch);
      } catch (err) {
        showNotice(err.message || "Could not delete supplier.", true);
      }
    }
  });

  document.addEventListener("DOMContentLoaded", () => {
    loadSuppliers("");
  });
})();