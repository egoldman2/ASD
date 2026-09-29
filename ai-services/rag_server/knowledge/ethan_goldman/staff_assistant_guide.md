# Customer Support staff assistant guide

## Queue totals and ticket attention

The queue summary counts all tickets matching the selected category and assignee filters, rather than just the displayed page. Unresolved means any ticket whose status is not solved. The unresolved unassigned count includes only unresolved tickets without an assigned staff member.

The attention list includes unresolved tickets with any of these reasons: needs triage, unassigned, high or urgent priority, latest message from the customer, or inactivity. A ticket can have several reasons. Solved tickets are excluded. Results are ordered by priority urgency, then oldest activity, then ticket ID before pagination. The inactivity default is 48 hours and staff can select 1 to 720 hours. Activity uses the later of the ticket update and its latest message. Inactivity is a review heuristic, not a promised response time or service-level agreement.

Source: student-Ethan Goldman/database_service/database.py and support_backend/tool_reads.py. Reviewed against the implemented application on 27 September 2026.

## Choosing a staff question

Use the support data assistant for current ticket facts, searches, queue totals and attention reasons. Ticket context shows a bounded selection of the newest conversation messages in chronological order and reports when earlier messages were omitted. Search and attention results report the full matching count and whether another page exists. These reads do not change ticket records.

Use the support knowledge assistant for the documented workflow, ticket field limits, triage states and the meaning of queue metrics. Knowledge answers are based on curated guidance, not live customer conversations. Knowledge does not establish refund periods, warranty terms, compensation entitlements or response deadlines. Staff must consult an approved policy before promising an outcome. AI suggestions do not save changes or send replies; staff remain responsible for explicit actions.

Source: student-Ethan Goldman/support_backend/mcp_assistant.py, ui.py and validation.py. Reviewed against the implemented application on 27 September 2026. This guide contains no customer ticket data.
