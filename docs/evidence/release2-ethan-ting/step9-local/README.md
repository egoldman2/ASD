# Ethan Ting: local integration and commit-hook check

22 October 2026, Sydney time. This is a bounded local check of the current
Desktop checkout. It does not replace the saved exact-source AWS deployment
records or the required group demonstration.

## Running application

- Docker Compose built and started all 13 configured services. Their final
  listed state was `running`; the six frontend homepages on ports 8000–8005
  each returned HTTP 200.
- Ollama, MCP, RAG and the Multi-Agent server ran as host processes outside
  Docker. Health responses were HTTP 200. The MCP and RAG listeners were bound
  to `127.0.0.1`; the Multi-Agent server used port 5054.
- From the `ethan-backend` container, `host.docker.internal` health requests
  to MCP port 8765, RAG port 5003 and Multi-Agent port 5054 all returned 200.
- A real MCP protocol call from that container to
  `ethan_ting_calculate_loyalty_tier` with `points_balance=720` returned Silver,
  Gold next and 280 points remaining. The supplied test balance was not read
  from or written to a customer account.
- The local RAG service refreshed the approved
  `ethan_ting_accounts_loyalty` scope, then answered a Gold-threshold question
  with `llama3.1:8b`: 1,000 points, two citations and `low` retrieval confidence.
  The answer remains subject to human review; confidence is not accuracy.

## Tests and commit workflow

- `student-Ethan Ting/tests` plus the owned MCP tool tests: **387 passed** in
  37.22 seconds, with all four AI flags disabled for deterministic tests.
- New host-observation tests: **17 passed**.
- Commit `14d6cf9` was created through the normal Git hook. The terminal
  reported **Passed** for Ruff security rules, Detect committed secrets and
  Audit all Python dependencies. The hook temporarily stashed and restored
  the two modified local RAG cache files; they were not part of that commit.

This proves the named checks ran for the staged commit. It does not turn the
separate shared Testing Review into a pass: its published `d297a42` capture
still reports unresolved group findings. The current cloud release also lacks
a human release decision. The local commit is not a GitHub Actions result or an
AWS deployment; pushing a new SHA will require fresh same-source CI and cloud
validation. No customer CRUD action was performed during this local check.
