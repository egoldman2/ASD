# Loyalty history MCP extension

Implemented and checked locally on 1 October 2026, on the Desktop checkout's
`main` branch. These changes are not committed or published yet. GitHub Actions
run #25 predates this extension; it must not be presented as its CI evidence.

## What changed

- A second Ethan tool, `ethan_ting_get_loyalty_history`, is registered in the
  existing shared host MCP server. It reads 1 to 20 recent transactions.
- The existing customer assistant routes explicit loyalty/point-history
  questions to this tool and displays dates, point changes and reasons in a
  table. No new page, database schema or account mutation was added.
- The requesting administrator's signed session is forwarded through MCP
  transport headers, not tool arguments. A fixed protected backend endpoint
  rechecks the administrator's active role and reads the database API.
- A shared validator rejects wrong customer identities, unexpected counts,
  malformed rows, duplicate transaction IDs and invalid timestamps. It strips
  unapproved fields, including administrator names. The frontend creates cells
  with `textContent`, not HTML from transaction reasons.
- History routing is deterministic. This does not claim model-selected tool
  calls or a multi-turn conversational memory feature.

## Validation

- Python feature, shared MCP and shared RAG suites: **316 passed, 2 skipped**.
  The two skipped tests are optional live-model RAG checks.
- Rebuilt Docker test image `asd-ethan-ting-test:history`: **191 passed** with
  AI Mode, MCP and RAG disabled at container startup.
- The new tests exercise strict arguments, bounded upstream output, HTTP
  errors/timeouts, unauthenticated and customer denial, current role/activity
  checks, ambiguity, conflicting identities, empty history and retry.
- A real MCP SDK/ASGI transport calls an HTTP feature backend in the isolated
  integration test. Admin access succeeds; customer and forged sessions fail.
- The browser retrieved Demo Customer #2's existing +120-point seed transaction
  through the running host MCP and Docker backend. ID, email and exact-name
  lookups returned the same record. A missing customer prompted clarification;
  a 21-row request showed a useful error and left Ask AI enabled. Jordan #61's
  history was explicitly empty.
- At a 390-pixel browser width, the history table remained inside the page;
  document content width and viewport width both measured 390 pixels. The
  viewport was reset afterward. No browser warning/error was observed.
- Before/after hashes of the current customer list, balances and Customer #2's
  transaction history matched across repeated API reads. No points or account
  records were changed for this extension's live checks.
- Docker Compose configuration and JavaScript syntax checks passed. Frontend
  and backend images were rebuilt without replacing the database volume.
- The host RAG guide was restarted and refreshed after the documentation
  update. A live Gold question returned 1,000 points with one real citation,
  `llama3.1:8b` and medium retrieval confidence. The unrelated astronomy
  question still returned insufficient context without citations.
- The workflow retains its `EthanTing.yml` name and now checks that the new
  protected data endpoint returns 503 when MCP is disabled. Existing suites
  automatically include the new tests.

## Shared review loop

The [actual MCP report](../agentic/ethan-ting-customer-accounts-and-loyalty-mcp-20261001-025434.md)
includes the five tier-boundary probes and the authenticated history probe.
All six passed. The model draft invented a boundary discrepancy; grounding
checks rejected its prose and the Adapt stage saved a verified evidence
summary. The report preserves the original draft, feedback and final result.
It does not establish model-selected application tool use.

See the [runbook](../../../student-Ethan%20Ting/RELEASE1.md) for host startup,
tests and securely supplying the review process's administrator session.
