# Ethan Ting: current security findings and Testing Review

22 October 2026, Sydney time. Published source:
`d297a42f144cd645f38ca294a1ae42c639ff58be`.

## Outcome

- Ethan Ting's current feature folder and owned MCP test have **zero Ruff security
  findings**, including the newer uncommitted cloud-evidence helpers/tests.
- The current feature secret scan has **21 existing baseline matches and zero
  new unclassified matches**. Matching the baseline is not a new acceptance or
  proof of safety; the raw records remain available.
- The clean published group source has **28 Ruff warnings**, **75 raw secret-scan
  detections** and **four unique ChromaDB advisory IDs**. Warnings are not a count
  of confirmed exploitable vulnerabilities.
- All **five same-SHA student workflows and ten allocated endpoint tests pass**.
  Their actual native artifacts were downloaded, digest-verified and retained.
- The shared Testing Review remains **fail**. Source warnings are not silently
  waived, and the existing validator treats all raw secret detections as
  unexcepted, including baseline metadata. Prior dependency exceptions remain
  documented; no new exception or release approval was created.

## Source separation

The user's checkout contained uncommitted Step 6/7 evidence and documentation.
It was not reset, stashed or committed. A temporary shared clone at the real
published SHA was used to run the existing collector with a clean source tree.
Original absolute Ruff paths under `/private/tmp/asd-security-review.2wwjEM/source`
are preserved in raw JSON, not relabelled as working-tree findings.

The separate [working-tree scans](working-tree/security/) include Ethan Ting's
new local files and are not claimed as part of published `d297a42` CI.
[Capture context](capture-environment.json) records this distinction and security
configuration hashes. No source, baseline, hook, dependency or teammate file was
changed by this audit. Only local evidence/documentation was added.

## Ownership and source review of all 28 Ruff warnings

| Owner/scope | Count | Source observation and next action |
|---|---:|---|
| Chufeng: `backend/controllers/ai_controller.py`, S310 | 2 | Ollama's URL comes from an environment value; the calls do not show a local-origin/scheme guard, redirect rejection or a bounded response read. Ask the owner to harden the configured model boundary and test invalid origins/redirects/oversized responses. This is a configuration-hardening finding, not proof that a public user can set that environment value. |
| Chufeng: `database/api.py:388`, S104 | 1 | Native startup defaults to all interfaces. Local Compose also publishes product database port 6001 without a loopback bind. The owner should review limiting the host-published port and native default to loopback while preserving explicit container binds. OS/network policy affects actual reachability. Cloud Compose does not publish this database port, so this is not evidence of a publicly exposed AWS database. |
| Chufeng: `database/api.py`, S608 | 9 | Inspected queries interpolate constant column lists and fixed-branch WHERE/ORDER fragments. Search values and IDs use bound parameters. These are reviewed query-composition warnings, not nine demonstrated injection attacks. The owner can retain explicit line-level rationale or refactor and add injection-regression tests. No blanket suppression was added here. |
| Chufeng: Multi-Agent and RAG controllers, S101 | 4 | Assertions check non-None values after validators have already returned on failure. The reviewed validation/authentication checks precede them; the assertions are not the only authorization gate. The owner should replace redundant assertions or document their invariant role. |
| Shared MCP/Multi-Agent config, S104 | 2 | Both flagged lines compare a host string to the all-interface address to display a loopback endpoint; they do not perform a bind. Defaults are loopback. These are reviewed address-conversion warnings, not demonstrated insecure default listeners. |
| Shared MCP/RAG test fixtures, S104 | 6 | Explicit all-interface strings in configuration/protocol test fixtures. These are test inputs, not live server observations. Ask the shared owner to document narrowly rather than disable the rule globally. |
| Shared RAG HTTP handlers, S101 | 3 | The JSON validator returns an error for non-object/invalid bodies before the handler assertion. These are redundant type/invariant assertions, not the only request-validation boundary. Shared-owner review/refactor is appropriate. |
| Ethan Ting: historical `docs/evidence/release1-ethan-ting/validate_local.py:52`, S607 | 1 | A manual evidence script invokes fixed Docker arguments with a PATH-resolved executable and no shell. This is not application request handling. Keep the historical artifact intact; use an explicitly resolved executable in a future replacement if the script is reused. No historical output was rewritten to hide this warning. |

Counts: **16 Chufeng + 11 shared AI + 1 historical evidence = 28**. Ryan, Howard,
Goldman and Ethan Ting's current feature folders have no Ruff findings in this
published scan. This is only scanner scope, not a claim that every other possible
security defect has been ruled out. Ownership refers to feature/module scope,
not proof of who authored each line.

## Secret detections

[Raw scan](main-d297a42/security/detect-secrets.json) and
[classification](main-d297a42/secret-classification.json) retain all 75 detections:

- 48 are detections on the baseline file's `hashed_secret` metadata.
- 27 match existing source baseline fingerprints and detector types.
- Zero are new unclassified fingerprints relative to that baseline.

Existing source matches comprise 21 Ethan Ting test entries, three support test
entries and three infrastructure-template entries. The classification contains
paths/lines/types, not plaintext secret values. No credential was validated
against a remote provider. All raw records remain in the review; the security
baseline and deterministic review policy were not changed to manufacture a pass.
This collector uses the existing exclusions for `docs/evidence/`, shared runtime
history/audit logs, minified JavaScript and `.log` files. Its result does not prove
excluded evidence/log files are free of private data. The detector ran with
`--no-verify`, so findings were not tested against external credential providers.

## Dependency advisories

The unfiltered [pip-audit report](main-d297a42/security/pip-audit.json) reports
ChromaDB **1.5.9** with unique IDs `PYSEC-2026-311`, `PYSEC-2026-3813`,
`PYSEC-2026-3814`, and `PYSEC-2026-3815`. ID 311 occurs twice in the raw feed;
it is not counted as two distinct advisories. Each finding lists no fixed version
in this captured audit feed. This is not a permanent claim about future releases.

The existing four documented exceptions are retained as `pass_with_exceptions`
by the shared validator. They are not newly approved here. RAG currently uses an
embedded `chromadb.PersistentClient`, defaults its HTTP wrapper to loopback, and
cloud packaging removes the ChromaDB requirement. Those are exposure context,
not proof that all advisory paths are unreachable or permission to dismiss them.
The shared dependency/RAG owners should review current vendor fixes or an
alternative and record an explicit decision before changing accepted risk.

## Review and test evidence

- [Manifest](main-d297a42/testing-manifest.json),
  [native scans and exit codes](main-d297a42/scans.json),
  [source provenance](main-d297a42/provenance.json), and
  [artifact download/digest plan](main-d297a42/download-plan.json).
- Five native endpoint ZIPs, actual Actions jobs/context and extracted JUnit
  reports are retained under each feature directory in `main-d297a42/`.
- [Console](main-d297a42/review-console.txt) retains the real shared
  Plan → Act → Observe → Adapt execution with local `llama3.1:8b`.
- [Full shared review](../../agentic/shared-asd-group-services-testing-20261022-184136-854716.md)
  and [independent validation](../../agentic/shared-asd-group-services-testing-20261022-184136-854716.validation.json)
  retain initial model output, reviewer feedback, attempted adaptation and the
  final deterministic summary.
- [Review-validation JUnit](main-d297a42/review-tests.xml): 55 local validator and
  review-mode tests passed using synthetic captures. These are not live feature
  tests or a substitute for the ten native endpoint cases above.

Exit code 1 represents the deterministic **fail**, not a successful release gate
or a model transport failure. The model used an incorrectly formatted status
line and omitted the required offline-authenticity limitation, so the guard used
its deterministic summary. The model's phrase "detect-secrets failed" means the
review gate failed, not that the scanner crashed: the raw scanner exit code is
0, with 75 detections in its JSON. Raw model wording is not rewritten.

## Next decisions

Prioritise the catalogue model-call boundary and local database-listener exposure
with their owner. The shared owner should resolve or narrowly justify shared
test/invariant/address-conversion warnings. The evidence owner should retain the
historical script warning honestly. The group must decide how reviewed baseline
metadata/fixtures and dependency exceptions are represented in its testing policy;
this audit does not silently change that policy or grant acceptance.

After actual source/policy changes are authorised, publish them, retain new
same-source scans and endpoint CI, then rerun Testing Review. Do not call the
group security gate passed solely because feature CI and AWS checks passed.
No message was sent to teammates and no commit, push or AWS change occurred.

## Reproduce the review

```bash
TZ=Australia/Sydney AI_MODE_ENABLED=true OLLAMA_MODEL=llama3.1:8b \
RELEASE_REVIEW_SOURCE_SHA=d297a42f144cd645f38ca294a1ae42c639ff58be \
TESTING_REVIEW_MANIFEST=docs/evidence/release2-ethan-ting/step8-security/main-d297a42/testing-manifest.json \
  .venv311/bin/python -u ai-services/agentic_loop.py --feature shared --mode testing
```
