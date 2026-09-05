# ASD 2026 Group 33 - Online Marketplace

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

**Student:** Howard

**Directory:** `student-Howard/`

The Order and Returns Management feature allows customers and administrators to manage orders and returns through a role-aware dashboard. Administrators can view all orders and returns, and approve or reject return requests. 

Customers can view only their own orders and submit new return requests. The backend enforces this access control by checking the signed-in user's role and filtering data by their user ID.

The feature also includes an advisory AI capability powered by Ollama and qwen2.5:0.5b. For a selected return, it generates a summary of the problem and a recommended customer-service action. The AI is advisory only and never modifies any database record, all status changes are performed by application logic through dedicated endpoints.

The frontend is available through Docker on: http://localhost:8004

The shared Flask backend is available on: http://localhost:5000

#### Main Functions
- Create, view, update, and delete orders
- Store order line items linked to parent orders
- Create and process return requests linked to existing orders
- Approve or reject return requests (administrators)
- Submit new return requests (customers)
- Enforce role-based access for administrators and customers
- Display orders and returns with summary statistics and colour-coded status badges
- Generate advisory AI return advice without modifying data

#### Architecture

The feature follows a layered architecture:
```text
Frontend (HTMX / JavaScript)
    ↓ HTTP / REST API (with authentication)
Flask Blueprint Routes
    ↓
Application Logic (role-based access, status changes)
    ↓
SQLite Database
    ↓ (advisory only)
Ollama / Qwen AI Service
```

#### Testing and CI/CD
Automated tests are implemented using Pytest. The tests cover order and return retrieval, creation, status changes, not-found handling, and database initialisation.
Howard GitHub Actions workflow:
- Installs Python dependencies
- Seeds the database and verifies at least ten records per table
- Runs the Order and Returns tests
- Builds the Order and Returns frontend image


### 5. Customer Support
