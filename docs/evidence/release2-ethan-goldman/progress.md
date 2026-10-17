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

## Current verification and remaining work

- Support: 206 passing tests, 10 opt-in skips. Shared/cloud: 302 passing tests.
  [Native endpoint and suite artifacts](ci/s03a-actions-artifact.json) identify
  their actual source and run. CI fixtures are separate from real local AI captures.
- Security: [44 whole-repository Ruff findings](security/s03a-all-ruff.json) and
  four existing ChromaDB exceptions remain disclosed in the [security report](security/README.md).
- Both ticket #2013 model workflows still require genuine human decisions/reasons;
  see the [local report](local/README.md). No ticket action or approval is invented.
- The recovered AWS app is an older manual release. The CPU probe repair is tested
  but undeployed; main Actions deployment, public CRUD/disabled-AI/persistence and
  representative-load stability remain required. GitHub OIDC access is SCP-blocked.
- [PR #16](https://github.com/egoldman2/ASD/pull/16) remains draft and unmerged.
  Merge and paid AWS capability changes need separate authorization.
- Other feature owners supply their integrations and evidence. Final three review
  outputs, human release decision, official group/workflow allocation, group PDF,
  video, attendance and resource-retention decision remain outstanding.

Next: record the real Support decisions; resolve deployment access and integration,
then capture final deployment/review evidence and complete the group submission.
