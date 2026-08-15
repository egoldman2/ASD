const PRODUCTS_API_URL = "http://localhost:5000/api/products";
const CART_API_URL = "http://localhost:5000/api/cart-items";
const AI_API_URL = "http://localhost:5000/api/ai/product-assistant";

const productGrid = document.querySelector("#productGrid");
const searchForm = document.querySelector("#searchForm");
const searchInput = document.querySelector("#searchInput");
const catalogueNotice = document.querySelector("#catalogueNotice");
const aiForm = document.querySelector("#aiForm");
const aiQuestion = document.querySelector("#aiQuestion");
const aiOutput = document.querySelector("#aiOutput");
const askAiButton = document.querySelector("#askAiButton");

function formatCurrency(value) {
  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency: "AUD",
  }).format(value);
}

function showMessage(text, isError = false) {
  const message = document.createElement("p");
  message.className = isError
    ? "productMessage productMessage--error"
    : "productMessage";
  message.textContent = text;
  productGrid.replaceChildren(message);
}

function showCatalogueNotice(text, isError = false) {
  catalogueNotice.textContent = text;
  catalogueNotice.classList.toggle("catalogueNotice--error", isError);
  catalogueNotice.hidden = false;
}

function showAiOutput(text, isError = false) {
  aiOutput.value = text;
  aiOutput.classList.toggle("aiOutput--error", isError);
  aiOutput.style.height = "auto";
  aiOutput.style.height = `${aiOutput.scrollHeight}px`;
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
  price.textContent = formatCurrency(product.price);

  const stock = document.createElement("span");
  stock.className = "productStock";
  stock.textContent = `${product.stock_quantity} in stock`;

  const purchaseControls = document.createElement("div");
  purchaseControls.className = "purchaseControls";

  const quantitySelector = document.createElement("div");
  quantitySelector.className = "quantitySelector";

  const decreaseButton = document.createElement("button");
  decreaseButton.type = "button";
  decreaseButton.className = "quantityButton";
  decreaseButton.textContent = "-";
  decreaseButton.setAttribute("aria-label", `Decrease quantity for ${product.name}`);

  const quantityValue = document.createElement("span");
  quantityValue.className = "quantityValue";
  quantityValue.textContent = "1";
  quantityValue.setAttribute("aria-live", "polite");

  const increaseButton = document.createElement("button");
  increaseButton.type = "button";
  increaseButton.className = "quantityButton";
  increaseButton.textContent = "+";
  increaseButton.setAttribute("aria-label", `Increase quantity for ${product.name}`);

  const addButton = document.createElement("button");
  addButton.type = "button";
  addButton.className = "addToCartButton";
  addButton.textContent = "Add to Cart";

  const cardNotice = document.createElement("span");
  cardNotice.className = "cardNotice";
  cardNotice.setAttribute("aria-live", "polite");

  const isUnavailable = product.status !== "active" || product.stock_quantity < 1;
  decreaseButton.disabled = isUnavailable;
  increaseButton.disabled = isUnavailable;
  addButton.disabled = isUnavailable;

  decreaseButton.addEventListener("click", () => {
    const currentQuantity = Number(quantityValue.textContent);
    quantityValue.textContent = String(Math.max(1, currentQuantity - 1));
  });

  increaseButton.addEventListener("click", () => {
    const currentQuantity = Number(quantityValue.textContent);
    quantityValue.textContent = String(
      Math.min(product.stock_quantity, currentQuantity + 1),
    );
  });

  addButton.addEventListener("click", async () => {
    cardNotice.textContent = "";
    cardNotice.classList.remove("cardNotice--error");
    addButton.disabled = true;
    addButton.textContent = "Adding...";

    try {
      const response = await fetch(CART_API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_id: product.id,
          quantity: Number(quantityValue.textContent),
        }),
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Unable to add product to cart.");
      }

      quantityValue.textContent = "1";
      showCatalogueNotice(`${product.name} was added to your cart.`);
      cardNotice.textContent = "Added";
    } catch (error) {
      console.error("Unable to add product to cart:", error);
      cardNotice.textContent = error.message;
      cardNotice.classList.add("cardNotice--error");
    } finally {
      addButton.disabled = isUnavailable;
      addButton.textContent = "Add to Cart";
    }
  });

  cardHeader.append(category, status);
  cardFooter.append(price, stock);
  quantitySelector.append(decreaseButton, quantityValue, increaseButton);
  purchaseControls.append(quantitySelector, addButton, cardNotice);
  card.append(cardHeader, name, description, cardFooter, purchaseControls);
  return card;
}

async function loadProducts(searchTerm = "") {
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

aiForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const message = aiQuestion.value.trim();

  if (!message) {
    showAiOutput("Please enter a product question.", true);
    return;
  }

  askAiButton.disabled = true;
  askAiButton.textContent = "Thinking...";
  showAiOutput("The AI assistant is reviewing the available products...");

  try {
    const response = await fetch(AI_API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "Unable to get an AI response.");
    }

    showAiOutput(data.answer);
  } catch (error) {
    console.error("Unable to use the AI product assistant:", error);
    showAiOutput(error.message, true);
  } finally {
    askAiButton.disabled = false;
    askAiButton.textContent = "Ask AI";
  }
});

loadProducts();
