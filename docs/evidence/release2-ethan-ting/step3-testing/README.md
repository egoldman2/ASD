# Ethan Ting: current Testing Review evidence

Captured and reviewed on 21 October 2026, Sydney time. Selected application source:
`4fa1ac861d0651b8c8a6f2861b32e2489d642a3f` (`Update Dockerfile`).

## Result

All five assigned main-push workflows completed successfully for that exact source.
Their downloaded endpoint archives each match GitHub's SHA-256 artifact digest.
The shared validator accepted all five owners and all ten assigned endpoint tests,
with zero failures, errors or skips and no missing/invalid capture issues.

| Feature | Real successful Actions run | Assigned tests |
| --- | --- | --- |
| Customer accounts and loyalty | [39596314302](https://github.com/egoldman2/ASD/actions/runs/39596314302) | 2 passed |
| Product catalogue | [39596314164](https://github.com/egoldman2/ASD/actions/runs/39596314164) | 2 passed |
| Inventory | [39596313885](https://github.com/egoldman2/ASD/actions/runs/39596313885) | 2 passed |
| Orders and returns | [39596313969](https://github.com/egoldman2/ASD/actions/runs/39596313969) | 2 passed |
| Customer support | [39596314311](https://github.com/egoldman2/ASD/actions/runs/39596314311) | 2 passed |

**Overall shared Testing Review: FAIL, not a release approval.** Passing endpoint
tests do not waive security findings. This run does not assess cloud deployment.

## Security findings and classification

Fresh, unfiltered output is under `main-4fa1ac8/security/`. Actual command exit codes
are in `scans.json`; raw stderr is retained too.

- Ruff: 29 findings remain (11 shared AI services, 16 Chufeng, one Howard test,
  one documentation tool). None are in Ethan Ting's feature. Relevant owners must
  fix or specifically assess these; no team source was changed during this capture.
- detect-secrets: 75 raw potential matches. Separate digest/line classification
  identifies 48 detections on `hashed_secret` fields in the baseline file itself,
  and 27 source matches already in that baseline. Zero are unclassified against
  this baseline. These counts are **not 75 verified leaked credentials**. Baseline
  membership is also not proof that a credential is safe. The unchanged shared
  validator counts all raw detections as unexcepted, so this gate remains failed.
- pip-audit: four unique ChromaDB advisory IDs remain. Only the existing documented
  exceptions are referenced; no new exception or human risk acceptance was granted.

`secret-classification.json` records categories, paths, line numbers and baseline
hashes without copying credential values. It does not filter the raw scan or alter
the shared validator's status. A follow-up should review those baseline entries
and the validator's treatment of baseline metadata, not simply suppress detectors.

## Actual Plan, Act, Observe, Adapt run

The existing shared loop ran locally against the new manifest with installed
`llama3.1:8b`; the model was selected through an environment override, not a change
to shared defaults. Initial review, reviewer feedback and adaptation are preserved.
The model's bold status formatting failed an exact-format grounding check; the
loop retained the real model outputs and used its deterministic fallback to
preserve the failed security gates. No output was rewritten to invent a pass.

- [Full review](../../agentic/shared-asd-group-services-testing-20261021-231020-165055.md)
- [Deterministic validation](../../agentic/shared-asd-group-services-testing-20261021-231020-165055.validation.json)
- [Original console output](main-4fa1ac8/testing-review.console.txt)
- [Selected manifest](main-4fa1ac8/testing-manifest.json)

The console was captured through `tee`; its shell pipeline status is not used as
the review outcome. The saved validation JSON is authoritative and records `fail`.

## Reproduce

From the repository root, using the existing Python environment:

```bash
# Use a NEW output folder for a new capture. Previous captures are not overwritten.
.venv311/bin/python 'student-Ethan Ting/scripts/capture_testing_review.py' capture \
  --output docs/evidence/release2-ethan-ting/step3-testing/NEW-CAPTURE
```

Download each artifact listed in `download-plan.json` from the corresponding real
Actions run into `<feature>/endpoints.zip`. Then run `assemble` with the same
output directory. It checks GitHub's digest before extracting exactly three
bounded files. `refresh` updates workflow/job metadata if a run was still pending.

Re-run the current shared review with explicit source and manifest:

```bash
TZ=Australia/Sydney AI_MODE_ENABLED=true OLLAMA_MODEL=llama3.1:8b \
RELEASE_REVIEW_SOURCE_SHA=4fa1ac861d0651b8c8a6f2861b32e2489d642a3f \
TESTING_REVIEW_MANIFEST=docs/evidence/release2-ethan-ting/step3-testing/main-4fa1ac8/testing-manifest.json \
  .venv311/bin/python ai-services/agentic_loop.py --feature shared --mode testing
```

The collector reports source HEAD separately from its untracked capture tooling
and generated evidence. Existing team manifests and historical captures remain
unchanged. The loop validates captures offline; it does not independently
authenticate their origin. The collection step fetched the live GitHub API and
verified downloaded archive digests, but that does not grant a release approval.

## Human decision and next work

**Human release decision: not recorded.** The student must review the unresolved
risks and record their own decision and reasons. Do not describe this as an accepted
release. Follow up on the group security findings and run Cloud Deployment Review
against an explicitly selected deployment/version. No commit, push, deployment,
customer mutation or risk acceptance was performed in this step.
