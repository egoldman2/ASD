# Ethan Ting Release 1 evidence index

## Final local validation: 4 October 2026 (Sydney AEDT)

These final results supersede the historical counts and one-tool description below.

- Local deterministic suites: **392 passed, 2 skipped**, with AI/MCP/RAG disabled.
- Docker image `asd-ethan-ting-test:final`: **254 passed in 33.06 seconds**, with all three disabled flags explicitly passed into the container.
- [Protected API validation](final-local-validation.json): test customer #187 returned 720 points, Silver, Gold next and 280 remaining. Both MCP progress and recorded history succeeded. History was unchanged before/after.
- Fresh supported RAG returned the Gold total-balance threshold of 1,000 points, a real approved citation, medium retrieval confidence and actual model `llama3.1:8b`. An unrelated question returned insufficient context without citations or generation. The approved corpus contains 16 sections. The guide no longer assumes the selected customer's balance is zero.
- `docker compose config --quiet` and `git diff --check` passed.
- [Fresh MCP loop, 14:57 AEDT](../agentic/ethan-ting-customer-accounts-and-loyalty-mcp-20261004-145718.md): five tier boundaries and authenticated history passed. This run does not claim complete application AI assistant validation.
- [Fresh RAG loop, 15:01 AEDT](../agentic/ethan-ting-customer-accounts-and-loyalty-rag-20261004-150145.md): grounded-answer and unsupported-question live checks passed. Both reports retain the initial review, corrective feedback and final adapted output, including model mistakes.

The backend now allowlists two read-only tools: `ethan_ting_calculate_loyalty_tier` and `ethan_ting_get_loyalty_history`. Optional AI progress calculations must exactly match deterministic MCP results; unavailable or rejected AI falls back to the rule-based result. Confidence measures retrieval relevance, not factual accuracy.

The assigned workflow is `.github/workflows/student-3.yml`, still displayed as **Ethan Ting - Customer Accounts and Loyalty CI**. See [CI records](CI.md) for published runs. Earlier run #25 does not cover the final patch.

Screenshots are retained in `screenshots/` with their original dates, not relabelled as new runs. The [validation script](validate_local.py) reproduces protected checks using a disposable fixture, refreshes only the approved index and records redacted results without printing credentials or cookies. Existing diagrams were left unchanged.

## Historical validation: 29 September to 1 October

Captured locally on 29–30 September 2026 in the newer Desktop assessment checkout on `main`, with published GitHub Actions verification added on 1 October. These files document validation; the group report has not been submitted through this work.

On 30 September, this checkout was fast-forwarded by 18 commits to the then-current `origin/main`, and the existing uncommitted work was reapplied without merge conflicts. A recoverable pre-sync Git stash remains. The shared MCP/RAG registration checks, focused Python suite and Docker test image were rerun on the combined checkout.

## Browser results

For the second MCP tool added on 1 October, see the [loyalty history extension checks](LOYALTY_HISTORY.md).
These newer local checks are separate from the historical results and published CI run below.

| Check | Observed result | Evidence |
|---|---|---|
| MCP selected-customer check | Disposable customer #187 at 720 points returned Silver, Gold next and 280 points remaining. | Recorded local browser check; screenshot is not retained in this repository. |
| RAG supported question | “How many loyalty points are needed for Gold?” returned “According to [1], Gold begins at 1,000 points.” The UI showed model `llama3.1:8b`, medium retrieval confidence, and the approved guide source. | Recorded local browser check; screenshot is not retained in this repository. |
| RAG unrelated question | “quasar orbital spectroscopy wavelengths” returned the exact insufficient-context message and no sources. | Recorded local browser check; screenshot is not retained in this repository. |
| RAG service outage and retry | With the host RAG process stopped, the guide showed a useful unavailable-service error and kept the Ask guide control enabled. After restarting and refreshing the service, retrying the same Gold question returned a cited answer. | Recorded local browser checks; screenshots are not retained in this repository. |

The 720-point account was created solely for this check, had one 720-point setup adjustment, and was then **deactivated** via the normal administrator endpoint. Its record and audit transaction remain in the local SQLite volume by design; do not mistake them for production data. Immediately before and after the MCP browser request, its balance was 720 and its transaction count was one. The RAG questions did not send live customer records to the RAG service.

## Local service and test results

- Host MCP `GET http://127.0.0.1:8765/health`: healthy, Streamable HTTP `/mcp`, 13 registered shared tools after syncing the latest `main` and restarting the local process. The Ethan backend allowlist exposes only `ethan_ting_calculate_loyalty_tier`.
- Host RAG `GET http://127.0.0.1:5003/health`: healthy, scope `ethan_ting_accounts_loyalty` available alongside three teammate scopes, local model `llama3.1:8b`.
- Ethan corpus refresh indexed six knowledge sections from `ethan_ting_accounts_loyalty/accounts_and_loyalty.md`.
- Existing administrator Customer Insight AI Mode was checked live after the Release 1 changes: administrator login 200, read-only insight 200, actual model `llama3.1:8b`, and all four Plan/Act/Observe/Adapt workflow fields present. No edit was confirmed or saved.
- After syncing `main`, administrator login, an MCP tier lookup and a cited RAG Gold-threshold answer all returned 200 against the restarted shared host services. The MCP result declared `read_only: true` and the RAG result cited one approved guide passage.
- `.venv311/bin/python -m pytest 'student-Ethan Ting/tests' ai-services/mcp_server/tests ai-services/rag_server/tests -q`: **237 passed, 2 skipped** on the synced `main` checkout. The shared registry and test expectations were updated for Ryan's newly merged tools and RAG scope.
- Docker test image `asd-ethan-ting-test:release1` built and ran with `AI_MODE_ENABLED=false`, `MCP_ENABLED=false` and `RAG_ENABLED=false`: **137 passed**.
- Isolated disabled backend: anonymous profile 401; customer login, profile and loyalty 200; customer MCP admin route 403; admin login and customer list 200; MCP, RAG and AI Mode admin calls each 503. The temporary backend was stopped after this check.
- `docker compose config --quiet`, SVG XML validation and `git diff --check` passed locally.

The shared review loop ran both live modes, including the real five-boundary MCP probes and the grounded/unsupported RAG probes. Its first model drafts were too broad, and the review stage corrected them rather than recording unsupported claims as validated outcomes:

- [MCP Plan → Act → Observe → Adapt report](../agentic/ethan-ting-customer-accounts-and-loyalty-mcp-20260930-095809.md)
- [RAG Plan → Act → Observe → Adapt report](../agentic/ethan-ting-customer-accounts-and-loyalty-rag-20260930-100547.md)

The two report-ready SVGs are [deployment architecture](architecture.svg) and [MCP/RAG request flow](request-flow.svg). The [runbook](../../../student-Ethan%20Ting/RELEASE1.md) gives reproducible commands.

## Published CI validation

The published workflow was manually run on `main` commit `9b793ac` on 1 October 2026. [Run #25](https://github.com/egoldman2/ASD/actions/runs/36736278891) **passed both jobs** in 3 minutes 6 seconds. The Python suites reported 237 passed and 2 skipped; the Docker job built all four targets and passed container tests and the account, loyalty, permissions and disabled-mode deployment checks. [CI evidence](CI.md) includes the job links, configuration details and [success screenshot](ci-run-25-success.jpg). Add the run URL to the group PDF. The evidence notes and diagrams in this directory still need to be committed if they are to be included in the shared repository.
