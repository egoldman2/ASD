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
