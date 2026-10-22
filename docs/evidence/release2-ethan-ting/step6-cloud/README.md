# Ethan Ting: completed technical cloud evidence

22 October 2026, Sydney time. Selected final source is
`d297a42f144cd645f38ca294a1ae42c639ff58be`, deployed by
[AWS Cloud Deployment run 39736987978](https://github.com/egoldman2/ASD/actions/runs/39736987978).
This step retrieves existing deployment records and measures server health. It
does not deploy, install software, alter infrastructure, or change customer data.

## Result

All **six technical checks pass** for this release:

| Check | Retained result |
|---|---|
| SSM deployment acceptance | Successful deployment and accepted release |
| Cloud Actions jobs | Completed successfully for the selected SHA |
| Student workflow gate | All five same-SHA student workflows passed |
| Public cloud smoke | 67 recorded checks passed, expected core CRUD and disabled-integration checks present, cleanup passed |
| Runtime baseline | All four AI flags false; captured service/port baseline passed |
| Health observation | 120 seconds, 14 running containers, no new OOM kills or unexpected restarts; EC2 system/instance/EBS checks passed |

The overall shared review remains **incomplete only because no human release
decision has been supplied**. Technical success is not approval. The student's
customer-browser sign-in was pending at capture time and is now completed in
[Step 7](../step7-customer-cloud/README.md). The earlier shared
Testing Review's group security findings are not cleared by these cloud results.

## What happened

1. AWS access was available through the user's existing Chrome session, despite
   no local AWS CLI credentials. One read-only SSM command retrieved the missing
   native records for the previously reviewed `7218c43` release and observed it
   from approximately **5:58:21 pm to 6:00:21 pm AEDT**. Its evidence is retained
   in [main-7218c43](main-7218c43/).
2. The user published `d297a42` during this task. Its automatic AWS workflow
   subsequently succeeded. The earlier health window was **not** reassigned to
   that new SHA. New same-source Actions archives were downloaded and verified in
   [deployment-input-d297a42](deployment-input-d297a42/).
3. A second read-only SSM command,
   `f84ced80-ba29-4553-8efa-10695beb142d`, retrieved this release's accepted files
   and observed its running containers from **6:10:20 pm to 6:12:20 pm AEDT**.
   It made only public-home GET requests, not new CRUD requests. The 67 cloud
   checks come from the deployment's original smoke run, not a rerun here.
4. Both public-smoke and runtime bytes match the SHA-256 references exported by
   the accepted deployment. The full host result has additional provenance fields
   omitted by `cloud/deploy.py`'s safe projection, so it has different bytes; all
   fields exported in the accepted Actions projection agree. This is not described
   as equality between the full and projected file hashes.
5. The existing shared Cloud Deployment Review ran locally using Ollama
   `llama3.1:8b`, retaining Plan → Act → Observe → Adapt and machine validation.
   It returned exit code **1** because human approval is absent, not because the
   six technical checks failed.

Two SSM diagnostic execution records were created. No EC2 restart, deployment,
container restart, customer mutation, account/password change, secret retrieval,
new permission, resource provisioning, Git commit or push was performed by this
step. The user's intervening publication is distinguished from this automation.

## Final evidence

- [Current manifest](main-d297a42/cloud-manifest.json) references this release's
  Actions/deployment/gate records, retrieved files and new health observation.
- [Native public smoke](main-d297a42/public-smoke.json) and
  [native runtime](main-d297a42/runtime.json): exact retrieved bytes.
- [Host observation](main-d297a42/host-observation.json): three timestamped samples
  with selected container fields, OOM counter, memory/disk/load observations and
  public-home GET status. Unrelated environment values are not exported.
- [Health summary](main-d297a42/health.json),
  [EC2 console text](main-d297a42/ec2-status.dom.txt) and
  [visible passed checks](main-d297a42/ec2-status-checks.png).
- [Original SSM output](main-d297a42/ssm-output.dom.txt) and
  [successful command screenshot](main-d297a42/ssm-command-success.png).
- [Verification](main-d297a42/retrieval-verification.json),
  [executed observer](main-d297a42/executed-observer.py),
  [exact command](main-d297a42/executed-command.txt) and
  [assembler snapshot](main-d297a42/executed-assembler.py) retain source provenance.
- [Collected technical validation](main-d297a42/pre-review-validation.json).
- [Final shared review](../../agentic/shared-asd-group-services-cloud-deployment-20261022-181356-625715.md),
  [review validation](../../agentic/shared-asd-group-services-cloud-deployment-20261022-181356-625715.validation.json)
  and [console](main-d297a42/review-console.txt).
- [Local regression JUnit](main-d297a42/tests.xml): 379 tests passed across Ethan
  Ting's feature suite and the shared Cloud Deployment Review tests, with AI flags
  disabled. New host-evidence tests also passed independently without live AWS.
- [Docker regression JUnit](main-d297a42/docker-results/tests.xml): 373 feature
  tests passed in the rebuilt test image, with all four AI flags disabled and
  live opt-ins zero. These local checks are not claimed as published CI results
  for the newly added observer, assembler or tests.

## Model limitations and pending decisions

The first `7218c43` model review incorrectly reversed the rule that manual
deployment cannot establish the integrated release. The `d297a42` initial review
misread empty `missing_crud` lists as missing features. Those claims are rejected,
not application defects. The model reviewer did not reliably detect these errors.
The original outputs remain available, while the deterministic final summary
preserves the actual six passing technical checks and missing human decision.

The observation used a light public-home workload, not a production load test.
It proves only the recorded two-minute window. EC2 console checks are a separate
point-in-time observation, not a continuous EC2-status API series. The shared
validator still checks captures offline and does not independently authenticate
remote records; saved UI/source/hash evidence does not turn that limitation off.
Native AWS timestamps retain their original offsets, while this explanation and
new host timestamps use Sydney time.

The next human step is to review these findings together with unresolved group
security findings and the separately recorded customer-browser check, then record a reasoned
accept/conditional-accept/reject decision for an explicit release. No decision
was fabricated. Future deployments need their own observation; this evidence
must not silently certify a later SHA.

## Reproduce the local review

Keep Ollama available and run from the repository root:

```bash
TZ=Australia/Sydney AI_MODE_ENABLED=true OLLAMA_MODEL=llama3.1:8b \
RELEASE_REVIEW_SOURCE_SHA=d297a42f144cd645f38ca294a1ae42c639ff58be \
CLOUD_DEPLOYMENT_REVIEW_MANIFEST=docs/evidence/release2-ethan-ting/step6-cloud/main-d297a42/cloud-manifest.json \
  .venv311/bin/python -u ai-services/agentic_loop.py \
  --feature shared --mode cloud-deployment
```

The new host observer and local assembler accept an explicit source, release
directory, prior capture and actual SSM command ID. Retain a new output directory
and exact executed script/command for any new observation. They reject changed
release identity, native-byte hash mismatches, malformed/oversized exports,
incomparable reboot/counter observations and replacement of existing evidence.
Do not run the observer's Linux/Docker host checks on the laptop or claim that
mocked tests are live AWS evidence. The public Git SHA scanner annotations are
specific public identifiers, not acceptance of credentials.
