INSERT INTO support_tickets (
    id, customer_name, customer_email, subject, category,
    priority, status, assigned_to, created_at, updated_at
) VALUES
  (1012, 'Mia Chen', 'mia.chen@example.com', 'Order confirmation has not arrived', 'order', 'urgent', 'open', NULL, '2026-08-24T10:40:00Z', '2026-08-24T11:32:00Z'),
  (1011, 'Oliver Jones', 'oliver.jones@example.com', 'Parcel marked delivered but not received', 'delivery', 'high', 'open', 'Alex Morgan', '2026-08-24T09:15:00Z', '2026-08-24T10:02:00Z'),
  (1010, 'Amelia Brown', 'amelia.brown@example.com', 'Need help returning the wrong size', 'return', 'medium', 'pending', 'Jordan Lee', '2026-08-23T14:15:00Z', '2026-08-23T16:45:00Z'),
  (1009, 'Noah Williams', 'noah.williams@example.com', 'Duplicate charge on my card', 'payment', 'high', 'solved', 'Alex Morgan', '2026-08-23T11:10:00Z', '2026-08-23T14:30:00Z'),
  (1008, 'Sophia Patel', 'sophia.patel@example.com', 'Question about product warranty', 'product', 'low', 'solved', 'Jordan Lee', '2026-08-22T09:45:00Z', '2026-08-22T15:10:00Z'),
  (1007, 'Liam Wilson', 'liam.wilson@example.com', 'Unable to reset account password', 'account', 'medium', 'open', NULL, '2026-08-22T08:54:00Z', '2026-08-22T10:24:00Z'),
  (1006, 'Emma Davis', 'emma.davis@example.com', 'Delivery address needs correction', 'delivery', 'medium', 'pending', 'Alex Morgan', '2026-08-21T12:05:00Z', '2026-08-21T16:18:00Z'),
  (1005, 'Jack Taylor', 'jack.taylor@example.com', 'Item arrived with missing part', 'product', 'high', 'open', 'Jordan Lee', '2026-08-21T11:30:00Z', '2026-08-21T13:47:00Z'),
  (1004, 'Ava Martin', 'ava.martin@example.com', 'Refund confirmed, funds not visible', 'payment', 'medium', 'solved', 'Alex Morgan', '2026-08-20T13:12:00Z', '2026-08-20T17:12:00Z'),
  (1003, 'Leo Nguyen', 'leo.nguyen@example.com', 'Need invoice for recent order', 'order', 'low', 'pending', NULL, '2026-08-20T09:00:00Z', '2026-08-20T11:06:00Z'),
  (1002, 'Isla Moore', 'isla.moore@example.com', 'Product colour differs from photos', 'product', 'low', 'solved', 'Jordan Lee', '2026-08-19T12:42:00Z', '2026-08-19T15:41:00Z'),
  (1001, 'Lucas Smith', 'lucas.smith@example.com', 'Order still processing', 'order', 'medium', 'open', 'Alex Morgan', '2026-08-19T08:30:00Z', '2026-08-19T09:22:00Z');

INSERT INTO support_ticket_messages (
    ticket_id, sender_role, author_name, message, created_at
) VALUES
  (1012, 'customer', 'Mia Chen', 'I placed an order yesterday but have not received a confirmation email or order number.', '2026-08-24T10:40:00Z'),
  (1011, 'customer', 'Oliver Jones', 'My tracking page says my parcel was delivered this morning, but it is not at my address. I have checked with my neighbours. Please let me know what happens next.', '2026-08-24T09:15:00Z'),
  (1011, 'staff', 'Alex Morgan', 'Thanks for letting us know. Can you confirm that the delivery address shown in your order confirmation is correct?', '2026-08-24T09:31:00Z'),
  (1011, 'customer', 'Oliver Jones', 'Yes, the address is correct. I also checked the lobby and parcel lockers but could not find it.', '2026-08-24T09:42:00Z'),
  (1011, 'staff', 'Alex Morgan', 'I have opened an investigation with the courier. Please send a photo of the safe-drop area if one is available.', '2026-08-24T09:50:00Z'),
  (1011, 'customer', 'Oliver Jones', 'I have the photo ready and can provide it. There was no parcel visible in the safe-drop area.', '2026-08-24T10:02:00Z'),
  (1010, 'customer', 'Amelia Brown', 'The item I received is the wrong size. I need the return instructions and a label.', '2026-08-23T14:15:00Z'),
  (1010, 'staff', 'Jordan Lee', 'Please confirm whether the item is unworn and still has its original tags so I can issue the correct label.', '2026-08-23T16:45:00Z'),
  (1009, 'customer', 'Noah Williams', 'I can see two charges for the same order on my bank statement.', '2026-08-23T11:10:00Z'),
  (1009, 'staff', 'Alex Morgan', 'We found a duplicate authorisation and released it. Your bank should remove the pending charge shortly.', '2026-08-23T14:30:00Z'),
  (1008, 'customer', 'Sophia Patel', 'Could you clarify how long the warranty lasts for the headphones I purchased?', '2026-08-22T09:45:00Z'),
  (1008, 'staff', 'Jordan Lee', 'The headphones include a two-year warranty from the purchase date. I have emailed the warranty terms.', '2026-08-22T15:10:00Z'),
  (1007, 'customer', 'Liam Wilson', 'The password reset email does not appear in my inbox or spam folder.', '2026-08-22T08:54:00Z'),
  (1006, 'customer', 'Emma Davis', 'I entered the apartment number incorrectly and need to know whether the delivery address can still be changed.', '2026-08-21T12:05:00Z'),
  (1006, 'staff', 'Alex Morgan', 'The parcel has not left our warehouse. Please reply with the correct apartment number and I will update it.', '2026-08-21T16:18:00Z'),
  (1005, 'customer', 'Jack Taylor', 'The product arrived without the charging cable shown in the product listing.', '2026-08-21T11:30:00Z'),
  (1004, 'customer', 'Ava Martin', 'I received a refund confirmation but the money is not visible in my account yet.', '2026-08-20T13:12:00Z'),
  (1004, 'staff', 'Alex Morgan', 'The refund was processed successfully. Most banks display the funds within three to five business days.', '2026-08-20T17:12:00Z'),
  (1003, 'customer', 'Leo Nguyen', 'I need a tax invoice with the billing details for an order placed last week.', '2026-08-20T09:00:00Z'),
  (1003, 'staff', 'Support staff', 'Please reply with the order number and the billing business name that should appear on the invoice.', '2026-08-20T11:06:00Z'),
  (1002, 'customer', 'Isla Moore', 'The colour of the product I received looks different from the listing photos.', '2026-08-19T12:42:00Z'),
  (1002, 'staff', 'Jordan Lee', 'We confirmed the item is from the correct colour batch and arranged a free return because it did not meet expectations.', '2026-08-19T15:41:00Z'),
  (1001, 'customer', 'Lucas Smith', 'My order has been processing for several days and I would like an update.', '2026-08-19T08:30:00Z');
