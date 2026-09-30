# Customer accounts and loyalty: implemented guide

This guide describes the implemented ASD 2026 accounts and loyalty feature. It contains no customer records. For a live customer's details, use the protected account and loyalty screens, not this knowledge guide.

## Customer registration

Customers can create their own account using a full name, email address, password and password confirmation. A full name is required and is limited to 100 characters. The email must be valid. The password must contain at least 8 characters and match its confirmation. Successful registration signs the new customer in.

## Account access and changes

Customers can view and update their own name and email on their account page. Customers can change their own password by supplying the current password and a different new password. Administrators can view and manage customer and administrator accounts through protected admin pages. An AI-suggested customer name or email change is only a proposal; an administrator must review and confirm it before the normal protected update endpoint saves it.

## Loyalty tiers

Customer loyalty balances start at zero points. Bronze covers 0 to 499 points. Silver covers 500 to 999 points. Gold begins at 1,000 points. Bronze customers reach Silver at 500 points; Silver customers reach Gold at 1,000 points. Gold has no next tier. The points needed for the next tier equal the next threshold minus the current balance.

## Points adjustments and history

Administrators can add or remove points on the protected loyalty page. Each adjustment must be a nonzero whole number, no more than 1,000,000 points in absolute value, and include a reason of at most 200 characters. An adjustment cannot make the balance negative. Successful adjustments are recorded as loyalty transactions with the reason and administrator identity. Customers can view their own balance and recent transaction history; administrators can view customer loyalty accounts and histories.

## Not implemented by this feature

The accounts and loyalty feature does not automatically award points for purchases or define a points-per-dollar earning rate. It does not provide a customer-facing reward catalogue, vouchers, or a monetary value for points. Administrators can manually remove points through a recorded adjustment, but this guide does not define what merchandise or benefits that represents. A missing rule should not be presented as a promise to customers.
