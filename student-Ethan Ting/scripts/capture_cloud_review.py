"""Capture exact-source cloud evidence using GitHub GETs and downloaded archives.

This does not deploy, execute AWS commands, test CRUD, or grant release approval.
Missing native runtime/smoke/health captures remain missing in the manifest.
Run once in a new evidence directory containing artifacts/deployment.zip and
artifacts/workflow-gate.zip downloaded through the authenticated GitHub connector.
"""

import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import stat
import subprocess
from zipfile import ZipFile
from zoneinfo import ZoneInfo

import requests


ROOT = Path(__file__).resolve().parents[2]
API = "https://api.github.com/repos/egoldman2/ASD"
DEPLOYMENT_FILES = {
    ".aws-deployment/deployment-candidate.json",
    "deployment-report.json",
    "deployment-evidence/deployment-result.json",
    "deployment-evidence/local-smoke.json",
    "deployment-evidence/public-smoke.json",
    "deployment-evidence/runtime.json",
}


def now():
    return datetime.now(ZoneInfo("Australia/Sydney")).isoformat()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()  # noqa: S603,S607 - Fixed Git executable/arguments below; no shell.


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def reference(path):
    return {"path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256(path.read_bytes()).hexdigest()}


def api(path):
    response = requests.get(API + path, timeout=30, allow_redirects=False)
    response.raise_for_status()
    if response.status_code != 200:
        raise ValueError("Expected HTTP 200 from the fixed GitHub repository API.")
    return response.json()


def extract(archive, expected_digest, allowed, destination):
    """Verify native digest before extracting only bounded, allowlisted JSON files."""
    if archive.is_symlink() or archive.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Invalid archive size or symlink.")
    if "sha256:" + sha256(archive.read_bytes()).hexdigest() != expected_digest:
        raise ValueError("Archive does not match GitHub's recorded SHA-256.")
    with ZipFile(archive) as zipped:
        rows = zipped.infolist()
        names = [row.filename for row in rows]
        if len(names) != len(set(names)) or not set(names) <= allowed:
            raise ValueError("Unexpected or duplicate archive member.")
        for row in rows:
            if row.file_size > 1024 * 1024 or stat.S_ISLNK(row.external_attr >> 16):
                raise ValueError("Oversized or symlink archive member.")
            raw = zipped.read(row)
            json.loads(raw)
            target = destination / row.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(raw)
    return names


def capture(output, run_id):
    if git("diff", "HEAD", "--name-only"):
        raise ValueError("Tracked source edits prevent claiming a clean committed source.")
    source = git("rev-parse", "HEAD")
    run = api(f"/actions/runs/{run_id}")
    if not (run["head_sha"] == source and run["head_branch"] == "main"
            and run["event"] == "push" and run["path"] == ".github/workflows/cloud-deployment.yml"):
        raise ValueError("The selected cloud push run must match committed HEAD on main.")
    jobs = api(f"/actions/runs/{run_id}/jobs?per_page=100")
    artifacts = api(f"/actions/runs/{run_id}/artifacts?per_page=100")
    if jobs["total_count"] != len(jobs["jobs"]) or artifacts["total_count"] != len(artifacts["artifacts"]):
        raise ValueError("Paginated evidence must not be silently truncated.")
    save(output / "provenance.json", {"owner": "Ethan Ting", "captured_at": now(),
        "source_sha": source, "run_id": run_id,
        "working_tree_status": git("status", "--short").splitlines(),
        "source_scope": "Committed HEAD. Capture helper/evidence may be untracked; hashes below retain review inputs.",
        "aws_commands_executed": False, "cloud_mutations_performed": False,
        "human_release_decision": "not_recorded", "commit_or_push_performed": False,
        "review_source_files": [reference(ROOT / path) for path in (
            "ai-services/agentic_loop.py", "ai-services/report_validation.py",
            "shared/agentic/review_config.json", "shared/agentic/review_prompt.txt",
            "shared/agentic/cloud_deployment_prompt.txt",
            "student-Ethan Ting/scripts/capture_cloud_review.py")]})
    save(output / "actions-run.json", run)
    save(output / "actions-jobs.json", jobs)
    save(output / "artifacts.json", artifacts)
    save(output / "actions.json", {**run, "jobs": jobs["jobs"]})
    captures = {}
    for name, filename, allowed in (
        ("aws-deployment-evidence", "deployment.zip", DEPLOYMENT_FILES),
        (f"student-workflow-gate-{source}-{run['run_attempt']}", "workflow-gate.zip", {"workflow-gate.json"}),
    ):
        matches = [row for row in artifacts["artifacts"] if row["name"] == name and not row["expired"]]
        if len(matches) != 1 or matches[0]["workflow_run"]["head_sha"] != source:
            raise ValueError("Expected exactly one unexpired same-source native artifact.")
        native = matches[0]
        archive = output / "artifacts" / filename
        members = extract(archive, native["digest"], allowed, output / "native")
        captures[filename] = {"artifact_id": native["id"], "run_id": run_id,
            "expected_digest": native["digest"], "archive": reference(archive), "members": members}
    save(output / "archive-verification.json", captures)
    deployment_path = output / "native/deployment-report.json"
    deployment = json.loads(deployment_path.read_text())
    result_path = output / "native/deployment-evidence/deployment-result.json"
    result = json.loads(result_path.read_text())
    if deployment["evidence_files"]["deployment-result.json"]["sha256"] != sha256(result_path.read_bytes()).hexdigest():
        raise ValueError("The deployment-result hash disagrees with the native report.")
    for key in ("source_sha", "source_sha256", "release_id", "target_instance", "public_url"):
        if deployment[key] != result[key]:
            raise ValueError("Deployment result and report identify different releases.")
    manifest = {"schema_version": 1, "kind": "cloud-deployment", "owner": "Ethan Ting",
        "captured_at": now(), "source_sha": source,
        "command": "Capture public GitHub run/jobs/artifacts and digest-verified native archives; preserve missing captures and absent human decision.",
        "deployment": reference(deployment_path), "actions": reference(output / "actions.json"),
        "workflow_gate": reference(output / "native/workflow-gate.json")}
    missing = []
    for key, filename in (("public_smoke", "public-smoke.json"), ("runtime", "runtime.json")):
        path = output / "native/deployment-evidence" / filename
        if path.exists():
            if sha256(path.read_bytes()).hexdigest() != result["artifact_refs"][filename]["sha256"]:
                raise ValueError("Native capture hash disagrees with the accepted host result.")
            manifest[key] = reference(path)
        else:
            missing.append({"kind": key, "expected_host_reference": result["artifact_refs"].get(filename),
                "reason": "The native Actions artifact exports its hash reference, not the capture bytes."})
    missing.extend([
        {"kind": "health", "reason": "No same-source measured health window captured in this run's downloaded artifacts."},
        {"kind": "human_release", "reason": "No student release approval supplied for this source. Historical decisions are not reused."},
        {"kind": "customer_browser_login", "reason": "The manual customer sign-in and own-account view remain unverified."},
    ])
    save(output / "missing-evidence.json", {"source_sha": source, "captured_at": now(), "missing": missing,
        "older_capture_reused": False, "local_aws_cli_available": False,
        "limitations": "Offline validation cannot independently prove remote authenticity or substitute hashes for missing capture content."})
    save(output / "cloud-manifest.json", manifest)
    print(json.dumps({"manifest": reference(output / "cloud-manifest.json"), "missing": [row["kind"] for row in missing]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT / "docs/evidence/release2-ethan-ting") or args.run_id <= 0:
        parser.error("Use a positive run ID and a directory confined to Ethan Ting's evidence.")
    capture(output, args.run_id)


if __name__ == "__main__":
    main()
