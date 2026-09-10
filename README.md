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

**Student:** Ethan Ting

**Directory:** `student-Ethan Ting/`

The Customer Accounts and Loyalty feature provides customer registration, login, session management, profile editing and password changes. Customers can view their loyalty points balance, membership tier and points transaction history. Administrators can manage customer and administrator accounts, disable customer accounts and adjust loyalty points through protected role-based endpoints.

The feature also includes the Customer Insight AI assistant powered by Ollama and `llama3.1:8b`. An administrator can ask questions about customer accounts and loyalty information, find the customer linked to an email address and prepare changes to a customer's name or email. Proposed account changes are not saved automatically. The administrator must review the current and proposed values and explicitly confirm the update.

The frontend is available through Docker on: http://localhost:8003

The Customer Accounts backend API is available on: http://localhost:6002

The database API is available internally through Docker Compose at `ethan-database:6003`.

#### Main Functions

- Register a new customer account
- Sign in and sign out using server-managed sessions
- View and update the signed-in customer's name and email address
- Change a customer's password after verifying the current password
- Display loyalty points, membership tier and points history
- Create and manage customer and administrator accounts
- Disable and reactivate customer accounts
- Add or deduct loyalty points with a recorded reason
- Enforce customer and administrator role permissions in the backend
- Find and summarise customer information using the administrator AI assistant
- Prepare AI-assisted account changes for human review and confirmation
- Demonstrate the Plan, Act, Observe and Adapt review workflow

#### Architecture

The feature runs as three separate services and uses the shared Ollama runtime:

```text
Nginx Frontend
    ↓ HTTP / JSON
Flask Customer Accounts API
    ├── HTTP → Flask Database API → SQLite users and loyalty data
    └── HTTP → Ollama / Llama 3.1 8B
```

Only the database API directly accesses the customer SQLite database. The frontend communicates with the backend API, while the backend applies validation, session checks and role-based access control before requesting data or saving changes.

#### Testing and CI/CD

Automated tests use Pytest and cover registration, login, logout, sessions, customer profile and password updates, administrator permissions, account management, loyalty calculations, transaction history, database validation, Customer Insight AI safeguards and agentic review evidence.

Run the Customer Accounts and Loyalty tests from the repository root:

```bash
python -m pytest "student-Ethan Ting/tests" -q
```

The Ethan Ting GitHub Actions workflow:

- Sets up Python 3.11 and installs the project dependencies
- Initialises and verifies the customer database
- Runs the automated tests and checks Python compilation
- Validates the shared Docker Compose configuration
- Builds the customer frontend, backend and database targets
- Starts the services and checks authentication, loyalty and role protection
- Displays service logs when a smoke test fails and stops the services after execution




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

**Student:** Ethan Goldman

**Directory:** `student-Ethan Goldman/`

The Customer Support feature allows authenticated customers to create support tickets, view their own tickets and continue conversations with staff. Administrators can search and filter the ticket queue, reply to customers, update ticket category, priority, status and assignment, and delete tickets.

The frontend uses HTMX to update ticket lists, conversations and analysis panels without full page reloads. The backend verifies sessions through the shared Customer and Loyalty authentication API, enforces administrator permissions and checks ticket ownership. Submitted values and request origins are validated, and customer messages are escaped when rendered as HTML.

An advisory AI assistant uses Ollama and `qwen2.5:0.5b` to generate a ticket summary, category, priority, sentiment, suggested next steps and supporting source references. The Plan, Act, Observe and Adapt workflow prepares bounded, redacted context, requests structured JSON, validates the response and allows one correction retry. Staff explicitly apply triage changes or send replies; AI analysis does not modify ticket records.

The frontend is available through Docker on: http://localhost:8005

The independent Flask backend is available on: http://localhost:6005

The database API is available internally through Docker Compose at `customer-support-database:6006`.

#### Main Functions

- Create support tickets with an opening message
- View owned tickets and chronological conversations
- Add customer and staff replies with verified authorship
- Search and filter tickets by category, priority, status and assignment
- Update ticket triage and staff assignment
- Delete tickets and their associated messages
- Enforce session authentication, administrator roles and customer ownership
- Generate validated AI analysis for staff review
- Review database, implementation, architecture and DevOps evidence using feature-specific agentic prompts

#### Architecture

The feature runs as three independent services, with shared authentication and AI dependencies:

```text
Nginx Frontend (HTMX)
    ↓ HTTP / JSON and HTML fragments
Flask Customer Support API
    ├── HTTP → Shared Authentication API (sessions and roles)
    ├── HTTP → Ollama / Qwen (advisory analysis)
    └── HTTP → Flask Support Database API
                   ↓
               SQLite Database
```

Only the database service accesses SQLite. The `support_tickets` and `support_ticket_messages` tables contain 12 seeded tickets and 20 messages, with foreign keys and cascading message deletion. The `support-ticket-data` Docker volume persists the database. Docker Compose connects the services and uses health checks and startup dependencies to prepare the database, authentication and Ollama services before the support backend starts.

#### Testing and CI/CD

Automated tests use Pytest and temporary Flask services. They cover ticket CRUD, conversations, authentication, ownership, HTMX responses, input and origin validation, database seeding and migration, dependency failures, AI output policy and agentic review evidence collection.

Run the Customer Support tests from the repository root using a Python 3.11 environment with `requirements.txt` installed:

```bash
python -m pytest "student-Ethan Goldman/tests" -v
```

The live inference test is enabled with `RUN_LIVE_AI=1` and requires a reachable Ollama service containing `qwen2.5:0.5b`. Local tests default to `http://127.0.0.1:11434`; set `OLLAMA_URL` to use another accessible runtime.

The Ethan Goldman GitHub Actions workflow:

- Installs Python 3.11 dependencies, runs the support tests and checks Python compilation
- Builds and runs the Customer Support Docker test target
- Validates Docker Compose and starts support, authentication and Ollama services
- Checks service health, access control, HTMX responses and real AI analysis
- Verifies agentic workflow logs and that AI analysis leaves the database unchanged
- Displays service logs on failure and removes CI containers and volumes after execution
