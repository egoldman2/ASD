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

## Ethan Ting evidence

- Database review: verifies the required customer and loyalty tables, minimum
  seeded counts, constraints, foreign keys, and password-hash redaction.
- Endpoint review: verifies `200` health/readiness checks and signed-out `401`
  protection without changing application data.
- Architecture review: verifies service separation, database API ownership,
  session/role controls, tests, and the administrator-only runtime Customer
  Insight integration. Regenerate this report after material AI changes so its
  final review reflects the current implementation.

The collector is read-only. Password hashes and secret-like fields are replaced
with `<redacted>` before model input and before a report is saved. Reproduction
commands are documented in `ai-services/ollama/README.md`.
