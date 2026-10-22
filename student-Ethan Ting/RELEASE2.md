# Release 2: Customer Accounts and Loyalty

## Step 1: shared Multi-Agent integration

Accounts and Loyalty use the same `customer-assistant.js` component and dashboard
stylesheet. Its **Loyalty review** tab uses `shared/multi_agent_client.py`, not a
second Multi-Agent server or a copy of another feature's client.

An administrator selects a customer and starts a fixed, read-only loyalty review.
The backend rechecks administrator access and collects the customer's balance and
five recent transactions from the database API. It sends only an internal customer
ID, approved transaction fields, thresholds and rules-based progress to the host
server. Names, emails, password hashes, sessions and reviewer identities supplied
by the browser are not forwarded as evidence.

Planner, Worker and Reviewer results are shown separately, with actual model names,
evidence, workflow ID and Sydney display time. Model output is **not guaranteed
correct**. The UI shows independently calculated progress alongside the AI results.
The administrator must select a decision and supply a reason. Accept, partially
accept and reject record a workflow decision only; no account or points changes
are performed. A recorded decision cannot be overwritten through this interface.

### Backend endpoints (administrator session required)

| Method | Endpoint | Input / behaviour |
| --- | --- | --- |
| POST | `/api/admin/multi-agent/workflows` | Only `{"user_id":187}`; backend collects evidence |
| GET | `/api/admin/multi-agent/workflows?user_id=187` | Last 20 stored reviews for that customer |
| GET | `/api/admin/multi-agent/workflows/<id>` | One validated customer-loyalty workflow |
| POST | `/api/admin/multi-agent/workflows/<id>/review` | `decision` and `reason`; reviewer ID comes from authenticated session |

Use **Load latest review** after a timeout before starting again: a timed-out
request may still finish on the host. Workflow history and coordination audit logs
belong to the shared server's configured log directory, not the customer database.

### Local startup

From the repository root, install the pinned requirements in the existing Python
3.11 environment:

```bash
.venv311/bin/python -m pip install -r requirements.txt -r ai-services/multi_agent_server/requirements.txt
```

Start Ollama with the configured Planner/Worker/Reviewer models installed. Start
the shared server outside Docker in one terminal:

```bash
OLLAMA_WORKER_MODEL=llama3.1:8b OLLAMA_TIMEOUT_SECONDS=120 PYTHONPATH=ai-services .venv311/bin/python -m multi_agent_server.app
```

The default server port is 5004. If another service owns that port, do not stop it
without checking. For example, use `MULTI_AGENT_PORT=5054` on the server command and
`MULTI_AGENT_SERVER_URL=http://host.docker.internal:5054` on the Compose command:

The Worker override above was used for the successful local check. The shared
default `qwen2.5:0.5b` Worker misread the loyalty thresholds in two retained runs.
This environment override does not change the team's committed server defaults.

For a full local team demonstration on this Mac, start the existing Compose
services first. Keep the product database's published port on loopback and point
both backends at the already running host Multi-Agent server on port 5054:

```bash
PRODUCT_DATABASE_HOST_PORT=127.0.0.1:6001 \
MULTI_AGENT_SERVER_URL=http://host.docker.internal:5054 \
  docker compose up -d --build
```

Then start the shared MCP and RAG services in separate host terminals, outside
Docker. The Docker backends can reach these loopback listeners through
`host.docker.internal` on this Mac:

```bash
MCP_HOST=127.0.0.1 PYTHONPATH=ai-services \
  .venv311/bin/python -m mcp_server.server
```

```bash
OLLAMA_MODEL=llama3.1:8b RAG_HOST=127.0.0.1 PYTHONPATH=ai-services \
  .venv311/bin/python -m rag_server.rag_http_server
```

Ollama and the Multi-Agent server also run on the host. Refresh the approved
`ethan_ting_accounts_loyalty` RAG scope after changing its source documents.
On 22 October 2026, all 13 Compose services were running, all six frontend
homepages returned HTTP 200, and the Ethan backend container reached the MCP,
RAG and Multi-Agent health endpoints. A live backend-container MCP call returned
Silver and 280 points to Gold for a supplied 720-point balance. The local RAG
service retrieved the approved guide and answered the Gold-threshold question
with citations. These checks do not substitute for the group showcase or prove
that all customer workflows were tested end to end.

```bash
AI_MODE_ENABLED=true MULTI_AGENT_ENABLED=true docker compose up -d --build ethan-database ethan-backend ethan-frontend
```

Open `http://localhost:8003/admin-loyalty.html`, sign in as an administrator, then
select **Loyalty review**. Default backend-to-host timeout is 300 seconds. Setting
either `AI_MODE_ENABLED=false` or `MULTI_AGENT_ENABLED=false` prevents workflow
requests. The existing cloud baseline already sets both false.

### Tests

```bash
AI_MODE_ENABLED=false MCP_ENABLED=false RAG_ENABLED=false MULTI_AGENT_ENABLED=false \
  .venv311/bin/python -m pytest 'student-Ethan Ting/tests' \
  ai-services/multi_agent_server/tests shared/tests/test_shared_multi_agent_client.py -q
```

Boundary tests inject host HTTP responses; they are not live model evidence.
Live review results can contain factual errors even when every agent completes.
Keep incorrect results and the human correction/rejection as evidence, rather than
describing schema validation as factual verification.

## Step 2: security hooks and endpoint CI

The existing pre-commit hook is installed in this Desktop checkout. Native
backend/database servers default to loopback, while their Docker targets explicitly
set `APP_HOST=0.0.0.0`. Backend service URLs are restricted to configured HTTP(S)
origins and application API paths; service redirects are rejected. Regression tests
check malicious URL inputs, redirect rejection, fixed SQL assignments and literal
storage of SQL-looking customer names in an isolated test database.

Capture current scans without changing the Git index or creating a commit:

```bash
.venv311/bin/python 'student-Ethan Ting/scripts/capture_release2_security.py'
```

The [Step 2 report and actual output](../docs/evidence/release2-ethan-ting/step2/README.md)
distinguish passing feature-scoped hooks from remaining whole-repository findings
and the four existing dependency-advisory exceptions. The published `student-3.yml`
run for `4d635cc` already passed both allocated endpoint tests and Docker validation.
That run does **not** cover subsequent uncommitted security changes. No commit-time
execution is claimed until the user makes a real commit; the hook will run then.

## Step 3: current shared Testing Review

The Step 2 changes and Docker test-fixture repair are published in source
`4fa1ac8`. Its student-3 workflow passed, including the full Docker test job.
All five exact-source team workflows and ten allocated endpoint tests were
captured and validated in the [current Testing Review evidence](../docs/evidence/release2-ethan-ting/step3-testing/README.md).

The live shared review completed with `llama3.1:8b`, retaining initial review,
feedback, adaptation and deterministic validation. The overall testing gate is
still **fail** because group security findings remain. Secret baseline matches
and baseline-hash metadata are classified separately, without modifying raw
results or waiving the failed gate. No human release approval is recorded.

## Step 4: selected loyalty Multi-Agent Review

This feature now configures the shared `multi-agent` review mode, restricted to an
explicit `customer_loyalty` workflow ID. The base prompt identifies Release 2 and
distinguishes unassessed sources from proven missing functionality. The review
checks matching history/audit logs without creating workflows or human decisions.

The [Multi-Agent Review evidence](../docs/evidence/release2-ethan-ting/step4-multi-agent/README.md)
retains the initial review, the context-budget failure, the compact rerun, source
hashes and test reports. The wrapper compares observations/log hashes before and
after review. Historical automated UI acceptance is not new student participation
or a release approval. The configuration/prompt/tests were subsequently published
in `7218c43`; its Ethan Ting CI run and AWS deployment succeeded. The Step 4
captures retain their original, pre-publication provenance.

## Step 5: shared Cloud Deployment Report Review

The [Cloud Deployment Review evidence](../docs/evidence/release2-ethan-ting/step5-cloud/README.md)
retains exact-source native Actions artifacts, verified ZIP/file hashes and a
real shared Plan → Act → Observe → Adapt review with local `llama3.1:8b`.
The existing default group manifest and teammates' evidence are unchanged.

For `7218c43`, cloud Actions, the five-student workflow gate and recorded SSM
acceptance pass. The full review remains **incomplete**: public-smoke/runtime
capture bytes, a same-release health window and human release approval are not
supplied. The model incorrectly inferred observed CRUD/disabled responses; the
final deterministic summary preserves the missing evidence instead. Customer
browser sign-in is separately pending. No AWS mutation or redeployment occurred.
The new capture helper/tests and evidence remain local for review.

## Step 6: retrieved cloud records and measured health

The [Step 6 cloud evidence](../docs/evidence/release2-ethan-ting/step6-cloud/README.md)
now supplies the missing native public-smoke/runtime bytes and a measured health
window. The user published `d297a42` during this task, so new same-source Actions
artifacts and a fresh 120-second observation were captured for that deployment;
the earlier `7218c43` observation remains separate historical evidence.

For `d297a42`, all six technical checks pass: deployment acceptance, cloud Actions,
five-student gate, 67 recorded public checks, disabled runtime baseline and stable
health across 14 containers with no new OOM kills or restarts. The shared PAOA
review completed locally. Overall status is still **incomplete** solely because
no human release decision is recorded. It does not clear the earlier group
security findings. The then-pending customer-browser login check is completed
separately in Step 7 below.

Only read-only SSM diagnostics and public-home GET observations were performed.
No application deployment or customer mutation was performed by this step. New
observer/assembler/tests, evidence and this documentation remain local for review.

## Step 7: customer cloud browser check

The user completed private sign-in for the temporary cloud customer. The
[customer-side evidence](../docs/evidence/release2-ethan-ting/step7-customer-cloud/README.md)
shows Assessment Test Updated, Silver tier, 720 available points, 280 points to
Gold and the +720 Cloud assessment test history entry. The observed URL is the
public cloud customer page, not localhost. Screenshot, visible page text and
verification metadata are retained. No account/password/points change or human
release approval was submitted during this read-only check.

## Step 8: refreshed security ownership and Testing Review

The [current security audit](../docs/evidence/release2-ethan-ting/step8-security/README.md)
uses an isolated clean copy of published `d297a42` so local Step 6/7 files are not
misrepresented as committed evidence. All five workflows and ten endpoint cases
pass for that source. Ethan Ting's current feature/MCP test scope has zero Ruff
findings and zero new unclassified secret matches, including local helper files.

The group scan retains 28 Ruff warnings (16 catalogue, 11 shared AI and one
historical evidence script), 75 raw secret detections (48 baseline metadata and
27 existing baseline matches), and four ChromaDB advisory IDs with existing
documented exceptions. Reviewed source context and owner actions are recorded;
these counts are not a count of confirmed exploits. No source, baseline,
dependency, hook, teammate code, release decision or cloud setting was changed.
The refreshed shared Testing Review remains **fail**, not a waived release gate.

## Remaining steps

- Retain genuine commit-hook output when available; manual hook runs are not commit-time evidence.
- Obtain owner-reviewed fixes or explicit policy decisions for the Step 8 findings, then retain fresh same-source scans/CI and rerun Testing Review.
- Review the local Step 6 observer/assembler/tests and Step 6/7 evidence before publishing; existing CI cannot certify new files.
- Record the student's own review/release decision and reasons; none was granted by this automation.
- Refresh cloud records if another release is deployed; the customer browser sign-in check is now complete.
- Update individual diagrams, report contribution and demonstration evidence.

This file does not certify the shared AWS deployment or the group's completion.
