const AUTH_API_URL = "http://localhost:6002";
const PRODUCT_API_URL = "http://localhost:5000";

const profileForm = document.querySelector("#profileForm");
const profileMessage = document.querySelector("#profileMessage");
const inventoryMessage = document.querySelector("#inventoryMessage");
const inventoryGrid = document.querySelector("#inventoryGrid");
const inventorySearch = document.querySelector("#inventorySearch");

let products = [];


async function authRequest(path, options = {}) {
  const response = await fetch(`${AUTH_API_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  const result = await response.json();

  if (!response.ok) {
    const error = new Error(result.error || "The request failed.");
    error.status = response.status;
    throw error;
  }

  return result;
}


function showProfileMessage(message, success = false) {
  profileMessage.textContent = message;
  profileMessage.classList.toggle("success", success);
}


function renderInventory() {
  const searchTerm = inventorySearch.value.trim().toLowerCase();
  const matchingProducts = products.filter((product) => (
    product.name.toLowerCase().includes(searchTerm)
    || product.category.toLowerCase().includes(searchTerm)
  ));

  inventoryGrid.replaceChildren();

  for (const product of matchingProducts) {
    const card = document.createElement("article");
    const title = document.createElement("h3");
    const meta = document.createElement("p");
    const details = document.createElement("div");
    const price = document.createElement("strong");
    const stock = document.createElement("span");

    card.className = "inventoryCard";
    title.textContent = product.name;
    meta.className = "inventoryMeta";
    meta.textContent = product.category;
    details.className = "inventoryDetails";
    price.textContent = `$${Number(product.price).toFixed(2)}`;
    stock.className = product.stock_quantity > 0
      ? "stockBadge stockBadge--available"
      : "stockBadge stockBadge--unavailable";
    stock.textContent = product.stock_quantity > 0
      ? `${product.stock_quantity} in stock`
      : "Out of stock";

    details.append(price, stock);
    card.append(title, meta, details);
    inventoryGrid.append(card);
  }

  if (matchingProducts.length === 0) {
    inventoryMessage.textContent = "No products match your search.";
  } else if (matchingProducts.length === 1) {
    inventoryMessage.textContent = "1 product available to view.";
  } else {
    inventoryMessage.textContent = (
      `${matchingProducts.length} products available to view.`
    );
  }
}


async function loadProfile() {
  const result = await authRequest("/api/profile");
  const user = result.user;

  document.querySelector("#customerGreeting").textContent = (
    `Welcome, ${user.full_name}`
  );
  profileForm.elements.full_name.value = user.full_name;
  profileForm.elements.email.value = user.email;
}


async function loadInventory() {
  try {
    const response = await fetch(`${PRODUCT_API_URL}/api/products`);
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || "Unable to load products.");
    }

    products = result.products;
    renderInventory();
  } catch (error) {
    inventoryMessage.textContent = "Product inventory is currently unavailable.";
  }
}


profileForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  try {
    const result = await authRequest("/api/profile", {
      method: "PUT",
      body: JSON.stringify({
        full_name: profileForm.elements.full_name.value,
        email: profileForm.elements.email.value,
      }),
    });
    document.querySelector("#customerGreeting").textContent = (
      `Welcome, ${result.user.full_name}`
    );
    showProfileMessage("Your profile was updated.", true);
  } catch (error) {
    showProfileMessage(error.message);
  }
});


inventorySearch.addEventListener("input", renderInventory);
document.querySelector("#logoutButton").addEventListener("click", async () => {
  await authRequest("/api/logout", { method: "POST" });
  window.location.replace("index.html");
});


async function startCustomerPage() {
  try {
    const sessionResult = await authRequest("/api/session");

    if (sessionResult.user.role === "admin") {
      window.location.replace("admin.html");
      return;
    }

    await Promise.all([loadProfile(), loadInventory()]);
  } catch (error) {
    window.location.replace("index.html");
  }
}


startCustomerPage();
