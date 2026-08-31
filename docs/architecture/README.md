# Release 0 architecture

## Integrated request flow

```mermaid
flowchart LR
    B[Browser] --> SF[Support frontend :8005]
    SF --> SB[Support backend :6005]
    SB --> AUTH[Customer & Loyalty auth :6002]
    AUTH --> UDB[User database API :6003]
    SB --> SDB[Support database API :6006]
    SDB --> SQLITE[(support_tickets.db)]
    SB --> O[Ollama :11434]
    O --> M[qwen2.5:0.5b]
```

The browser never accesses the support SQLite database. The support backend
does not mount or import that database. All ticket persistence crosses the
internal database HTTP API. Only `customer-support-database` mounts the
`support-ticket-data` volume.

## Authentication and authorization

```mermaid
sequenceDiagram
    participant Browser
    participant Support as Support backend
    participant Auth as Auth backend
    participant DB as Support database API
    Browser->>Support: request + ethan_session
    Support->>Auth: GET /api/session + ethan_session
    Auth-->>Support: verified id, name, email, role
    alt customer
        Support->>DB: owner-scoped operation using verified id
    else administrator
        Support->>DB: admin search or management operation
    end
    DB-->>Support: ticket data
    Support-->>Browser: safe JSON/HTML response
```

Customer identity, sender role and ownership are derived server-side. Customer
routes cannot search all tickets or set category, priority, status or assignee.
Administrator routes enforce the admin role before queue access or mutation.

## AI workflow

```mermaid
flowchart LR
    P[Plan: minimise and redact context] --> A[Act: request structured Ollama JSON]
    A --> O[Observe: validate schema, enums, bounds and claims]
    O -->|valid| R[Read-only suggestion for staff]
    O -->|invalid once| D[Adapt: correction retry]
    D --> A
    O -->|invalid twice| E[Safe 502]
    R --> H[Explicit administrator apply action]
    H --> DB[Validated database API update]
```

Ollama never receives direct database access. Analysis does not persist changes.
The separate apply action records the authenticated administrator ID in
`triage_applied_by`.
