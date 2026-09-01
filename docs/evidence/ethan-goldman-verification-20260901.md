# Ethan Goldman Release 0 Verification — 1 September 2026

This record covers executable checks run for Ethan Goldman's Customer Support
feature. It is not evidence of a remote GitHub Actions run.

## Focused tests

The complete Customer Support suite was run in the existing Python 3.11 test
image on the Compose network, with the gated live-AI test enabled against the
real `ollama` service and installed `qwen2.5:0.5b` model.

```text
........................                                                 [100%]
24 passed in 25.18s
```

The focused suite covers live Flask service boundaries, customer/admin roles,
ticket ownership and CRUD, HTMX fragments, origin and validation failures,
database migration, AI privacy and action policy, outage handling, a genuine
Ollama response, response validation, Plan -> Act -> Observe -> Adapt logs, and
proof that AI analysis does not mutate the ticket database.

## Build and Compose checks

- The `student-Ethan Goldman/Dockerfile` test target built successfully.
- `docker compose config --quiet` completed successfully.
- `docker compose ps` showed `customer-support`,
  `customer-support-backend`, and `customer-support-database` running healthy;
  the required authentication services and Ollama were also healthy.

## Whole-repository suite

The repository-wide run completed with `70 passed, 6 failed, 1 skipped`. None
of the six failures are in `student-Ethan Goldman/`. They comprise one Chufeng
agentic-loop mock failure and five Ethan Ting test/configuration failures. This
means Goldman's slice is green, but the repository as a whole is not yet a
fully green submission.

## Retained agentic reviews

- `agentic/ethan-goldman-customer-support-database-20260901-225703.md`
- `agentic/ethan-goldman-customer-support-implementation-20260901-230637.md`
- `agentic/ethan-goldman-customer-support-architecture-20260901-231137.md`
- `agentic/ethan-goldman-customer-support-devops-20260901-231211.md`

Each report retains the initial model response, reviewer feedback, and final
adapted review. Unsupported small-model claims remain visible in the earlier
sections but were rejected; only each report's **Final Review** is the grounded
conclusion.

## Still external

A successful remote `EthanGoldman.yml` GitHub Actions run and its URL or
screenshot must still be captured from GitHub. Static workflow inspection,
local Docker builds, and local Compose health do not prove that remote run.
