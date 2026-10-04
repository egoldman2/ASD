# Customer accounts and loyalty: implemented guide

This guide describes the implemented ASD 2026 accounts and loyalty feature. It contains no customer records. For a live customer's details, use the protected account and loyalty screens, not this knowledge guide.

## Customer registration

Customers can create their own account using a full name, email address, password and password confirmation. A full name is required and is limited to 100 characters. The email must be valid. The password must contain at least 8 characters and match its confirmation. Successful registration signs the new customer in.

Registration creates a customer account, not an administrator account. Email addresses must be unique; an email already in use is rejected. Email addresses are trimmed and stored in lowercase. Registration also creates a loyalty account with zero points and the Bronze tier.

## Account access and changes

Customers can view and update their own name and email on their account page. Customers can change their own password by supplying the current password and a different new password. Administrators can view and manage customer and administrator accounts through protected admin pages. An AI-suggested customer name or email change is only a proposal; an administrator must review and confirm it before the normal protected update endpoint saves it.

## Updating a customer profile

To update their profile, a signed-in customer opens My account, edits Full name or Email address, and selects Save changes. The full name is required and must be 100 characters or fewer. The email must be valid and not already used by another account. The profile update cannot change the customer's role or active status. After saving an email change, use the new email address for future sign-ins.

## Changing a customer password

To change a password, a signed-in customer opens My account and the Change password section. Enter Current password, New password and Confirm new password, then select Change password. The current password must be correct. The new password must contain at least 8 characters, match its confirmation and be different from the current password. A missing field, incorrect current password, short new password, mismatched confirmation or reused password is rejected without changing the stored password. Use the new password for future sign-ins. Never enter a password into the assistant or guide.

## Forgotten passwords and sign-in problems

The customer password-change form requires the current password. This feature has no self-service forgotten-password email, recovery link or one-time-code flow. It cannot send a password reset email. For sign-in, use the account's current email and password. Disabled accounts cannot sign in. Protected requests recheck that the account is still active. Logging out clears the current session; another protected request requires signing in again. This guide cannot reactivate an account or sign a user in.

## Loyalty tiers

Bronze covers 0 to 499 points. Silver covers 500 to 999 points. Gold begins at 1,000 points. Bronze customers reach Silver at 500 points; Silver customers reach Gold at 1,000 points. Gold has no next tier. The points needed for the next tier equal the next threshold minus the current balance. A question about the Gold threshold asks for the required total balance, not the points remaining for a particular customer. This guide does not supply a live customer balance; do not assume that a selected customer has zero points. Use the live MCP progress tool for the points remaining.

These are balance-based tiers, not a separate lifetime-spending total. For example, a balance of 720 points is Silver, with Gold next and 280 points remaining. Removing points can lower the tier when the balance falls below a threshold. No expiry schedule, annual reset or additional Gold tier is defined by this feature.

## Points adjustments and history

Administrators can add or remove points on the protected loyalty page. Each adjustment must be a nonzero whole number, no more than 1,000,000 points in absolute value, and include a reason of at most 200 characters. An adjustment cannot make the balance negative. Successful adjustments are recorded as loyalty transactions with the reason and administrator identity. Customers can view their own balance and recent transaction history; administrators can view customer loyalty accounts and histories.

Administrators can also ask the existing customer assistant for point history. The shared MCP tool `ethan_ting_get_loyalty_history` reads the latest 1 to 20 recorded point changes (default 5) for one customer identified by ID, email or exact full name. Ambiguous names require clarification. The administrator session is rechecked by the protected backend. The assistant displays recorded dates, point changes and reasons without model-generated transactions or account edits. This guide describes that capability; RAG itself does not retrieve live customer history.

## Getting loyalty points

Customers get loyalty points when an administrator manually adds points with a recorded reason. The feature does not automatically award points for purchases. Purchases are not rewarded automatically, and there is no implemented points-per-dollar earning rate. Customers cannot add points themselves. New customer balances start at zero points. Ask an administrator to review recorded adjustments rather than assuming a purchase has earned points.

## Customer loyalty balance and history

Signed-in customers open My account to view their current loyalty balance, tier, progress to the next tier and recent point history. A positive history entry adds points; a negative entry removes points. Each recorded entry includes a date, point change and reason. No recorded adjustments means the history can be empty; it does not mean the request failed. Customers cannot award themselves points through the account page.

## Administrator loyalty tools

Administrators open Loyalty to review customer balances and make a manual points adjustment with a reason. In Customer assistant, select the customer and use Check progress for their live tier or Point history for their latest 5 recorded adjustments. These MCP tools are read-only. Ask the guide explains the documented rules instead of reading the selected customer's live balance or history. For a point dispute, review the recorded adjustments; this guide does not promise refunds or automatically correct a balance.

Only administrators can access Customer assistant, Check progress, Point history and Ask the guide. These administrator tools are not available to customer-role accounts. Customers use their own My account page to see their balance and history instead.

## Not implemented by this feature

The accounts and loyalty feature does not automatically award points for purchases or define a points-per-dollar earning rate. It does not provide a customer-facing reward catalogue, vouchers, or a monetary value for points. Administrators can manually remove points through a recorded adjustment, but this guide does not define what merchandise or benefits that represents. A missing rule should not be presented as a promise to customers.
