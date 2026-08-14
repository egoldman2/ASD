const CART_API_URL = "http://localhost:5000/api/cart-items";

const cartGrid = document.querySelector("#cartGrid");
const cartNotice = document.querySelector("#cartNotice");
const cartSummary = document.querySelector("#cartSummary");
const cartItemCount = document.querySelector("#cartItemCount");
const cartTotal = document.querySelector("#cartTotal");

function formatCurrency(value) {
  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency: "AUD",
  }).format(value);
}

function showCartMessage(text, isError = false) {
  const message = document.createElement("p");
  message.className = isError
    ? "productMessage productMessage--error"
    : "productMessage";
  message.textContent = text;
  cartGrid.replaceChildren(message);
}

function showCartNotice(text, isError = false) {
  cartNotice.textContent = text;
  cartNotice.classList.toggle("catalogueNotice--error", isError);
  cartNotice.hidden = false;
}

function createCartCard(item) {
  const card = document.createElement("article");
  card.className = "productCard cartCard";

  const cardHeader = document.createElement("div");
  cardHeader.className = "productCardHeader";

  const category = document.createElement("span");
  category.className = "productCategory";
  category.textContent = item.category;

  const status = document.createElement("span");
  status.className = "productStatus productStatus--active";
  status.textContent = "In cart";

  const name = document.createElement("h3");
  name.textContent = item.name;

  const description = document.createElement("p");
  description.textContent = item.description || "No description available.";

  const priceDetails = document.createElement("div");
  priceDetails.className = "cartPriceDetails";

  const unitPrice = document.createElement("span");
  unitPrice.textContent = `Unit price: ${formatCurrency(item.price)}`;

  const subtotal = document.createElement("strong");
  subtotal.textContent = `Subtotal: ${formatCurrency(item.subtotal)}`;

  const actions = document.createElement("div");
  actions.className = "cartActions";

  const quantityLabel = document.createElement("label");
  quantityLabel.className = "cartQuantityField";
  quantityLabel.textContent = "Quantity";

  const quantityInput = document.createElement("input");
  quantityInput.type = "number";
  quantityInput.min = "1";
  quantityInput.max = String(item.stock_quantity);
  quantityInput.step = "1";
  quantityInput.value = String(item.quantity);
  quantityInput.setAttribute("aria-label", `Quantity for ${item.name}`);

  const updateButton = document.createElement("button");
  updateButton.type = "button";
  updateButton.className = "updateCartButton";
  updateButton.textContent = "Update Quantity";

  const removeButton = document.createElement("button");
  removeButton.type = "button";
  removeButton.className = "removeCartButton";
  removeButton.textContent = "Remove";

  const actionNotice = document.createElement("span");
  actionNotice.className = "cardNotice";
  actionNotice.setAttribute("aria-live", "polite");

  updateButton.addEventListener("click", async () => {
    const quantity = Number(quantityInput.value);
    actionNotice.textContent = "";
    actionNotice.classList.remove("cardNotice--error");

    if (!Number.isInteger(quantity) || quantity < 1) {
      actionNotice.textContent = "Quantity must be a whole number of one or greater.";
      actionNotice.classList.add("cardNotice--error");
      quantityInput.focus();
      return;
    }

    if (quantity > item.stock_quantity) {
      actionNotice.textContent = `Only ${item.stock_quantity} available.`;
      actionNotice.classList.add("cardNotice--error");
      quantityInput.focus();
      return;
    }

    updateButton.disabled = true;
    updateButton.textContent = "Updating...";

    try {
      const response = await fetch(`${CART_API_URL}/${item.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ quantity }),
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Unable to update cart quantity.");
      }

      showCartNotice(`${item.name} quantity was updated.`);
      await loadCart();
    } catch (error) {
      console.error("Unable to update cart item:", error);
      actionNotice.textContent = error.message;
      actionNotice.classList.add("cardNotice--error");
      updateButton.disabled = false;
      updateButton.textContent = "Update Quantity";
    }
  });

  removeButton.addEventListener("click", async () => {
    actionNotice.textContent = "";
    actionNotice.classList.remove("cardNotice--error");

    if (!window.confirm(`Remove ${item.name} from your cart?`)) {
      return;
    }

    removeButton.disabled = true;
    removeButton.textContent = "Removing...";

    try {
      const response = await fetch(`${CART_API_URL}/${item.id}`, {
        method: "DELETE",
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Unable to remove cart item.");
      }

      showCartNotice(`${item.name} was removed from your cart.`);
      await loadCart();
    } catch (error) {
      console.error("Unable to remove cart item:", error);
      actionNotice.textContent = error.message;
      actionNotice.classList.add("cardNotice--error");
      removeButton.disabled = false;
      removeButton.textContent = "Remove";
    }
  });

  cardHeader.append(category, status);
  priceDetails.append(unitPrice, subtotal);
  quantityLabel.append(quantityInput);
  actions.append(quantityLabel, updateButton, removeButton, actionNotice);
  card.append(cardHeader, name, description, priceDetails, actions);
  return card;
}

async function loadCart() {
  showCartMessage("Loading your cart...");
  cartSummary.hidden = true;

  try {
    const response = await fetch(CART_API_URL);
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }

    const data = await response.json();
    if (data.items.length === 0) {
      showCartMessage("Your cart is empty.");
      return;
    }

    cartGrid.replaceChildren(...data.items.map(createCartCard));
    cartItemCount.textContent = `${data.total_quantity} items across ${data.count} products`;
    cartTotal.textContent = `Total: ${formatCurrency(data.total)}`;
    cartSummary.hidden = false;
  } catch (error) {
    console.error("Unable to load cart:", error);
    showCartMessage("Your cart could not be loaded. Please try again later.", true);
  }
}

loadCart();
