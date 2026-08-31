INSERT OR IGNORE INTO support_tickets (
    id, customer_user_id, customer_name_snapshot, customer_email_snapshot,
    subject, category, priority, status, assigned_to, triage_applied_by, created_at, updated_at
) VALUES
    (2001, '5', 'Mia Wilson', 'mia@example.test', 'Order confirmation has not arrived', 'order', 'urgent', 'open', NULL, 'Alex Morgan', '2026-08-24T10:40:00Z', '2026-08-24T11:32:00Z'),
    (2002, '2', 'Demo Customer', 'customer@asd.local', 'Parcel marked delivered but not received', 'delivery', 'high', 'open', 'Alex Morgan', 'Alex Morgan', '2026-08-24T09:15:00Z', '2026-08-24T10:02:00Z'),
    (2003, '3', 'Ava Chen', 'ava@example.test', 'Help returning the wrong size', 'return', 'medium', 'pending', 'Jordan Lee', 'Jordan Lee', '2026-08-23T14:15:00Z', '2026-08-23T16:45:00Z'),
    (2004, '6', 'Noah Brown', 'noah@example.test', 'Duplicate charge on my card', 'payment', 'high', 'solved', 'Alex Morgan', 'Alex Morgan', '2026-08-23T11:10:00Z', '2026-08-23T14:30:00Z'),
    (2005, '4', 'Liam Smith', 'liam@example.test', 'Question about product warranty', 'product', 'low', 'solved', 'Jordan Lee', 'Jordan Lee', '2026-08-22T09:45:00Z', '2026-08-22T15:10:00Z'),
    (2006, '9', 'Zoe Thomas', 'zoe@example.test', 'Unable to reset account password', 'account', 'medium', 'open', NULL, NULL, '2026-08-22T08:54:00Z', '2026-08-22T10:24:00Z'),
    (2007, '7', 'Isla Taylor', 'isla@example.test', 'Delivery address needs correction', 'delivery', 'medium', 'pending', 'Alex Morgan', 'Alex Morgan', '2026-08-21T12:05:00Z', '2026-08-21T16:18:00Z'),
    (2008, '8', 'Jack Anderson', 'jack@example.test', 'Item arrived with a missing part', 'product', 'high', 'open', 'Jordan Lee', 'Jordan Lee', '2026-08-21T11:30:00Z', '2026-08-21T13:47:00Z'),
    (2009, '3', 'Ava Chen', 'ava@example.test', 'Refund confirmed, funds not visible', 'payment', 'medium', 'solved', 'Alex Morgan', 'Alex Morgan', '2026-08-20T13:12:00Z', '2026-08-20T17:12:00Z'),
    (2010, '10', 'Leo Martin', 'leo@example.test', 'Need an invoice for a recent order', 'order', 'low', 'pending', NULL, NULL, '2026-08-20T09:00:00Z', '2026-08-20T11:06:00Z'),
    (2011, '7', 'Isla Taylor', 'isla@example.test', 'Product colour differs from photos', 'unclassified', 'unclassified', 'needs_triage', NULL, NULL, '2026-08-19T12:42:00Z', '2026-08-19T15:41:00Z'),
    (2012, '4', 'Liam Smith', 'liam@example.test', 'Order is still processing', 'unclassified', 'unclassified', 'needs_triage', NULL, NULL, '2026-08-19T08:30:00Z', '2026-08-19T09:22:00Z');

INSERT OR IGNORE INTO support_ticket_messages (id, ticket_id, sender_role, author_name, message, created_at) VALUES
    (3001, 2001, 'customer', 'Mia Wilson', 'I placed an order yesterday but have not received a confirmation email or order number.', '2026-08-24T10:40:00Z'),
    (3002, 2002, 'customer', 'Demo Customer', 'My tracking page says my parcel was delivered this morning, but it is not at my address. I checked with my neighbours.', '2026-08-24T09:15:00Z'),
    (3003, 2002, 'staff', 'Alex Morgan', 'Thanks for letting us know. Can you confirm that the delivery address shown in your order confirmation is correct?', '2026-08-24T09:31:00Z'),
    (3004, 2002, 'customer', 'Demo Customer', 'Yes, the address is correct. I also checked the lobby and parcel lockers but could not find it.', '2026-08-24T09:42:00Z'),
    (3005, 2003, 'customer', 'Ava Chen', 'The item I received is the wrong size. I need the return instructions and a label.', '2026-08-23T14:15:00Z'),
    (3006, 2003, 'staff', 'Jordan Lee', 'Please confirm whether the item is unworn and still has its original tags so I can issue the correct label.', '2026-08-23T16:45:00Z'),
    (3007, 2004, 'customer', 'Noah Brown', 'I can see two charges for the same order on my bank statement.', '2026-08-23T11:10:00Z'),
    (3008, 2004, 'staff', 'Alex Morgan', 'We found a duplicate authorisation and released it. Your bank should remove the pending charge shortly.', '2026-08-23T14:30:00Z'),
    (3009, 2005, 'customer', 'Liam Smith', 'Could you clarify how long the warranty lasts for the headphones I purchased?', '2026-08-22T09:45:00Z'),
    (3010, 2005, 'staff', 'Jordan Lee', 'The headphones include a two-year warranty from the purchase date. I have emailed the warranty terms.', '2026-08-22T15:10:00Z'),
    (3011, 2006, 'customer', 'Zoe Thomas', 'The password reset email does not appear in my inbox or spam folder.', '2026-08-22T08:54:00Z'),
    (3012, 2007, 'customer', 'Isla Taylor', 'I entered the apartment number incorrectly and need to know whether the delivery address can still be changed.', '2026-08-21T12:05:00Z'),
    (3013, 2007, 'staff', 'Alex Morgan', 'The parcel has not left our warehouse. Please reply with the correct apartment number and I will update it.', '2026-08-21T16:18:00Z'),
    (3014, 2008, 'customer', 'Jack Anderson', 'The product arrived without the charging cable shown in the product listing.', '2026-08-21T11:30:00Z'),
    (3015, 2009, 'customer', 'Ava Chen', 'I received a refund confirmation but the money is not visible in my account yet.', '2026-08-20T13:12:00Z'),
    (3016, 2009, 'staff', 'Alex Morgan', 'The refund was processed successfully. Most banks display the funds within three to five business days.', '2026-08-20T17:12:00Z'),
    (3017, 2010, 'customer', 'Leo Martin', 'I need a tax invoice with the billing details for an order placed last week.', '2026-08-20T09:00:00Z'),
    (3018, 2010, 'staff', 'Support staff', 'Please reply with the order number and the billing business name that should appear on the invoice.', '2026-08-20T11:06:00Z'),
    (3019, 2011, 'customer', 'Isla Taylor', 'The colour of the product I received looks different from the listing photos.', '2026-08-19T12:42:00Z'),
    (3020, 2012, 'customer', 'Liam Smith', 'My order has been processing for several days and I would like an update.', '2026-08-19T08:30:00Z');
