# Ethan Ting: Multi-Agent Review

22 October 2026, Sydney time. This step adds the customer-loyalty configuration
and prompt to the existing shared review loop, not another server or agent chain.
It does not change the application's account, points or workflow endpoints.

## What was checked

The read-only collector selected workflow
`ea8edb14-543a-4ec4-8666-86356b8e9e80`, explicitly restricted to
`customer_loyalty`, from the already-running host server on port 5054. It checked:

- Planner, Worker and Reviewer wiring and source order.
- Shared contract feature identifiers and HTTP endpoints.
- Administrator-only feature boundaries, fixed read-only request, safe evidence,
  verified rules-based progress and latest-five-history limitation.
- The selected workflow's evidence IDs, models, scope, timestamps and stage completion.
- Exact matching retained history and the ordered coordination audit, including
  the previously recorded decision.
- Matching observations and unchanged log hashes before and after the AI review.

The selected workflow was originally executed on 20 October. Its Planner used
`qwen2.5:0.5b`; Worker and Reviewer used `llama3.1:8b`. Its acceptance was recorded
during automated local UI validation. Reading it today is **not** a new three-agent
execution, new student participation, or a student release approval. The earlier
small-model errors remain preserved in Step 1. No new workflow or decision was
submitted, and no customer account or point balance was changed in this step.

## Runs and adaptation

1. `20261022/`: initial completed review and before/after checks. The AI followed
   a stale Release 1 base prompt and made unsupported claims about missing ordinary
   account/points tests. Those tests exist in `test_login_system.py` and
   `test_loyalty_edge_cases.py`, outside this mode's narrow source list. The shared
   grounding guard replaced the final unsupported model output with its evidence
   summary. The original outputs were not edited.
2. `20261022-refined/`: corrected Release 2 wording and explicit scope. This run
   reached initial review and reviewer feedback, but adaptation exceeded the
   shared 24,000-character prompt budget. Its error and console are retained.
3. `20261022-compact/`: reduced the source list from 21 to 14 relevant files,
   retaining all configured source checks and runtime boundaries. The shared
   prompt safety limit was not raised. This is the selected final capture.

The model review uses installed `llama3.1:8b` through an environment override.
It is a separate engineering review of historical workflow evidence, not a new
invocation of that workflow's Planner/Worker/Reviewer stages. Model assessments
still need critical reading; positive observations labelled High/Medium severity
or a wrongly attributed five-record limit are not proven application defects.
The five-record limit belongs to the feature's backend request preparation, not
the feature-neutral shared workflow store.

## Evidence and tests

- [Selected full AI review](../../agentic/ethan-ting-customer-accounts-and-loyalty-multi-agent-20261022-023240-456029.md)
  and [console](20261022-compact/review.console.txt): original model outputs,
  feedback and adaptation, including the incorrect store attribution noted above.
- [Selected validation](20261022-compact/validation.json): structural checks,
  source presence, runtime identity, unchanged logs and unchanged observation.
  All 17 checks passed. These booleans do not certify every sentence of model text.
- [Before](20261022-compact/before.json) and [after](20261022-compact/after.json)
  observations: raw bounded evidence from the shared collector.
- [Provenance](20261022-compact/provenance.json): Sydney time, base SHA,
  actual working-tree status and source hashes, including the new prompts/config.
- [Native regression JUnit](20261022-compact/tests.xml): 472 tests passed.
- [Docker regression JUnit](20261022-compact/docker-results/tests.xml): feature
  tests run with all AI flags false and all live opt-ins zero; 345 passed.
- [Hook check](20261022-compact/hook-check.console.txt): configured scans exercised
  with a temporary Git index, without staging files in the user's actual index.

Base commit is `4fa1ac8`; the new review configuration, prompts and tests are local
working-tree changes, not claimed as already covered by that published CI run.
New tests check mode discovery, source checks, disabled-mode no-network behaviour,
mandatory explicit workflow selection, and rejection of a different workflow/feature.
Fixtures and mocked tests are not live model or student participation evidence.

The secret hook automatically normalized path separators, added its standard
baseline-file filter and updated an existing fixture's line number/timestamp.
A normalized comparison against HEAD verified the same 27 existing digest/type/
verification entries: no finding was added or removed and no new waiver granted.
The first hook attempt updated that metadata; a subsequent unstaged-baseline
refusal is not called a passing commit. The selected check used an isolated index
containing that bookkeeping update. No actual commit was performed.

The shared grounding guard caught missing-agent/source-citation problems, but
did not catch the compact run's final semantic misattribution of the five-record
limit to the shared store. That model assertion is rejected in this evidence
annotation. It is not a new application defect or a student release decision.

## Reproduce the selected review

Keep Ollama and the matching host server available. Run from the repository root:

```bash
TZ=Australia/Sydney AI_MODE_ENABLED=true MULTI_AGENT_ENABLED=true \
MULTI_AGENT_SERVER_URL=http://127.0.0.1:5054 \
MULTI_AGENT_REVIEW_WORKFLOW_ID=ea8edb14-543a-4ec4-8666-86356b8e9e80 \
OLLAMA_MODEL=llama3.1:8b \
  .venv311/bin/python 'student-Ethan Ting/scripts/review_loyalty_multi_agent.py' \
  --output docs/evidence/release2-ethan-ting/step4-multi-agent/NEW-CAPTURE
```

Always use a new output directory; existing captures are not overwritten. The
default configured log references intentionally select retained Step 1 evidence.
If selecting a newly executed workflow, configure its matching project-local log
snapshots instead. Do not rewrite retained logs or use another feature's latest
workflow to manufacture a pass. An unavailable historical workflow is a limitation,
not permission to submit a new workflow or decision through this read-only tool.

## Remaining decisions

Structural completion does not guarantee model factual accuracy or clear the
shared Testing Review's security failures. The student's own release decision is
still **not recorded**. Cloud deployment validation, current CI after publication,
final report/diagrams and showcase participation remain separate work. Nothing
was committed, pushed or deployed during this step.
