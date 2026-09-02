# Release 0 Evidence

This directory stores assessment evidence generated from the integrated
application. Agentic review records are saved in `agentic/` and retain all four
Plan -> Act -> Observe -> Adapt stages:

1. the feature prompt and read-only collected evidence;
2. the model's initial review;
3. reviewer and deterministic grounding feedback; and
4. the final adapted review.

The final review is the verified conclusion. Earlier sections are intentionally
retained to demonstrate how an inaccurate or incomplete model response was
observed and corrected; they must not be presented as confirmed findings.

## Ethan Goldman evidence

- Database review: verifies the Customer Support tables, seeded counts,
  constraints, message-to-ticket foreign key, and redaction of identity,
  contact, author, and ticket-message samples.
- Implementation review: inspects the CRUD, authentication, validation,
  database-API, HTMX, and advisory AI code paths.
- Architecture review: inspects frontend/backend/database separation, private
  SQLite ownership, HTTP service boundaries, persistence, and Ollama wiring.
- DevOps review: inspects Ethan's accepted contributor-named
  `EthanGoldman.yml`, image build, Compose checks, integration checks, real AI
  logging assertions, ownership check, and cleanup.

Static source reviews do not prove a successful remote GitHub Actions run.
Keep the workflow run URL/screenshot and a fresh Compose execution alongside
these generated reports as separate execution evidence.
The local test, live-Ollama, build, Compose, and whole-repository results are
recorded in `ethan-goldman-verification-20260901.md`.

## Ethan Ting evidence

- Database review: verifies the required customer and loyalty tables, minimum
  seeded counts, constraints, foreign keys, and password-hash redaction.
- Endpoint review: verifies `200` health/readiness checks and signed-out `401`
  protection without changing application data.
- Architecture review: verifies service separation, database API ownership,
  session/role controls, tests, and the administrator-only runtime Customer
  Insight integration. Regenerate this report after material AI changes so its
  final review reflects the current implementation.

The collector is read-only. Configured personal fields, password hashes, and
secret-like fields are replaced with `<redacted>` before model input and before
a report is saved. Reproduction commands are documented in
`ai-services/ollama/README.md`.
