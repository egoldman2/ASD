DELETE FROM cart_items;
DELETE FROM products;
DELETE FROM sqlite_sequence WHERE name IN ('cart_items', 'products');

INSERT INTO products (name, category, description, price, stock_quantity, status) VALUES
('Smart Home Hub', 'Smart Home', 'Central control device for connected home products.', 129.00, 24, 'active'),
('Wireless Earbuds', 'Electronics', 'Compact wireless earbuds with long battery life.', 89.00, 36, 'active'),
('Fitness Watch', 'Wearables', 'Activity tracker with health monitoring and notifications.', 159.00, 18, 'active'),
('Portable Bluetooth Speaker', 'Electronics', 'Water-resistant speaker for indoor and outdoor use.', 74.50, 22, 'active'),
('USB-C Charging Dock', 'Accessories', 'Multi-port charging dock for phones, tablets, and laptops.', 49.99, 40, 'active'),
('Smart LED Desk Lamp', 'Smart Home', 'Adjustable desk lamp with brightness and colour controls.', 62.00, 15, 'active'),
('Noise Cancelling Headphones', 'Electronics', 'Over-ear headphones with active noise cancellation.', 199.00, 10, 'active'),
('Laptop Stand', 'Accessories', 'Ergonomic aluminium stand for laptops and tablets.', 39.00, 30, 'active'),
('Smart Security Camera', 'Smart Home', 'Indoor security camera with motion alerts.', 119.00, 14, 'active'),
('Travel Power Adapter', 'Accessories', 'Universal travel adapter for international charging.', 29.99, 12, 'active'),
('Mechanical Keyboard', 'Electronics', 'Compact mechanical keyboard with adjustable backlighting.', 109.00, 20, 'active'),
('E-Reader', 'Electronics', 'Lightweight e-reader with a glare-free display.', 149.00, 16, 'active');

INSERT INTO cart_items (product_id, quantity) VALUES
((SELECT id FROM products WHERE name = 'Smart Home Hub'), 2),
((SELECT id FROM products WHERE name = 'Wireless Earbuds'), 1),
((SELECT id FROM products WHERE name = 'Fitness Watch'), 3),
((SELECT id FROM products WHERE name = 'Portable Bluetooth Speaker'), 2),
((SELECT id FROM products WHERE name = 'USB-C Charging Dock'), 4),
((SELECT id FROM products WHERE name = 'Smart LED Desk Lamp'), 1),
((SELECT id FROM products WHERE name = 'Noise Cancelling Headphones'), 2),
((SELECT id FROM products WHERE name = 'Laptop Stand'), 3),
((SELECT id FROM products WHERE name = 'Smart Security Camera'), 1),
((SELECT id FROM products WHERE name = 'Travel Power Adapter'), 2);
