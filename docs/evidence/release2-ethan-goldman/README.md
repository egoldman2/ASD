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
- [Integrated main tests, five-workflow gate and actual deployment blocker](ci/main-cc6f1e4/verification.json).
- [AWS recovery and backups](../release2-aws/recovery-20261017/README.md),
  [CPU diagnosis and tested repair](../release2-aws/cpu-probes-20261017/README.md).
- [Original failed baseline test summary](ci/s00-tests.json).
  Planning documents and duplicate intermediate scans are excluded.

PR #16 is merged and all five main workflows pass at `cc6f1e4`. Deployment stopped
at the missing role preflight; renewed AWS access confirms the managed OIDC deny.
Ethan retained the Free plan. Owner evidence, Actions deployment, final group
reviews/release decision and the group PDF/video remain pending.
Cloud recovery is not final deployment acceptance. Native captures retain their
actual historical SHAs after branch-history cleanup. No bonus work is claimed.
