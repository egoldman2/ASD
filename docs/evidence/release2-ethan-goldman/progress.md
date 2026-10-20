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

## Current verification and remaining work

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

Next: retain this required native evidence checkpoint, then resume S16 only when
supported AWS deployment-role access exists under the owner's capability decision.
Resolve remaining source-owner security findings and rerun affected reviews before
release sign-off. Report/video assembly is deferred at Ethan's request.
