CREATE TABLE IF NOT EXISTS support_tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL CHECK (LENGTH(TRIM(customer_name)) BETWEEN 2 AND 100),
    customer_email TEXT NOT NULL CHECK (LENGTH(TRIM(customer_email)) BETWEEN 3 AND 254),
    subject TEXT NOT NULL CHECK (LENGTH(TRIM(subject)) BETWEEN 5 AND 160),
    message TEXT NOT NULL CHECK (LENGTH(TRIM(message)) BETWEEN 10 AND 2000),
    category TEXT NOT NULL CHECK (category IN ('order', 'return', 'payment', 'product', 'delivery', 'account', 'other')),
    priority TEXT NOT NULL CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'pending', 'solved')),
    assigned_to TEXT CHECK (assigned_to IS NULL OR LENGTH(TRIM(assigned_to)) BETWEEN 2 AND 100),
    staff_response TEXT CHECK (staff_response IS NULL OR LENGTH(TRIM(staff_response)) <= 2000),
    responded_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_support_tickets_status
ON support_tickets (status);

CREATE INDEX IF NOT EXISTS idx_support_tickets_priority
ON support_tickets (priority);

CREATE INDEX IF NOT EXISTS idx_support_tickets_category
ON support_tickets (category);

CREATE INDEX IF NOT EXISTS idx_support_tickets_created_at
ON support_tickets (created_at DESC);
