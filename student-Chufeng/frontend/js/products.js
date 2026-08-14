const PRODUCTS_API_URL = "http://localhost:5000/api/products";

const productGrid = document.querySelector("#productGrid");
const searchForm = document.querySelector("#searchForm");
const searchInput = document.querySelector("#searchInput");
const toggleProductFormButton = document.querySelector("#toggleProductFormButton");
const addProductForm = document.querySelector("#addProductForm");
const cancelProductButton = document.querySelector("#cancelProductButton");
const submitProductButton = document.querySelector("#submitProductButton");
const productFormTitle = document.querySelector("#productFormTitle");
const formMessage = document.querySelector("#formMessage");
const catalogueNotice = document.querySelector("#catalogueNotice");
let currentSearchTerm = "";
let editingProductId = null;

function showMessage(text, isError = false) {
  const message = document.createElement("p");
  message.className = isError
    ? "productMessage productMessage--error"
    : "productMessage";
  message.textContent = text;
  productGrid.replaceChildren(message);
}

function setProductFormOpen(isOpen) {
  addProductForm.hidden = !isOpen;
  toggleProductFormButton.setAttribute("aria-expanded", String(isOpen));
  toggleProductFormButton.textContent = isOpen ? "Close Form" : "Add Product";

  if (isOpen) {
    addProductForm.elements.name.focus();
  }
}

function setProductFormMode(product = null) {
  editingProductId = product ? product.id : null;
  productFormTitle.textContent = product ? "Edit Product" : "Add Product";
  submitProductButton.textContent = product ? "Save Changes" : "Create Product";

  if (product) {
    addProductForm.elements.name.value = product.name;
    addProductForm.elements.category.value = product.category;
    addProductForm.elements.price.value = product.price;
    addProductForm.elements.stock_quantity.value = product.stock_quantity;
    addProductForm.elements.description.value = product.description || "";
  }
}

function showCatalogueNotice(text) {
  catalogueNotice.textContent = text;
  catalogueNotice.hidden = false;
}

function validateProductForm() {
  const nameField = addProductForm.elements.name;
  const categoryField = addProductForm.elements.category;
  const priceField = addProductForm.elements.price;
  const stockField = addProductForm.elements.stock_quantity;
  const price = Number(priceField.value);
  const stockQuantity = Number(stockField.value);

  if (!nameField.value.trim()) {
    return { field: nameField, message: "Please enter a product name." };
  }

  if (!categoryField.value) {
    return { field: categoryField, message: "Please select a category." };
  }

  if (priceField.value === "" || !Number.isFinite(price) || price < 0) {
    return { field: priceField, message: "Please enter a valid price of zero or greater." };
  }

  if (
    stockField.value === ""
    || !Number.isInteger(stockQuantity)
    || stockQuantity < 0
  ) {
    return {
      field: stockField,
      message: "Please enter a whole stock quantity of zero or greater.",
    };
  }

  return null;
}

function createProductCard(product) {
  const card = document.createElement("article");
  card.className = "productCard";

  const cardHeader = document.createElement("div");
  cardHeader.className = "productCardHeader";

  const category = document.createElement("span");
  category.className = "productCategory";
  category.textContent = product.category;

  const status = document.createElement("span");
  status.className = `productStatus productStatus--${product.status}`;
  status.textContent = product.status === "active" ? "Available" : "Out of stock";

  const name = document.createElement("h3");
  name.textContent = product.name;

  const description = document.createElement("p");
  description.textContent = product.description || "No description available.";

  const cardFooter = document.createElement("div");
  cardFooter.className = "productCardFooter";

  const price = document.createElement("strong");
  price.className = "productPrice";
  price.textContent = new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency: "AUD",
  }).format(product.price);

  const stock = document.createElement("span");
  stock.className = "productStock";
  stock.textContent = `${product.stock_quantity} in stock`;

  const cardActions = document.createElement("div");
  cardActions.className = "productCardActions";

  const editButton = document.createElement("button");
  editButton.className = "editButton";
  editButton.type = "button";
  editButton.textContent = "Edit";

  const deleteButton = document.createElement("button");
  deleteButton.className = "deleteButton";
  deleteButton.type = "button";
  deleteButton.textContent = "Delete";

  const deleteConfirmation = document.createElement("div");
  deleteConfirmation.className = "deleteConfirmation";
  deleteConfirmation.hidden = true;

  const deletePrompt = document.createElement("span");
  deletePrompt.className = "deletePrompt";
  deletePrompt.textContent = "Delete this product?";

  const deleteError = document.createElement("span");
  deleteError.className = "deleteError";
  deleteError.setAttribute("aria-live", "polite");

  const cancelDeleteButton = document.createElement("button");
  cancelDeleteButton.className = "cancelDeleteButton";
  cancelDeleteButton.type = "button";
  cancelDeleteButton.textContent = "Cancel";

  const confirmDeleteButton = document.createElement("button");
  confirmDeleteButton.className = "confirmDeleteButton";
  confirmDeleteButton.type = "button";
  confirmDeleteButton.textContent = "Confirm Delete";

  editButton.addEventListener("click", () => {
    addProductForm.reset();
    formMessage.textContent = "";
    catalogueNotice.hidden = true;
    setProductFormMode(product);
    setProductFormOpen(true);
    addProductForm.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  deleteButton.addEventListener("click", () => {
    deleteButton.hidden = true;
    deleteConfirmation.hidden = false;
    confirmDeleteButton.focus();
  });

  cancelDeleteButton.addEventListener("click", () => {
    deleteError.textContent = "";
    deleteConfirmation.hidden = true;
    deleteButton.hidden = false;
    deleteButton.focus();
  });

  confirmDeleteButton.addEventListener("click", async () => {
    deleteError.textContent = "";
    confirmDeleteButton.disabled = true;
    confirmDeleteButton.textContent = "Deleting...";

    try {
      const response = await fetch(`${PRODUCTS_API_URL}/${product.id}`, {
        method: "DELETE",
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Unable to delete product.");
      }

      showCatalogueNotice(`${product.name} was deleted successfully.`);
      await loadProducts(currentSearchTerm);
    } catch (error) {
      console.error("Unable to delete product:", error);
      deleteError.textContent = error.message;
      confirmDeleteButton.disabled = false;
      confirmDeleteButton.textContent = "Confirm Delete";
    }
  });

  cardHeader.append(category, status);
  cardFooter.append(price, stock);
  deleteConfirmation.append(
    deletePrompt,
    cancelDeleteButton,
    confirmDeleteButton,
    deleteError,
  );
  cardActions.append(editButton, deleteButton, deleteConfirmation);
  card.append(cardHeader, name, description, cardFooter, cardActions);

  return card;
}

async function loadProducts(searchTerm = "") {
  currentSearchTerm = searchTerm;
  const requestUrl = new URL(PRODUCTS_API_URL);

  if (searchTerm) {
    requestUrl.searchParams.set("search", searchTerm);
  }

  showMessage("Loading products...");

  try {
    const response = await fetch(requestUrl);

    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }

    const data = await response.json();

    if (data.products.length === 0) {
      showMessage("No products found.");
      return;
    }

    productGrid.replaceChildren(...data.products.map(createProductCard));
  } catch (error) {
    console.error("Unable to load products:", error);
    showMessage("Products could not be loaded. Please try again later.", true);
  }
}

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  catalogueNotice.hidden = true;
  loadProducts(searchInput.value.trim());
});

toggleProductFormButton.addEventListener("click", () => {
  const shouldOpen = addProductForm.hidden;
  addProductForm.reset();
  formMessage.textContent = "";
  setProductFormMode();
  setProductFormOpen(shouldOpen);
});

cancelProductButton.addEventListener("click", () => {
  addProductForm.reset();
  formMessage.textContent = "";
  setProductFormMode();
  setProductFormOpen(false);
});

addProductForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  formMessage.textContent = "";

  const validationError = validateProductForm();

  if (validationError) {
    formMessage.textContent = validationError.message;
    validationError.field.focus();
    return;
  }

  const isEditing = editingProductId !== null;
  const requestUrl = isEditing
    ? `${PRODUCTS_API_URL}/${editingProductId}`
    : PRODUCTS_API_URL;
  submitProductButton.disabled = true;
  submitProductButton.textContent = isEditing ? "Saving..." : "Creating...";

  const formData = new FormData(addProductForm);
  const product = {
    name: formData.get("name").trim(),
    category: formData.get("category"),
    description: formData.get("description").trim(),
    price: Number(formData.get("price")),
    stock_quantity: Number(formData.get("stock_quantity")),
  };

  try {
    const response = await fetch(requestUrl, {
      method: isEditing ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(product),
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.error || (isEditing ? "Unable to update product." : "Unable to create product."),
      );
    }

    addProductForm.reset();
    setProductFormMode();
    setProductFormOpen(false);
    showCatalogueNotice(
      isEditing
        ? `${data.product.name} was updated successfully.`
        : `${data.product.name} was added successfully.`,
    );

    if (isEditing) {
      await loadProducts(currentSearchTerm);
    } else {
      searchInput.value = "";
      await loadProducts();
    }
  } catch (error) {
    console.error(isEditing ? "Unable to update product:" : "Unable to create product:", error);
    formMessage.textContent = error.message;
  } finally {
    submitProductButton.disabled = false;
    submitProductButton.textContent = editingProductId === null
      ? "Create Product"
      : "Save Changes";
  }
});

loadProducts();
