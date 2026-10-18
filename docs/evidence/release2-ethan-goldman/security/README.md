# Release 2 security testing report

Owner: Ethan Goldman. Captures date from 17 October 2026 (Australia/Sydney).
Python 3.11.16; Ruff 0.17.0, detect-secrets 1.5.0, pip-audit 2.10.1,
pre-commit 4.7.0. [Resolved baseline dependencies](s00-python311-versions.txt).

The original [all-files hook run](s00-all-files-hooks.txt) and
95 baseline Ruff findings record failures, not approval.
The later [whole-repository scan](s03a-all-ruff.json) retains **44 findings**.
Passing changed-file hooks do not clear this global result. Relevant source owners
must assess and fix or document their findings; no global rule was disabled.

Support's native database bind now defaults to loopback; Docker keeps its explicit
private-network bind. Support and shared RAG tests use pytest's private temporary
directories. One fixed-argv subprocess warning and 18 bound-SQL warnings have
specific reviewed explanations. SQL-looking values/identifiers, literal wildcards,
CRUD/summary/context reads and migration were checked with actual SQLite tests.
[Source hashes and unchanged production AST proof](s00c-verification.json)
distinguish false-positive classification from vulnerability repair. See
`student-Ethan Goldman/tests/test_database_query_security.py` for the regressions.

[Unfiltered dependency findings](s18a-dependency-findings.json) retain four existing
ChromaDB advisory exceptions: PYSEC-2026-311, PYSEC-2026-3813, PYSEC-2026-3814 and
PYSEC-2026-3815. [Captured package metadata](s18a-chroma-metadata.json) records missing fixes.
The advisory impacts are unauthenticated remote model-configuration code execution
([311](https://github.com/advisories/GHSA-f4j7-r4q5-qw2c)), authenticated collection-update
code injection ([3814](https://github.com/advisories/GHSA-36p7-vc44-83pf)), tenant-permission
bypass ([3815](https://github.com/advisories/GHSA-xph7-9rjv-w5fr)) and cross-tenant
collection access ([3813](https://github.com/advisories/GHSA-2wm9-hf6c-p5cr)).
Embedded local RAG narrows exposure but does not establish safety. Required cloud
packaging omits ChromaDB; no new exception or human risk acceptance was invented.

The installed Linux cloud-package audit separately found seven unique pip/setuptools
advisories. [Before](s14a-linux-audit-before.json), [after](s14a-linux-audit-after.json)
and [package metadata](s14a-package-metadata.json) show the repaired image scope.
Its zero findings do not clear the development/RAG exceptions.

Actual commit-time hooks are retained for [endpoint implementation](s09-commit-hooks.txt),
[cloud CPU repair](s03a-commit-hooks.txt) and [local evidence](s15a-commit-hooks.txt).
Ruff/detect-secrets skips on evidence-only commits are disclosed. The standard
secret hook excludes evidence; the [separate local evidence scan](s15a-evidence-review.json)
reviewed 98 known digests with zero unclassified findings and no new ignores.
Native model, browser, history/audit, scan and JUnit bytes remain unchanged.
