# Ethan Ting: Cloud Deployment Review

22 October 2026, Sydney time. This is the shared Release 2 **Cloud Deployment
Report Review**, not another deployment or simply a browser check. The existing
shared loop ran Plan → Act → Observe → Adapt against retained deployment
evidence, using local Ollama with `llama3.1:8b`.

## Selected release and result

Selected source: `7218c437182feb42c202abf15232b535675576e2`.
The [actual main-push deployment run](https://github.com/egoldman2/ASD/actions/runs/39701565735)
completed successfully, including the `deploy` job. All five same-source student
workflows passed the gate. The native report records successful SSM execution
and accepted release `7218c437182feb42c202abf15232b535675576e2-1`.

The **review result is incomplete**, not a deployment failure or release approval.
Three checks pass: SSM acceptance, cloud Actions jobs, and the five-student gate.
Detailed public-smoke, runtime and health capture contents are not supplied for
this release, and no human release decision was recorded. The manual customer
sign-in check also remains pending. Older cloud captures and another person's
release decisions were not relabelled to fill these gaps.

## Retained evidence

- [Manifest](main-7218c43/cloud-manifest.json) selects this SHA without changing
  the team's default manifest or historical evidence.
- [Actions run](main-7218c43/actions-run.json), [jobs](main-7218c43/actions-jobs.json)
  and [artifact metadata](main-7218c43/artifacts.json) are real GitHub API responses.
- [Archive verification](main-7218c43/archive-verification.json) checks both ZIPs
  against GitHub's SHA-256 digests before bounded, allowlisted extraction.
- [Native deployment report](main-7218c43/native/deployment-report.json),
  [host result](main-7218c43/native/deployment-evidence/deployment-result.json)
  and [workflow gate](main-7218c43/native/workflow-gate.json) retain original bytes.
  Host-result identity and hash agree with the report.
- [Missing evidence](main-7218c43/missing-evidence.json) lists the host paths and
  expected hashes for public-smoke/runtime files without inventing their contents.
- [Provenance](main-7218c43/provenance.json) records committed source, actual local
  working-tree state, review-source hashes and a Sydney-offset capture timestamp.
- [Complete AI review](../../agentic/shared-asd-group-services-cloud-deployment-20261022-172300-449579.md),
  [machine validation](../../agentic/shared-asd-group-services-cloud-deployment-20261022-172300-449579.validation.json)
  and [console](main-7218c43/review-console.txt) retain the initial answer, feedback,
  attempted adaptation and deterministic final summary.
- [Local JUnit](main-7218c43/tests.xml): 362 tests passed across the feature suite
  and shared Cloud Deployment Review tests, with all four AI flags disabled.
- [Docker JUnit](main-7218c43/docker-results/tests.xml): 356 feature tests passed
  in the rebuilt test image, with all four AI flags false and live opt-ins zero.

The review finished at approximately 5:23 pm AEDT on 22 October. Exit code **1**
deliberately reflects `incomplete`; it is not an Ollama crash or a passing release
gate. Native GitHub/AWS timestamps retain original offsets for integrity; this
explanation uses Sydney time.

## Critical reading of the model output

The model incorrectly claimed public CRUD and actual disabled-AI responses were
observed, despite their detailed captures being absent. Its reviewer did not
catch that semantic error. It also formatted the required exact status line with
Markdown. The shared guard rejected that format and, because collected evidence
remained incomplete, used its deterministic summary as the final result. The
original incorrect statements remain in the report; they are **not** test evidence.

Structural completion is not factual correctness. A successful deployment report
and file hashes do not substitute for missing detailed checks. Offline validation
cannot independently prove remote authenticity or production capacity. An AI
review cannot grant human release approval.

## Remaining work

1. An authorised operator retrieves this release's existing `public-smoke.json`
   and `runtime.json` from the paths in `deployment-result.json`, preserving bytes
   and matching hashes. Do not retrieve `cloud.env`, passwords or other private
   configuration. Retrieval does not require rerunning CRUD or deploying again.
2. Capture a real same-release health observation window: EC2/system status,
   new OOM events, unexpected restarts, timestamp and measured duration. Do not
   assign an old window to this SHA. No health observation was invented here.
3. Review those results and outstanding group security findings before recording
   an explicit, reasoned human release decision. This file is not that decision.
4. Supply the captures through a new manifest and rerun the review, preserving
   this incomplete attempt. Separately complete the customer browser login check.

The local AWS CLI and credentials were unavailable during this capture. No AWS
command, deployment, resource change, customer mutation, workflow decision, Git
commit or push was performed. Changes are limited to Ethan Ting's local capture
helper, tests, documentation and evidence.

## Reproduce

Download this run's `aws-deployment-evidence` and matching student-workflow-gate
archives through authenticated GitHub. Put them in a **new** output directory as
`artifacts/deployment.zip` and `artifacts/workflow-gate.zip`, then run:

```bash
.venv311/bin/python 'student-Ethan Ting/scripts/capture_cloud_review.py' \
  --run-id 39701565735 \
  --output docs/evidence/release2-ethan-ting/step5-cloud/NEW-CAPTURE

TZ=Australia/Sydney AI_MODE_ENABLED=true OLLAMA_MODEL=llama3.1:8b \
RELEASE_REVIEW_SOURCE_SHA=7218c437182feb42c202abf15232b535675576e2 \
CLOUD_DEPLOYMENT_REVIEW_MANIFEST=docs/evidence/release2-ethan-ting/step5-cloud/NEW-CAPTURE/cloud-manifest.json \
  .venv311/bin/python -u ai-services/agentic_loop.py \
  --feature shared --mode cloud-deployment
```

The helper requires committed HEAD to match the selected run and rejects tracked
source edits, digest mismatches, duplicate/unlisted archive members and replacing
old captures. For a later source SHA, select its actual run and change the review
environment. This old run cannot certify later code or a newer live release.
