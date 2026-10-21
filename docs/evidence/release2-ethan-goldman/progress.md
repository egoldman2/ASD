# Release 2 contribution and verification ledger

Owner: Ethan Goldman. This ledger records completed implementation and actual
historical checks. The branch history was subsequently cleaned at Ethan's request;
original SHAs below remain the source identities of their captured Actions runs
and native artifacts. They are not claims that rewritten commits ran those jobs.
Fresh CI for the cleaned branch is linked from PR #16 and the session handoff.

Repeated session handoffs, copied PR bodies and intermediate CI payloads have been
removed. Code, tests, required report drafts and native local/cloud captures remain.

| Stage | Original source | Result | Evidence / actual Actions runs |
| --- | --- | --- | --- |
| S00 | `f3c1675` | Recorded failure: five cookie tests, 95 Ruff findings | [baseline](ci/s00-tests.json) [CI 1](https://github.com/egoldman2/ASD/actions/runs/38967670747) |
| S01 | `c9a05ba` | Automated checks and branch CI passed |  [CI 1](https://github.com/egoldman2/ASD/actions/runs/38968081770) |
| S05 | `2d6b5a3` | Automated checks and branch CI passed |  [CI 1](https://github.com/egoldman2/ASD/actions/runs/38968890480) |
| S06 | `49319bd` | Initial CI failed; repaired by S06a |  [CI 1](https://github.com/egoldman2/ASD/actions/runs/38969614910) |
| S06a | `3f325f7` | Automated checks and branch CI passed |  [CI 1](https://github.com/egoldman2/ASD/actions/runs/38970325636) |
| S07 | `a0d40ca` | Automated checks and branch CI passed |  [CI 1](https://github.com/egoldman2/ASD/actions/runs/38971168500) |
| S08 | `1ff2c50` | Automated checks and branch CI passed |  [CI 1](https://github.com/egoldman2/ASD/actions/runs/38973285184) |
| S09 | `50fe5ad` | Automated checks and branch CI passed | [endpoint mapping](ci/s09-endpoint-mapping.json) [CI 1](https://github.com/egoldman2/ASD/actions/runs/38974830702) |
| S11 | `f9dc0c9` | Automated checks and branch CI passed |  [CI 1](https://github.com/egoldman2/ASD/actions/runs/38976066482) |
| S12a | `de9aba3` | Automated checks and branch CI passed |  [CI 1](https://github.com/egoldman2/ASD/actions/runs/38977098474) |
| S12b | `fc77190` | Automated checks and branch CI passed |  [CI 1](https://github.com/egoldman2/ASD/actions/runs/38977973250) |
| S13a | `28a2934` | Automated checks and branch CI passed |  [CI 1](https://github.com/egoldman2/ASD/actions/runs/38978919204) |
| S13b | `0b56ed2` | Automated checks and branch CI passed |  [CI 1](https://github.com/egoldman2/ASD/actions/runs/38979885152) |
| S14a | `365b335` | Automated checks and branch CI passed | [Linux smoke](cloud/s14a-smoke-report.json) [CI 1](https://github.com/egoldman2/ASD/actions/runs/38982817148) |
| S14b | `d42a22a` | Automated checks and branch CI passed | [provenance](cloud/s14b-verification.json) [CI 1](https://github.com/egoldman2/ASD/actions/runs/38983764411) |
| S10a | `9c70b04` | Automated checks and branch CI passed |  [CI 1](https://github.com/egoldman2/ASD/actions/runs/38984491762) |
| S10b | `37e859a` | Automated checks and branch CI passed |  [CI 1](https://github.com/egoldman2/ASD/actions/runs/38985410683), [CI 2](https://github.com/egoldman2/ASD/actions/runs/38985414204) |
| S10c | `d8724d2` | Automated checks and branch CI passed |  [CI 1](https://github.com/egoldman2/ASD/actions/runs/38986995991), [CI 2](https://github.com/egoldman2/ASD/actions/runs/38986999923) |
| S15a | `1b2b032` | Real local captures; both human decisions pending | [local captures](local/README.md) [CI 1](https://github.com/egoldman2/ASD/actions/runs/38989318132), [CI 2](https://github.com/egoldman2/ASD/actions/runs/38989321762) |
| S18a | `27f2d40` | Individual/shared report drafts; submission pending | [report drafts](../../reports/release2-ethan-goldman-contribution.md) [CI 1](https://github.com/egoldman2/ASD/actions/runs/38989771233), [CI 2](https://github.com/egoldman2/ASD/actions/runs/38989775933) |
| S00b | `bec5890` | Automated checks and branch CI passed | [security](security/README.md) [CI 1](https://github.com/egoldman2/ASD/actions/runs/38990815366), [CI 2](https://github.com/egoldman2/ASD/actions/runs/38990819236), [CI 3](https://github.com/egoldman2/ASD/actions/runs/38991919913), [CI 4](https://github.com/egoldman2/ASD/actions/runs/38991922657) |
| S04a | `675e8d9` | Trust/template/environment checks pass; AWS access blocked | [OIDC checks](ci/s04a-verification.json) [CI 1](https://github.com/egoldman2/ASD/actions/runs/38993762504), [CI 2](https://github.com/egoldman2/ASD/actions/runs/38993765920) |
| S00c | `5df4fcc` | Automated checks and branch CI passed | [SQL review](security/s00c-verification.json) [CI 1](https://github.com/egoldman2/ASD/actions/runs/38994640055), [CI 2](https://github.com/egoldman2/ASD/actions/runs/38994644387) |
| S00d | `8702c4b` | Automated checks and branch CI passed | [current findings](security/s03a-all-ruff.json) [CI 1](https://github.com/egoldman2/ASD/actions/runs/38995127754), [CI 2](https://github.com/egoldman2/ASD/actions/runs/38995130793) |
| S02a | `7b64a0c` | Recovered host and verified consistent database backups | [recovery](../release2-aws/recovery-20261017/README.md) [CI 1](https://github.com/egoldman2/ASD/actions/runs/39032815225), [CI 2](https://github.com/egoldman2/ASD/actions/runs/39032819040) |
| S03a | `78e21b7` | 15 health tests and 302 shared/cloud tests pass; undeployed | [probe repair](../release2-aws/cpu-probes-20261017/README.md) [CI 1](https://github.com/egoldman2/ASD/actions/runs/39033738565), [CI 2](https://github.com/egoldman2/ASD/actions/runs/39033742420) |
| S15b | Evidence `5796521`; demo `37e859a`; review `d389a49` | Both genuine Accept decisions saved; restart/API/audit checks pass; Support 206 passed/10 opt-in skips | [human review](local/human-review-20261018/README.md); [push CI](https://github.com/egoldman2/ASD/actions/runs/39115466578), [cloud PR CI](https://github.com/egoldman2/ASD/actions/runs/39115468955) |
| S16a | Authorized PR #16 merge `cc6f1e4` | All five main workflows, seven cloud suites, image build and exact-main gate pass; deploy fails at missing role preflight | [native endpoint/context/gate and verification](ci/main-cc6f1e4/verification.json); [Support CI](https://github.com/egoldman2/ASD/actions/runs/39116067484), [actual cloud attempt](https://github.com/egoldman2/ASD/actions/runs/39116067546) |
| S16b | Authorized PR #17 merge `857866c` | All five main workflows, seven cloud suites, build and gate pass; deployment again stops before credentials at the missing role | [Support CI](https://github.com/egoldman2/ASD/actions/runs/39118421094), [cloud attempt](https://github.com/egoldman2/ASD/actions/runs/39118421096) |
| S13c | `2bc6ae6` | Cloud Review retains an actual failed preflight without an accepted deployment artifact; 104 focused and 311 shared/cloud tests pass; all six CI runs pass | [regressions](../../../shared/tests/test_cloud_report_validation.py); [push CI](https://github.com/egoldman2/ASD/actions/runs/39119587355), [cloud PR CI](https://github.com/egoldman2/ASD/actions/runs/39119900573) |
| S09b | `5c2bb80` | Two existing endpoint tests per feature selected from task allocations under Ethan's instruction; all ten endpoint cases, eight capture tests and 319 shared/cloud tests pass locally; all seven exact-head CI runs pass | [mapping](../../reports/release2-report-evidence-contract.md); [Support push](https://github.com/egoldman2/ASD/actions/runs/39120828462), [cloud PR](https://github.com/egoldman2/ASD/actions/runs/39120832173); all five PR archives downloaded and digest-verified |
| S16c | Authorized PR #18 merge `137c298` | All five main workflows, seven cloud suites, build and exact-main gate pass; all ten named endpoint cases pass; deployment fails at missing-role preflight before credentials or publish/SSM | [native five-owner verification](ci/main-137c298/verification.json), [gate and failure](../release2-aws/main-137c298/verification.json); [Support CI](https://github.com/egoldman2/ASD/actions/runs/39122068977), [cloud attempt](https://github.com/egoldman2/ASD/actions/runs/39122068227) |
| S17a | Evidence `cc84d7c`; review source `137c298` | Real local Qwen 3B Testing/Cloud reviews save linked validation/console logs; both retain deterministic failure and fallback; artifact hashes/links and separate evidence scan verified; both exact-head CI runs pass | [Testing Review](../agentic/shared-asd-group-services-testing-20261018-221717-719042.md), [Cloud Review](../agentic/shared-asd-group-services-cloud-deployment-20261018-222109-735344.md); [testing inputs](../release2-testing-manifest.json), [cloud inputs](../release2-cloud-deployment-manifest.json); [push CI](https://github.com/egoldman2/ASD/actions/runs/39123077665), [PR CI](https://github.com/egoldman2/ASD/actions/runs/39123112738) |
| S15c | Collection `cc84d7c`; retained S15 runtime | Ethan authorized deletion of disposable #2015 through the staff UI; queue search returns zero, API returns 404, #2013 snapshot hash and all 13 pre-existing ticket IDs remain unchanged | [native screenshots and verification](local/ui-delete-20261018/verification.json); no rebuild, new model call or API DELETE |
| S00e | Source parent `d36fd7a`; fix follows in Git history | RAG defaults to loopback; explicit host override retained. Regression reproduced one default-bind failure before repair; MCP/RAG 141 passed/2 opt-in skips, Support 206 passed/10 opt-in skips and shared/cloud 319 passed. Docker Support reaches the existing loopback RAG health endpoint (200). Changed-source Ruff passes; global scan retains 42 findings | [entrypoint regression](../../../ai-services/rag_server/tests/test_server_protocol.py), [configuration and deployment guidance](../../../ai-services/rag_server/README.md); exact pushed-SHA CI results recorded in the fix PR |

## Integration security follow-up — 20 October 2026

S00f removes the inventory email-based administrator override introduced on main
in `cb1908f`. On source `d046a4f`, customer sessions using `admin@asd.com` and its
case/whitespace variant reproduced HTTP 200 instead of 403 (two failed, two
passed baseline cases). The repair restores the authentication service's role
as the authority. All six role/email cases pass, with rejected customers making
no database call and genuine administrators retaining access. Inventory's 46
checks and all 319 shared/cloud checks pass locally. Support retains 206 passes
and 10 opt-in skips; changed-source Ruff and all three security hooks pass.
The [regression test](../../../student-Ryan_Nolan/tests/test_authentication.py)
and fix are retained in this checkpoint. Its commit and exact-SHA Actions results
are recorded in the fix PR; no separate bookkeeping commit is required.

## Historical operational checkpoints — 18–21 October 2026

- S16d: public browser ticket #2019 survives the automatic `2e72743` deployment;
  manual reply/update/reload and explicitly approved deletion succeed. Deletion
  exposes a real 404 redirect to `/staff.html`. The one-line repair uses the
  existing `SUPPORT_PUBLIC_URL`; four regression cases replace three reproduced
  failures and one pass. Support: 210 passed/10 opt-in skips; shared/cloud: 373
  passed. [Native baseline and repair checks](../release2-aws/public-delete-redirect-20261021/baseline.json).
  Repair commit/CI follow in its PR; hosted redirect verification remains pending.

- S04e `9d19caa`: all three exact-head checks pass, including [cloud CI](https://github.com/egoldman2/ASD/actions/runs/39544531203).
  The scoped relay update is UPDATE_COMPLETE. Approved PR #24 integrates as
  `2e72743`; the genuine GitHub PUSH relay, API-started child and [native main
  Actions deployment](https://github.com/egoldman2/ASD/actions/runs/39545291195)
  succeed after all five student workflows. Both 64-check smoke captures pass,
  all four AI flags are false, and four-database persistence is verified.
  [Native baseline](../release2-aws/codebuild-relay-20261021.json); [subsequent native results](https://github.com/egoldman2/ASD/pull/24).
  Thirty-minute load observation is running; final release acceptance is pending.

- S04d: the separate `asd-release2-actions` stack is CREATE_COMPLETE with only
  a main-push CodeBuild project, scoped service role and seven-day logs. All three
  S04c `421c71a` [exact-head checks](https://github.com/egoldman2/ASD/actions/runs/39417240957)
  pass. Workflow wiring preserves all existing gates and native Actions artifacts.
  The real registration preflight exposed the vendor config's UTF-8 BOM; the
  reader repair has a reproducing lifecycle test. The repeat native preflight
  succeeds and removes all three disposable registrations without starting a
  listener. Shared/cloud: 363 passed; lint, three guard rules, AWS validation,
  IAM validation and change-set preflight pass. [Native evidence](../release2-aws/codebuild-deployment-20261020.json).
  Application deployment is pending PR #23 integration; the AWS plan is unchanged.

- S04c: main-source bootstrap admits only the exact native cloud deploy job after
  its nine prerequisites and five student workflows pass. A private pre-job hook
  checks the native run/attempt/job/runner assignment and current main before any
  workflow steps. The pinned, digest-verified runner is ephemeral; credentials
  and registration are cleaned up after success or failure. Shared/cloud: 361
  passed, including 37 runner cases; shell syntax and Ruff security checks pass.
  This checkpoint supplies the bootstrap; infrastructure/workflow wiring follows.
  S01b `1d21590`: all three [exact-head checks](https://github.com/egoldman2/ASD/actions/runs/39414922522)
  pass. Checkpoint SHA/CI are recorded in PR #23 to avoid bookkeeping-only commits.

- S01b: [S04b cloud PR CI](https://github.com/egoldman2/ASD/actions/runs/39412209238)
  exposed a random workflow UUID containing `0412`, incorrectly matched as phone
  leakage. A deterministic colliding-ID fixture reproduces it. API/review/UI
  checks now distinguish metadata from customer content, retaining fragment
  checks on model input/review reasons and full/normalized phone checks on all
  output. The UI also proves the redaction marker is rendered. Support: 206
  passed, 10 opt-in skips; route suite: 19 passed. No production code changed.

- S04b, 20 October: `asd-release2-github` is AVAILABLE. The isolated CodeBuild
  source probe downloads and verifies main `d4660ff`; native build
  `asd-release2-source-check-source:a25c9bf0-e7ac-42c1-8550-bf23b22332d2`
  succeeds. Five focused tests, 324 shared/cloud tests, cfn-lint, three AWS guard
  rules, IAM policy validation and change-set preflight pass. The source-only
  role has no release permissions or webhook. [Native verification](../release2-aws/codebuild-source-20261020.json)
  and [reusable template](../../../cloud/codebuild-source.yml) are retained;
  exact commit/Actions results follow in the checkpoint PR. Deployment integration
  remains required; the AWS plan is unchanged.

- Main `137c298`: all five student workflows and all ten named endpoint cases pass
  without failures/errors/skips. Seven cloud suites, image build and exact-main
  gate pass. The actual deployment stops at the missing role before credentials;
  [native main captures](ci/main-137c298/verification.json) and
  [actual cloud failure](../release2-aws/main-137c298/verification.json) retain
  run/archive identities. Four byte-identical native dependency lists are stored
  once, with each original archive-to-member mapping retained.
- Earlier main `cc6f1e4`: Support 206 passed/10 opt-in skips; shared/cloud 302 passed;
  MCP/RAG 138 passed/2 opt-in skips; Multi-Agent 82 passed. The two required
  endpoint cases pass without skips. [Native main evidence](ci/main-cc6f1e4/verification.json)
  identifies actual runs and verified archive hashes. CI fixtures are separate
  from real local model captures.
- Security: [44 whole-repository Ruff findings](security/s03a-all-ruff.json) and
  four existing ChromaDB exceptions remain disclosed in the [security report](security/README.md).
  Fresh source-`137c298` scans retain [75 unfiltered detector candidates](security/s17-detect-secrets.json)
  (48 reported on baseline metadata itself) and the [four native dependency findings](security/s17-dependency-findings.json).
  Candidates are not a count of confirmed leaked secrets; raw findings are not
  removed or relabelled as passing. All five student endpoint/Actions captures
  pass the actual Testing Review validator, while security keeps its result failed.
  A separate scan of 33 new evidence files found 201 known provenance/detector
  digest literals and zero unclassified candidates; no new ignore was added.
- Both ticket #2013 workflows now record Ethan's Accept / `nothing needed.`;
  [native evidence and completed review](local/human-review-20261018/README.md)
  verify unchanged ticket/model data and post-decision restart persistence.
  Review runtime validation passes; model grounding failed and used the existing
  deterministic fallback. This is separate from final group release approval.
- The recovered AWS app is an older manual release. The CPU probe repair is tested
  but undeployed; main Actions deployment, public CRUD/disabled-AI/persistence and
  representative-load stability remain required. GitHub OIDC access is SCP-blocked.
  The [18 October read-only follow-up](../release2-aws/cpu-probes-20261017/followup-20261018.json)
  records nearly empty CPU credits, 76–80% steal samples and no container restarts
  at capture. Its first command exited 1 on an empty journal search; a successful
  bounded follow-up does not establish historical OOM cause or final stability.
- Ethan authorized [PR #16](https://github.com/egoldman2/ASD/pull/16)'s merge on
  18 October. Renewed AWS access confirms FREE/active, healthy EC2/SSM, an explicit
  OIDC SCP denial and no GitHub-trusting role. Ethan chose to keep the current
  plan; Paid/Advanced changes remain unauthorized. Actions configured no AWS
  credentials and performed no publish/SSM deployment.
- Other feature owners supply their integrations and evidence. The actual Support
  Multi-Agent review and both shared report reviews are saved; their genuine
  limitations/failures remain. Human release decision, official numeric workflow allocation and
  resource-retention decision remain outstanding. On 18 October Ethan deferred
  report/video assembly; the local PDF draft is not part of this evidence commit.
- Canvas confirms Group 33. Release 2 displays 25 October, 23:59 with the profile
  timezone Sydney; its brief says AEST. The timezone wording still needs confirmation.

## Current release verification — 21 October 2026

- S03b: deployed `2e72743` completes 1,800 seconds, 15 cycles and 960 passing
  public checks. No new OOM events or unexpected restarts; minimum available
  memory 891,892 KiB. Actual seven-service health schedules and native metric
  captures are retained. [Observation](../release2-aws/stability-20261021/verification.json).
- S16d: repair `b640997` passes all three exact-head CI runs and security hooks;
  Support 210 passed/10 opt-in skips, shared/cloud 373 passed. Explicitly approved
  [PR #25](https://github.com/egoldman2/ASD/pull/25) merges as `5ac7535` after the
  observation. All five main workflows and ten endpoint cases pass;
  [native owner captures](ci/main-5ac7535/verification.json). The automatic relay,
  child runner and [main deployment](https://github.com/egoldman2/ASD/actions/runs/39548953172)
  succeed. Both 64-check smoke captures pass with all AI flags false. All baseline
  database keys and pre-existing Support rows survive; explicitly approved Chrome
  deletion of #2039 returns to `/support/staff.html`, zero matches/rows afterward.
  The final redirect-only revision also passes a three-minute/128-check health
  observation. [Native acceptance/persistence/browser evidence](../release2-aws/final-5ac7535/verification.json).
- S17b: three real Qwen 3B reviews of current source and actual captures are saved
  with matching console, input hashes and validation logs;
  [provenance](../agentic/release2-5ac7535-execution.json). Support's selected
  workflow/history/audit validation passes. Shared Testing validates all five
  owners but retains 39 Ruff findings and 78 detector candidates; four unique
  Chroma advisories retain existing exceptions. Cloud technical validation passes.
  Ethan explicitly approves [Conditional accept](../release2-aws/final-5ac7535/human-release.json)
  for `5ac7535`: keep the assessment demo available, retain the failed Testing
  Review and require source-owner security review/resolution before unconditional
  group sign-off. [Separate post-decision validation](../release2-aws/final-5ac7535/post-decision-validation.json)
  confirms the genuine decision and pending conditions; original model review
  inputs/outputs remain unchanged. Model grounding failures/fallback stay visible.
  No blanket security pass or production capacity claim is made.
- Ethan requested keeping the demo running for marking. Report/PDF/video work and
  bonuses remain deferred. Historical blocker statements above describe their
  dated checkpoints and do not describe current deployment availability.

PR #26 was explicitly approved and merged as `b46e719`; its
[main deployment](https://github.com/egoldman2/ASD/actions/runs/39552747817)
passed. Newer integrated main `358cc29` also passes all six workflows and its
[native deployment](https://github.com/egoldman2/ASD/actions/runs/39611233212)
records SSM `37f83a20-be7c-417d-8608-9dd66a039b55`, Success/accepted. The downloaded
archive digest matches Actions; this verifies that capture, not a fresh host read.

S14c (22 October): extend shared disabled-AI smoke and Cloud Review requirements
to the now-integrated Accounts/Loyalty, Inventory and Orders/Returns Multi-Agent
routes, using only temporary CRUD fixtures. Regression baseline: 4 failed/60
passed; repaired focused suite: 65 passed. Shared/cloud: 377 passed; Support:
210 passed/10 opt-in skips; MCP/RAG: 141 passed/2 opt-in skips; agents: 82 passed.
Tests are in `cloud/tests/test_smoke.py` and
`shared/tests/test_cloud_report_validation.py`; this checkpoint's PR records its
commit, hooks and exact-SHA Actions links without a follow-up bookkeeping commit.
Explicitly approved [PR #29](https://github.com/egoldman2/ASD/pull/29), authored as
`32a97b0`, merged as `c081853`. All three authoring-SHA CI runs passed; all seven
main/synchronized-branch runs passed. The main gate verifies all five owners.
Live acceptance now covers all five Multi-Agent routes with all AI flags false.

## Current release verification — 22 October 2026

- S16e: exact main `c081853` automatically deploys through the existing push relay,
  child runner and [Actions deployment](https://github.com/egoldman2/ASD/actions/runs/39680184997).
  All ten deployment jobs succeed; SSM acceptance is Success/0. Native archives
  retain their verified Actions digests. Both local and public smoke pass 67 checks;
  all 14 containers are healthy. Four-database integrity, foreign keys, baseline
  keys and pre-existing Support rows survive. The approved-deleted #2039 remains
  absent. Its earlier Chrome deletion proof is carried forward only because
  Support and proxy source bytes are unchanged; no fresh browser run is claimed.
  The three-minute observation passes 134 public checks with no new OOM/restarts
  and minimum available memory 906,404 KiB. One sequential demo client does not
  establish production capacity. [Native verification](../release2-aws/final-c081853/verification.json).
- All five main workflows and ten allocated endpoint cases pass:
  [Catalogue](https://github.com/egoldman2/ASD/actions/runs/39680185023),
  [Inventory](https://github.com/egoldman2/ASD/actions/runs/39680185076),
  [Accounts/Loyalty](https://github.com/egoldman2/ASD/actions/runs/39680184988),
  [Orders/Returns](https://github.com/egoldman2/ASD/actions/runs/39680185027),
  [Support main](https://github.com/egoldman2/ASD/actions/runs/39680184983) and
  [synchronized Support branch](https://github.com/egoldman2/ASD/actions/runs/39680214295).
  [Native ZIPs, JUnit, contexts and hashes](ci/main-c081853/verification.json).
- S17c: three real Qwen2.5:3b reviews use current source and actual captures;
  [execution provenance](../agentic/release2-c081853-execution.json) includes
  matching console and validation hashes. Support history/audit checks pass.
  Shared Testing passes all five endpoint captures but retains the raw failed
  security review: 28 Ruff findings, 75 detector candidates and four existing
  Chroma exceptions. Model grounding/fallback limitations remain disclosed.
  Cloud technical validation passes. Ethan explicitly approves
  [Conditional accept for c081853](../release2-aws/final-c081853/human-release.json);
  [post-decision validation](../release2-aws/final-c081853/post-decision-validation.json)
  records the actual decision and pending source-owner security conditions.
  Original pre-decision model inputs and earlier decisions remain unchanged.
- Keep the Free-plan demo running for marking. Cloud AI remains disabled;
  report/PDF/video and bonuses remain deferred. The final evidence-only commit
  and exact-head CI are recorded in its PR metadata to avoid bookkeeping commits.
