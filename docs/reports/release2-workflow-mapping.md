# Release 2 workflow identities

S10 uses the current named feature workflows, verified against GitHub's workflow
API on 17 October 2026 (Sydney). This records file/ID ownership from existing
workflow titles and source; it does not assign or confirm new student numbers.
Goldman's numeric filename remains unconfirmed and no teammate file is renamed.

| Owner / feature | Existing workflow | GitHub workflow ID |
| --- | --- | --- |
| Ethan Goldman / Customer Support | `.github/workflows/EthanGoldman.yml` | 344339772 |
| Chufeng / Product Catalogue | `.github/workflows/Chufeng.yml` | 335370198 |
| Ryan Nolan / Inventory | `.github/workflows/Ryan.yml` | 349934041 |
| Ethan Ting / Accounts and Loyalty | `.github/workflows/student-3.yml` | 334044998 |
| Howard / Orders and Returns | `.github/workflows/Howard.yml` | 340892125 |

The versioned source of this mapping is `cloud/student-workflows.json`. Legacy
numbered entries still returned by GitHub are not substitutes for these five
named feature workflows. Before an agreed filename migration, update both the
mapping and report-review paths together and verify the new actual workflow ID;
never infer an ID from a number or accept another workflow's success.

`cloud/check_workflows.py` takes one exact source SHA, requires five successful
main push runs and every reported job from the exact latest run attempt, and
rechecks the main reference. Missing/pending evidence polls for at most 1,200
seconds by default; `--timeout 0` takes one bounded snapshot. It never substitutes
PR/branch runs or an older green attempt for a failed rerun. A changed main SHA
returns `superseded`, with `current=false` for Actions, rather than granting a
passing gate. An API error, incomplete/duplicate page, oversized capture, skipped
job or invalid identity fails closed. The safe report contains IDs, URLs and
outcomes; no repository token or API error body is retained.

```bash
# Read-only diagnostic; use the actual deployment candidate SHA.
python3 cloud/check_workflows.py --sha '<40-character main SHA>' \
  --timeout 0 --report .aws-deployment/workflow-gate.json
```

The implementation follows GitHub's primary REST documentation for
[filtered workflow runs](https://docs.github.com/en/rest/actions/workflow-runs#list-workflow-runs-for-a-repository)
and [jobs from a run attempt](https://docs.github.com/en/rest/actions/workflow-jobs#list-jobs-for-a-workflow-run-attempt).
S10a supplies the checker and deterministic tests; S10b connects the gate,
main-candidate checks and student trigger/disabled-flag consistency. These source
checkpoints do not prove a final five-student main release or AWS deployment.
