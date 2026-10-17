# Release 2 report evidence contract

S12a supplies `ai-services/report_validation.py`, a read-only structured Testing
Report validator. S12b connects it to the existing Agentic Loop's `testing` mode. This document
defines inputs; it is not a passing release report or a human decision.

Call `collect_testing_evidence(root, manifest_path, source_sha, required_features,
expected_endpoints=..., accepted_advisories=...)`. The expected 40-character code
SHA and feature scope come from the selected review, independently of the manifest.
Support requires `customer_support`; shared review requires all five existing
feature IDs. Expected support endpoint descriptors are `customer_create` and
`admin_update`, using the exact method/path/test-node mapping captured by S09.
Other owners must supply their real assignments and results. Official student
workflow numbering remains unconfirmed; this validator does not assign numbers.

The JSON manifest has `schema_version: 1`, `kind: testing`, `source_sha`, `owner`,
timezone-aware `captured_at`, `security` and `students`. Every scan/student capture
also has `source_sha`, `owner`, timezone-aware `captured_at` and the actual `command`.
All referenced artifact descriptors are `{path, sha256}`, with a project-relative
path and the SHA-256 of the exact captured bytes. The manifest itself is hashed on
read. If a sanitized copy is used, hash that copy and retain its original archive
digest and sanitization record separately.

`security` contains exactly one capture for each of `ruff`, `detect-secrets` and
`pip-audit`. Each has `tool`, actual `exit_code` and `report`:

- Ruff: native JSON array of findings from `ruff check --select S --output-format json`.
- Detect-secrets: native scan JSON including `version`, nonempty `plugins_used`
  and `results`. A zero process exit does not erase detections.
- Pip-audit: native JSON object with nonempty `dependencies`, each with `name`,
  `version` and `vulns`. Skipped dependencies cannot establish a complete audit.
  Do not filter out findings or use advisory ignores in the captured raw report.

A dependency capture may include `exceptions`: each has advisory `id`, bounded
`reason` and a hash-checked `record` referencing the actual exception documentation.
The caller must also explicitly allow that advisory. Missing, unconfigured or
invalid exception records leave findings failed. Valid exceptions produce
`pass_with_exceptions`, preserving raw finding count, exit code and accepted IDs.
This is a technical classification, not a newly granted human risk acceptance.

Each student capture contains:

- `feature` and a distinct `owner` matching its captured test context.
- Exactly two `endpoints`, each with `function`, `method`, `path` and
  `test_node_id`. Nodes must be in that feature owner's existing test directory;
  configured expected descriptors must match exactly.
- `junit`: the named endpoint JUnit artifact. Each declared node must occur once
  and pass, with no failure, error or skip. Aggregate failures/errors remain failed;
  unrelated skips are counted and visible. Use pytest's flat suites/cases format;
  nested suites, XML entities/DTDs and inconsistent declared counts are rejected.
- `context`: the actual post-commit Actions context JSON, matching S09's owner,
  feature, SHA, run ID/URL, push event/ref, workflow path, endpoint filename/mapping,
  four false AI flags and all seven zero live opt-ins.
- `actions`: captured GitHub run/job JSON containing `id`, `head_sha`,
  `head_branch`, `event`, `html_url`, workflow `path`, `status`, `conclusion` and
  all `jobs` with status/conclusion. A pending, failed or skipped job cannot pass.

Results are `pass`, `pass_with_exceptions`, `fail` or `incomplete`. A known failed
scan/test/job takes precedence over other missing inputs. Findings, exceptions,
skips, deterministic issue codes and each input's path/hash/byte count are retained.
Raw source, scan prose and JUnit stdout are not copied into the model digest;
owner email/phone redaction applies. The validator executes no command, performs
no network request and changes no input file.

Limits: manifest 128 KiB, each referenced file 1 MiB, total reads 8 MiB, at most
40 file reads, three security captures and five students. Absolute paths,
symlink escapes, non-regular files, hash mismatches and malformed reports fail
validation. Archive larger captures deliberately rather than silently truncating
or discarding failures.

The validator parses supplied captures offline. It does not independently prove
their remote authenticity, current GitHub status, official endpoint allocation or
a human release decision. Preserve run/artifact URLs and original archive digests,
verify current exact-SHA Actions results separately, and disclose that limitation
in generated reviews. YAML source markers and model prose never prove passing CI.

## Run a Testing Report Review

Prepare the real manifest and artifacts first; the configured default paths are
not pre-populated with placeholder success evidence. Select the actual code SHA
independently, then run the existing host loop with Ollama available:

```bash
export RELEASE_REVIEW_SOURCE_SHA='<40-character code SHA to review>'
export TESTING_REVIEW_MANIFEST='docs/evidence/release2-ethan-goldman/testing-manifest.json'
AI_MODE_ENABLED=true python ai-services/agentic_loop.py --feature 'student-Ethan Goldman' --mode testing
```

For the five-owner review, select `--feature shared` and its actual manifest.
The interactive menu also offers `9 = Testing Report`. The manifest override is
optional when using `testing_rules.manifest`; the selected SHA may alternatively
be set explicitly in `testing_rules.source_sha`. Missing configuration or captures
produce an incomplete result. Paths stay relative to the repository root.

The loop prints deterministic status before model review and saves the generated
Markdown under `docs/evidence/agentic/`, alongside `*.validation.json`. The JSON
retains status, selected SHA, all input hashes/results, model grounding issues and
the linked review's SHA-256. The Markdown links back to it. Model prose cannot
convert failed/incomplete evidence into a pass; findings and accepted exceptions
remain visible. `--no-save` creates neither artifact. Fixture tests use scripted
model replies and do not establish real model or human participation.
The CLI exits 1 for failed/incomplete deterministic report evidence; pass and
pass-with-exceptions exit 0. A zero exit still does not grant release approval.

## Cloud Deployment Report captures (S13a)

`collect_cloud_evidence(root, manifest_path, source_sha, required_workflows)` reuses
the same bounded, hash-checked reader. S13b connects it to the existing loop's
`cloud-deployment` mode and interactive option 10;
S14 supplies the deployment/smoke provenance fields and S16 supplies real captures.
`cloud/deploy.py` saves a sanitized deployment report and a hash-linked remote
result in `deployment-evidence/`. Its native local/public smoke and runtime files
stay in the release directory on EC2. Retrieve these through SSM and verify each
recorded SHA-256 before supplying manifest descriptors; a remote path/hash alone
is not the native capture. The collector still requires a separately observed
resource health window and genuine human release decision. Source/fixture checks
do not create either record.
This contract and its synthetic tests are not live deployment evidence.

The manifest uses `schema_version: 1`, `kind: cloud-deployment`, selected
`source_sha`, `owner`, timezone-aware `captured_at`, actual capture `command` and
artifact descriptors for `deployment`, `actions`, `workflow_gate`, `public_smoke`,
`runtime`, `health` and optional `human_release`. Every descriptor is `{path,
sha256}`. The expected code SHA and five distinct assigned student workflow paths
are provided independently. An unknown official allocation cannot pass by guessing.

- `deployment`: capture metadata plus `release_id` (`<code SHA>-<run attempt>`),
  bundle `source_sha256`, HTTPS `public_url`, `environment: aws-cloud`,
  `region: ap-southeast-2`, SSM `command_id`, EC2 `target_instance`, actual
  `run_id`/`run_attempt`, `trigger: github_actions`, SSM `status: Success` and
  `acceptance: passed`. A manual SSM success is insufficient.
- `actions`: actual cloud workflow/run/job metadata. The source SHA, main push,
  run ID/attempt, workflow path and successful deploy job must match. Every
  captured job must have completed successfully; skipped/pending jobs cannot pass.
- `workflow_gate`: `source_sha`, `status` and five raw `workflows` run summaries,
  with distinct IDs and the exact assigned paths. Each has the selected SHA,
  `head_branch: main`, `event: push`, run URL, completed/success result and all
  job statuses. A declaration that a gate passed cannot replace those records.
- `public_smoke`: selected SHA, release ID, actual HTTPS `base_url`, capture time,
  `status`, `cleanup_status` and bounded `checks`. Derive rows from real gateway
  requests, recording `method`, `path`, `status`, `passed`, `feature` and CRUD
  `operation` for each applicable request. Require create/read/update/delete for
  all five core features and a support staff `reply`. Match methods/statuses and
  existing API paths, rather than accepting a raw check count or homepage alone.
- Disabled-response rows also record `disabled_integration` and `safe_disabled`
  after checking the actual authenticated response. Require support AI/MCP/RAG/
  Multi-Agent, existing account AI/MCP/RAG and catalogue Multi-Agent checks on
  their concrete POST routes. Each must return safe disabled behaviour and 503.
  Teammates' additional integrations remain with their owners.
- `runtime`: capture metadata with `origin: ssm-runtime`, selected SHA, release
  ID/bundle digest and actual `/srv/asd/current` target in `current_release`.
  Inspect running container flags (`ai_flags`), `service_names` and host
  `listening_ports`; the four flags must be false and AI services/model ports
  absent. Source Compose flags alone are insufficient. No public diagnostics
  endpoint is required.
- `health`: capture metadata, same release/instance, positive
  `observation_seconds`, actual `instance_status`/`system_status`,
  `new_oom_events`, `unexpected_restarts` and `status`. A stable recorded window
  requires both instance checks OK and zero new events; it is not a production
  capacity guarantee or permission to change AWS capabilities.
- `human_release`: a genuine separately supplied record with selected SHA,
  `decision` (`accept`, `conditional_accept` or `reject`), `identity`,
  timezone-aware `decided_at` after deployment capture and nonempty `reason`.
  Conditional decisions additionally require `conditions`. The validator never
  generates this record. It retains only a redacted identity and decision summary;
  the input file/hash links to the actual reasons, without copying raw human prose.

`technical_status` covers captured deployment, gate, public smoke, runtime and
health evidence. `status` additionally requires an actual human acceptance:
missing/conditional decisions remain incomplete, and rejection or failed
technical checks remain failed. A successful model review cannot create approval.
Offline capture authenticity, unrecorded returns/supplier operations, broader
capacity and other release checks remain explicit limitations. Verify original
Actions/public/resource evidence separately before the real release decision.

Configure `cloud_deployment_rules.required_workflows` with the five confirmed
assigned paths before reviewing final evidence. Both supplied configs deliberately
start empty while allocation is unconfirmed; fixture names never become defaults.
Missing allocation/configuration remains incomplete and the summary shows the
configured count out of five.

```bash
export RELEASE_REVIEW_SOURCE_SHA='<actual integrated main code SHA>'
export CLOUD_DEPLOYMENT_REVIEW_MANIFEST='docs/evidence/release2-cloud-deployment-manifest.json'
AI_MODE_ENABLED=true python ai-services/agentic_loop.py --feature shared --mode cloud-deployment
```

Goldman's config also registers the mode for his report contribution. Manifest
overrides are optional when using the configured confined path. The shared report
infrastructure saves linked Markdown/validation JSON, preserves deterministic
status and returns nonzero for fail/incomplete evidence. Missing human approval
can therefore block final release even when `technical_status` is pass. This
review command never deploys, changes AWS, edits records or creates a decision.
