# Release 2 report evidence contract

S12a supplies `ai-services/report_validation.py`, a read-only structured Testing
Report validator. S12b connects it to the existing Agentic Loop. This document
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
