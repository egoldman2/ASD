-- Ryan
CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact_name TEXT,
    email TEXT,
    phone TEXT,
    address TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

--Combined
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    price REAL NOT NULL CHECK (price >= 0),
    unit_cost REAL NOT NULL DEFAULT 0 CHECK (unit_cost >= 0),
    stock_quantity INTEGER NOT NULL CHECK (stock_quantity >= 0),
    status TEXT NOT NULL CHECK (status IN ('active', 'out_of_stock')),

    supplier_id INTEGER,
    reorder_threshold INTEGER NOT NULL DEFAULT 10 CHECK (reorder_threshold >= 0),
    reorder_quantity INTEGER NOT NULL DEFAULT 50 CHECK (reorder_quantity >= 0),
    last_restocked_at TEXT,  -- NULL until actually restocked

    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
);

--Chufeng
CREATE UNIQUE INDEX IF NOT EXISTS idx_products_name_unique
ON products (LOWER(TRIM(name)));

CREATE TABLE IF NOT EXISTS cart_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL UNIQUE,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);
