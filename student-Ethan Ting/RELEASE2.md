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

## Remaining steps

- Review these local security changes, then retain hook execution during a real commit.
- Publish the final version and retain a new passing student-3 CI run for that commit.
- Configure this feature's Release 2 review evidence using the latest shared modes.
- Validate the integrated local application and final cloud deployment.
- Update individual diagrams, report contribution and demonstration evidence.

This file does not certify the shared AWS deployment or the group's completion.
