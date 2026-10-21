# Ethan Ting: Release 2 security and endpoint testing

21 October 2026, Australia/Sydney. This report covers Criteria 3 and 4 preparation.
Source baseline: `4d635cc87541fe97331c8640ff73e7f40a007232`. Today's security repairs
remain **uncommitted and unpushed**, at the user's request. No real commit was made
to manufacture commit-time evidence.

## Local pre-commit checks

The existing pinned tools were installed into `.venv311`: pre-commit 4.7.0,
Ruff 0.17.0, detect-secrets 1.5.0 and pip-audit 2.10.1. The actual pre-commit Git
hook is installed in this checkout, with its Python interpreter recorded in the
hook. It will run on a normal commit, including one made through GitHub Desktop.

`capture.json` records actual commands, exit codes, Sydney capture time, source
hashes, hook metadata and working-tree status. The generated `*.stdout.txt` and
`*.stderr.txt` files retain unedited tool output. Reproduce with:

```bash
.venv311/bin/python 'student-Ethan Ting/scripts/capture_release2_security.py'
```

| Scope | Actual result |
| --- | --- |
| Ruff security rules, Ethan Ting feature and owned MCP rule-comparison test | Pass, no unreviewed findings |
| Existing pre-commit hooks, explicit owned-file set, pre-commit stage | All three hooks pass |
| Independent detect-secrets source scan | 21 digests match the existing baseline; zero unclassified digests |
| Whole-repository Ruff scan | **29 findings remain** outside the feature scope; not a group-wide pass |
| Unfiltered aggregate dependency audit | **Exit 1**: four unique ChromaDB advisory IDs remain |

The secret baseline contains Windows-style paths; the digest comparison normalizes
path separators, not secret values. `secret-digest-review.json` shows classification
against the unchanged baseline. New test-only URL credentials and an intentionally
invalid hash have specific inline explanations. No global detector was disabled,
no new baseline entries were added and no real production credentials were found
or introduced by these changes.

The shared audit hook already excludes `PYSEC-2026-311`, `PYSEC-2026-3813`,
`PYSEC-2026-3814` and `PYSEC-2026-3815`. The raw audit reports ChromaDB 1.5.9 with
empty fix-version lists (and a duplicate entry for 311). A passing configured hook
is **not** a vulnerability-free result or a new human risk acceptance. The existing
team exceptions are retained, not expanded. Whole-repository Ruff findings comprise
11 in shared AI services, 16 in Chufeng's feature, one in Howard's tests and one in
documentation tooling; owners must assess them separately.

## Repairs and reviewed warnings

- Backend database/RAG/Ollama URLs now reject non-HTTP(S) schemes, malformed origins,
  embedded credentials, origin path/query/fragment, external API paths and control
  characters before I/O. Internal service redirects are rejected. Three `S310`
  constructor warnings have local explanations referring to this validation.
- Native backend/database listeners default to `127.0.0.1`. Docker images explicitly
  set `APP_HOST=0.0.0.0`; cloud Gunicorn bind commands are unchanged.
- `S608` is narrowly reviewed: the four update assignments are fixed literals;
  every supplied value and the user ID is bound. AST and real temporary SQLite
  tests prove that a SQL-looking name is stored literally and caller-supplied
  column names cannot change an account's role.
- The owned MCP comparison test's `S102` warning is classified locally: it executes
  only the repository's parsed `loyalty_status` function in an isolated namespace,
  not user input or database module startup.
- Newly introduced fixture-only secret warnings are resolved or explicitly reviewed;
  the Multi-Agent test Flask key is generated rather than hardcoded.

`local-regression.xml` records **363 passing tests** across the feature, owned MCP
rule tests and shared endpoint-evidence tests. `local-endpoint-functions.xml`
separately records both allocated functions passing locally. Backend/database
Docker images build successfully; isolated disposable-container checks confirmed
their Docker binding configuration, backend shared imports and database health.
No production/customer data volume was mounted for those container checks.

## Published post-commit endpoint evidence

[Run 39446704204](https://github.com/egoldman2/ASD/actions/runs/39446704204) is a real
successful push-triggered `student-3.yml` run for the baseline SHA above, created
at 2:15 am Sydney time on 21 October. Both its test and Docker jobs passed.

| Endpoint function | Endpoint | Actual published test |
| --- | --- | --- |
| `register` | `POST /api/register` | `test_customer_registration_creates_customer_session` |
| `create_loyalty_adjustment` | `POST /api/admin/loyalty/<int:user_id>/adjustments` | `test_admin_adjustment_includes_authenticated_admin_id` |

The downloaded artifact is retained unchanged as `ethan-ting-endpoints-4d635cc.zip`.
Its SHA-256 matches GitHub's reported artifact digest:
`45686bd660c756b6acbb005f85cd79013401eba0ee5e258e426586f7b6bd6da5`.
The three original files are extracted under `ci-4d635cc/`: `test-context.json`,
`endpoint-functions.xml` and `python-versions.txt`. JUnit records two tests, zero
failures/errors/skips. Context confirms all four AI flags false, all live opt-ins
zero, the actual source SHA, workflow and run URL. Raw GitHub run/job/artifact API
captures are retained alongside them. These are endpoint-function tests using the
real Flask route code with a controlled database adapter, not live cloud HTTP tests.

## Still required after review

The feature-scoped hooks were invoked manually using the pre-commit hook stage;
this is not evidence that today's edits have already passed a real commit hook.
When approved, make a normal commit (do not bypass hooks), retain its output, then
push and save the new successful student-3 run and artifact. The published baseline
run cannot certify these uncommitted security changes. Group Testing Review,
cloud deployment and final submission are separate steps.
