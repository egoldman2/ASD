# Ethan Ting: GitHub Actions validation

## Final patch: 4 October 2026, 15:06 AEDT (Sydney)

- Assigned workflow: `.github/workflows/student-3.yml`
- Visible name: **Ethan Ting - Customer Accounts and Loyalty CI**
- Push on `main`, commit `2d261b0e038161aa5b50c9ab31f15f5b55edad3c` (implementation commit `be42f1e` included)
- [Successful run #66](https://github.com/egoldman2/ASD/actions/runs/37176044671): **Success**, 3 minutes 8 seconds
- [Test job](https://github.com/egoldman2/ASD/actions/runs/37176044671/job/111358735807): passed, 1 minute 14 seconds
- [Build and smoke-test job](https://github.com/egoldman2/ASD/actions/runs/37176044671/job/111358924649): passed, 1 minute 47 seconds
- [Final success screenshot](screenshots/ci-final-66.jpg)

Both jobs use disabled AI/MCP/RAG flags. The Docker invocation passes the flags explicitly, builds the four feature targets, starts the three application services, validates ordinary account operations and disabled integration endpoints, and cleans up. This is CI build/deployment validation on an ephemeral runner, not deployment to permanent hosting. GitHub's action-runtime and runner-image warnings were non-failing.

Fresh local RAG evidence is [captured here](screenshots/rag-final-validation.jpg), with full redacted [API results](final-local-validation.json). Review-loop reports and local suite counts are linked from the [evidence index](README.md).

## Historical run: 1 October

Verified on 1 October 2026 against the published `main` commit `9b793ac2b405b758ee14374a1a085b8c7a96ebeb`.

- Workflow: `.github/workflows/EthanTing.yml`
- Visible name: Ethan Ting - Customer Accounts and Loyalty CI
- Trigger: manual `workflow_dispatch` on `main`
- [Successful run #25](https://github.com/egoldman2/ASD/actions/runs/36736278891)
- Result: **Success**, total duration **3 minutes 6 seconds**
- [Summary screenshot](ci-run-25-success.jpg)

## Test job

[Test job logs](https://github.com/egoldman2/ASD/actions/runs/36736278891/job/109958732599)

| Suite | Result |
|---|---|
| Customer accounts and loyalty | 137 passed |
| Shared RAG scope and contract tests | 47 passed, 2 skipped |
| Shared MCP tool and protocol tests | 53 passed |

The job also initialised and verified the database and compiled the feature's Python modules. The two skipped tests require live model execution; live AI services are disabled for CI.

## Build and deployment checks

[Docker job logs](https://github.com/egoldman2/ASD/actions/runs/36736278891/job/109959281956)

The Docker job passed Compose validation, built the frontend, backend, database and test targets, ran the container tests, and started `ethan-database`, `ethan-backend` and `ethan-frontend` on the GitHub runner. It verified backend readiness, frontend access, customer and administrator login, profile and loyalty access, and role protection.

The workflow sets `AI_MODE_ENABLED=false`, `MCP_ENABLED=false` and `RAG_ENABLED=false`. The Docker test invocation passes those flags explicitly. With an authenticated administrator, the MCP loyalty-tier endpoint, RAG answer endpoint and existing AI Mode endpoint each returned the expected HTTP 503 while ordinary account functions remained usable. Cleanup also passed.

This workflow validates deployment on an ephemeral GitHub runner. It does not publish an image or deploy the application to a permanent hosting environment. Live MCP, RAG and AI Mode interactions are demonstrated separately on localhost.

GitHub reported non-failing notices about the actions' Node.js runtime and the future `ubuntu-latest` image migration. Neither job failed.
