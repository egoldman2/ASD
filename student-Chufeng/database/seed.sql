DELETE FROM cart_items;
DELETE FROM products;
DELETE FROM suppliers;
DELETE FROM sqlite_sequence WHERE name IN ('cart_items', 'products', 'suppliers');

INSERT INTO suppliers (name, contact_name, email, phone, address) VALUES
('Northline Electronics Supply', 'Priya Nair', 'priya.nair@northline-supply.com', '02 9123 4567', '14 Industrial Ave, Alexandria NSW 2015'),
('Harbor Tech Distributors', 'Marcus Chen', 'marcus.chen@harbortech.com.au', '02 9876 5432', '88 Dockside Rd, Botany NSW 2019'),
('Greenfield Home Goods', 'Ella Simmons', 'ella@greenfieldhome.com.au', '03 8123 9988', '5 Orchard St, Richmond VIC 3121'),
('Pinnacle Accessories Co.', 'Daniel Ostrowski', 'daniel@pinnacleacc.com', '07 3345 1290', '221 Riverside Pde, South Brisbane QLD 4101'),
('Wavefront Wearables', 'Tara Whitfield', 'tara.whitfield@wavefrontwear.com', '08 8234 7711', '9 Beacon Ln, Adelaide SA 5000');

INSERT INTO products (name, category, description, price, stock_quantity, status, supplier_id, reorder_threshold, reorder_quantity, last_restocked_at) VALUES
('Smart Home Hub', 'Smart Home', 'Central control device for connected home products.', 129.00, 24, 'active', (SELECT id FROM suppliers WHERE name = 'Greenfield Home Goods'), 15, 30, '2026-08-10 09:15:00'),
('Wireless Earbuds', 'Electronics', 'Compact wireless earbuds with long battery life.', 89.00, 36, 'active', (SELECT id FROM suppliers WHERE name = 'Harbor Tech Distributors'), 20, 50, '2026-08-15 11:00:00'),
('Fitness Watch', 'Wearables', 'Activity tracker with health monitoring and notifications.', 159.00, 18, 'active', (SELECT id FROM suppliers WHERE name = 'Wavefront Wearables'), 20, 40, '2026-08-05 14:30:00'),
('Portable Bluetooth Speaker', 'Electronics', 'Water-resistant speaker for indoor and outdoor use.', 74.50, 22, 'active', (SELECT id FROM suppliers WHERE name = 'Harbor Tech Distributors'), 15, 30, '2026-08-12 10:00:00'),
('USB-C Charging Dock', 'Accessories', 'Multi-port charging dock for phones, tablets, and laptops.', 49.99, 40, 'active', (SELECT id FROM suppliers WHERE name = 'Pinnacle Accessories Co.'), 25, 60, '2026-08-18 08:45:00'),
('Smart LED Desk Lamp', 'Smart Home', 'Adjustable desk lamp with brightness and colour controls.', 62.00, 15, 'active', (SELECT id FROM suppliers WHERE name = 'Greenfield Home Goods'), 18, 35, '2026-08-01 13:20:00'),
('Noise Cancelling Headphones', 'Electronics', 'Over-ear headphones with active noise cancellation.', 199.00, 10, 'active', (SELECT id FROM suppliers WHERE name = 'Northline Electronics Supply'), 15, 25, '2026-07-28 09:00:00'),
('Laptop Stand', 'Accessories', 'Ergonomic aluminium stand for laptops and tablets.', 39.00, 30, 'active', (SELECT id FROM suppliers WHERE name = 'Pinnacle Accessories Co.'), 20, 40, '2026-08-14 16:10:00'),
('Smart Security Camera', 'Smart Home', 'Indoor security camera with motion alerts.', 119.00, 14, 'active', (SELECT id FROM suppliers WHERE name = 'Northline Electronics Supply'), 15, 30, '2026-08-09 10:30:00'),
('Travel Power Adapter', 'Accessories', 'Universal travel adapter for international charging.', 29.99, 12, 'active', (SELECT id FROM suppliers WHERE name = 'Pinnacle Accessories Co.'), 20, 50, '2026-08-20 09:50:00'),
('Mechanical Keyboard', 'Electronics', 'Compact mechanical keyboard with adjustable backlighting.', 109.00, 20, 'active', (SELECT id FROM suppliers WHERE name = 'Harbor Tech Distributors'), 15, 30, '2026-08-11 12:00:00'),
('E-Reader', 'Electronics', 'Lightweight e-reader with a glare-free display.', 149.00, 16, 'active', (SELECT id FROM suppliers WHERE name = 'Northline Electronics Supply'), 15, 25, '2026-08-03 15:40:00');

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