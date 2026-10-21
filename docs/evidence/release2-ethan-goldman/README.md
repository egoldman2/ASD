# Release 2 — Ethan Goldman evidence

Required report material and genuine testing/deployment captures for Customer
Support, shared AWS deployment and the two shared report-review modes.

- [Individual report](../../reports/release2-ethan-goldman-contribution.md) and
  [shared cloud/testing report](../../reports/release2-shared-cloud-and-testing.md).
- [Contribution, original source SHAs and CI links](progress.md).
- [Security findings, exceptions and commit-time scans](security/README.md).
- [Two required endpoints](ci/s09-endpoint-mapping.json), [native JUnit](ci/s03a-actions-endpoint-functions.xml),
  [actual CI context](ci/s03a-actions-test-context.json) and [artifact provenance](ci/s03a-actions-artifact.json).
- [Real local UI/terminal/model/history captures](local/README.md).
- [Both genuine human decisions, restart persistence and completed Support review](local/human-review-20261018/README.md).
- [Final five-owner endpoint/Actions captures](ci/main-c081853/verification.json)
  and [current deployment, persistence and browser-proof continuity](../release2-aws/final-c081853/verification.json).
- [AWS recovery and backups](../release2-aws/recovery-20261017/README.md),
  [CPU diagnosis and tested repair](../release2-aws/cpu-probes-20261017/README.md).
- [Original failed baseline test summary](ci/s00-tests.json).
  Planning documents and duplicate intermediate scans are excluded.

Approved PR #29 is merged as `c081853` and automatically deployed. All five
student workflows and ten endpoint cases pass. The three final real model
reviews and matching console/validation records are indexed in
[review provenance](../agentic/release2-c081853-execution.json). Raw security
findings remain disclosed; release conditions are recorded in the ledger.
Ethan retained the Free plan and requested keeping the demo running for marking.
Report/video work is deferred. Historical captures retain their actual source
SHAs after branch cleanup; no bonus inference deployment is claimed.
