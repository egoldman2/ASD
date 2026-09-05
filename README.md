# ASD 2026 Group 7 - Online Marketplace

## Project Overview

This project is an integrated online marketplace developed by Group 7 for ASD 2026.

The application is divided into five individual microservice features. Each feature contains its own frontend, backend/API, database, testing, Docker, AI-assisted functionality, and CI/CD workflow. The services are integrated through a shared home page and Docker Compose configuration.

The application uses technologies including:

- Python and Flask
- HTML, CSS, JavaScript and HTMX
- SQLite
- Docker and Docker Compose
- GitHub Actions
- Ollama and approved open-source language models

## Team Features

### 1. Product Catalogue and Shopping Cart

**Student:** Chufeng Li  
**Directory:** `student-Chufeng/`

The Product Catalogue allows customers to browse available products and search for products using case-insensitive partial-name matching.

Customers can add products to a shopping cart, view cart items, update item quantities, remove items, and view the calculated cart total. The backend validates product availability, stock quantity, and user input before modifying cart records.

The feature also includes a read-only AI Product Assistant powered by Ollama and `qwen2.5:0.5b`. It recommends combinations of available catalogue products according to the customer's question, category preferences, and budget.

The frontend is available through Docker on: http://localhost:8001
The shared Flask backend is available on: http://localhost:5000

#### Main Functions

- Display all catalogue products
- Search products by partial product name
- Add products to the shopping cart
- View shopping cart items and total price
- Update shopping cart quantities
- Remove products from the shopping cart
- Validate stock availability and requested quantities
- Generate AI-assisted product recommendations
- Demonstrate the Plan, Act, Observe and Adapt workflow

#### Architecture

The feature follows a layered architecture:

```text
Frontend
    ↓ HTTP / REST API
Flask Routes
    ↓
Controllers
    ↓
Models / Data-Access Layer
    ↓
SQLite Database
```

#### Testing and CI/CD
Automated tests are implemented using Pytest. The tests cover product retrieval, product search, shopping cart CRUD operations, validation, database initialisation, totals, and the Agentic review loop.
The Chufeng GitHub Actions workflow:
- Installs Python dependencies
- Runs the Product Catalogue tests
- Builds the Product Catalogue frontend image
- Builds the shared backend Docker image

### 2. Inventory Management


### 3. Customer and Loyalty Management


### 4. Order and Returns Management


### 5. Customer Support
