# Order and returns: implemented guide

This guide describes the implemented ASD 2026 order and returns feature. It contains no customer orders or personal records. For a live order or return, use the protected order and returns screens or the read-only assistant tools, not this knowledge guide.

## Orders overview

The order and returns feature manages customer orders, the items within each order, and return requests. Orders, order items, and returns are stored in three related tables, with each order item and each return linked to its parent order. Each order records the customer it belongs to, an order date, a status, and a total. The feature is seeded with sample orders, order items, and returns so it can be demonstrated with realistic data.

## Order status

Each order has a status that describes where it is in its lifecycle, such as pending, shipped, delivered, or cancelled. An order's status is changed only through the protected status endpoint by an administrator; it is never changed by the AI. Customers can view the status of their own orders.

## Creating and viewing orders

Orders can be created, listed, retrieved by identifier, updated, and deleted through the feature's REST API. Retrieving an order returns its details together with its associated order items. A signed-in customer sees only their own orders; an administrator sees all orders.

## Requesting a return

A customer requests a return for one of their existing orders by providing the order it relates to and a reason for the return. The return is created with a pending status and is linked to the original order. A return is always associated with an existing order; a return cannot be created without one. Customers can view the returns on their own orders.

## Approving or rejecting a return

Only an administrator can approve or reject a return. The administrator changes the return's status through the protected return status endpoint, and the new status, for example approved or rejected, is saved and shown against the return. Customers cannot change the status of a return themselves; they can only request one.

## Role-based access

Access is role-based and enforced in the backend, independent of the interface. A signed-in customer can view only their own orders and returns and can request new returns. An administrator can view all orders and returns and can change order and return status. Requests without a valid session are rejected, and status changes are rejected for non-administrators even if the request is sent directly to the API.

## AI return advice

The feature provides an AI advice capability for returns. For a selected return, the assistant produces a short summary of the problem and a recommended next customer-service action. This advice is advisory only: it never changes any order or return, and all status changes are made by administrators through the protected status endpoints. The advice uses a local language model and its exact wording can vary.

## Looking up orders and returns with the assistant

The feature exposes two read-only shared MCP tools. The tool howard_get_order_status looks up a single order by its identifier and returns the order's customer, order date, status, total, and number of items. The tool howard_get_return_details looks up a single return by its identifier and returns the return's order, reason, status, and creation date together with the related order's status and total. Both tools are read-only: they report stored information and never create, change, or delete an order or a return. This guide describes that capability; RAG itself does not retrieve live order or return records.

## Not handled by this feature

The order and returns feature does not include a checkout flow that creates orders from a shopping cart; orders are created through the orders API or seeded for demonstration. The AI advice never approves, rejects, or otherwise changes a return or an order. Return eligibility rules, refunds, and payment handling are not defined by this feature, and a missing rule should not be presented to a customer as a promise.
