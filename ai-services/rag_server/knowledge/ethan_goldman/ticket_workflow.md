# Customer Support ticket workflow

## Creating a customer ticket

A signed-in customer creates a support ticket using a subject and an initial message. The subject must contain 5 to 160 characters. The initial message must contain 1 to 2000 characters. Customer identity comes from the verified account session. New customer tickets begin with category unclassified, priority unclassified, status needs_triage, and no assigned staff member. Customers can read and reply only to their own tickets.

Source: student-Ethan Goldman/support_backend/validation.py, app.py and database_service/database.py. Reviewed against the implemented application on 27 September 2026. This knowledge contains application workflow facts, not private ticket records.

## Staff triage and ticket state

Signed-in administrators use the staff queue to search tickets and open a ticket workspace. Staff can explicitly save category, priority, status, and assignee changes, and send a reply as the verified staff user. Allowed ticket statuses are needs_triage, open, pending, and solved. Allowed priorities are unclassified, low, medium, high, and urgent. Allowed categories are unclassified, order, return, payment, product, delivery, account, and other. A blank assignee removes the assignment. These fields describe recorded state; no automatic status transition or promised response time is defined by these controls.

AI ticket analysis provides advisory suggestions. A staff member reviews suggestions before explicitly applying category and priority. The support data assistant reads tickets and generates explanations but cannot send replies, issue refunds, or save ticket changes. The application does not establish refund periods, compensation rules, or warranty entitlements; staff must consult an approved policy before promising an outcome.

Source: student-Ethan Goldman/support_backend/validation.py, ui.py and mcp_assistant.py. Reviewed against the implemented application on 27 September 2026.
