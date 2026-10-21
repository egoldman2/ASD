# AWS port evidence

Current release, 21 October 2026: main `5ac7535` passes automatic native Actions
deployment, public CRUD/disabled-AI checks, redeployment persistence and the Chrome
redirect repair check. [Final native evidence](final-5ac7535/verification.json)
and [30-minute infrastructure observation](stability-20261021/verification.json)
supersede the historical availability/deployment status below. Ethan requested
keeping the demo running for marking. Final security/release conditions remain
in the [ledger](../release2-ethan-goldman/progress.md).

Validation date: 9 October 2026. Scope: cloud baseline and compatibility changes, not the whole Release 2 submission.

| Check | Result |
| --- | --- |
| Shared, accounts and support regression suites | 406 passed, 8 optional live tests skipped |
| Catalogue regression suite | 79 passed |
| Inventory regression suite | 24 passed |
| Orders regression suite | 9 passed |
| New cloud and inventory authorization checks | 11 passed |
| Legacy inventory MCP/RAG and shared AI-service suites | 148 passed, 2 optional live tests skipped |
| Integrated local cloud authentication, CRUD and disabled AI checks | 44 passed |
| EC2 deployment and host-side integrated checks | Passed on initial release and subsequent update |
| Public CloudFront HTTPS integrated checks | 44 passed |
| Local gateway request without origin verification header | Rejected with HTTP 403 |
| cfn-lint 1.40.0 | Passed |
| cfn-guard 3.2.1 targeted repository rules | Passed |
| AWS template API validation | Passed |

`local-smoke.json` and `public-smoke.json` record sanitized HTTP checks. `deployment.json` identifies the accepted release, source checksum and SSM command. The public app is [the Release 2 cloud demo](https://dww8d9hiqp0ce.cloudfront.net). The initial `t3.medium` provision was rejected by the Free-plan eligibility policy; it did not deploy application data. The approved cleanup removed the failed stack and its unused retained volume, bucket and seed-password secret. The template now uses eligible `t3.small` and checks eligibility before provisioning.

Chrome verified that the homepage and catalogue load and browser links point at the cloud origin. A second accepted release exercised deployment with the existing databases in place. In-place updates briefly interrupt service on this single-host baseline. See [cost comparison](cost-estimate.md) for running, stopping and cleanup estimates.

After final verification, EC2 was confirmed **stopped** at the user's request. `environment-state.json` records that state. The public site is offline until the host starts again; data and setup remain. A stop/start recovery cycle and load testing have not yet been verified. Temporary local `asd-cloud` test containers were removed; other local Docker projects were preserved.

GitHub workflow execution and OIDC role setup are not yet verified. `CreateOpenIDConnectProvider`, `GetOpenIDConnectProvider` and `ListOpenIDConnectProviders` were explicitly denied by the project's managed service control policy. No access keys or alternative identity were introduced. See [deployment design and runbook](../../architecture/aws-deployment.md).

## Group handover and first GitHub execution — 12 October

The AWS source, infrastructure, workflow, evidence and [group explanation guide](../../architecture/aws-group-handover.md) were published directly to `main`. AWS Settings confirmed that project invitations were sent to all four teammates; acceptance was pending. Invitation addresses and credential values are intentionally omitted from this public evidence.

The first cloud workflow run split the two feature paths containing spaces before pytest ran. The corrected workflow passes JSON arrays of exact paths. [The corrected run](https://github.com/egoldman2/ASD/actions/runs/38200811684) passed **all six validation jobs and the cloud image build**. Its deployment job failed at **Require configured deployment role**, because `AWS_DEPLOY_ROLE_ARN` is not configured. This verifies GitHub validation/build execution, not a GitHub-to-AWS deployment. Manual AWS deployments remain the previously verified path.

Read-only checks on 12 October found the existing host running, the project still on its active Free plan and US$97.49 in reported remaining credits. The handover did not start, stop, redeploy or upgrade AWS infrastructure.
