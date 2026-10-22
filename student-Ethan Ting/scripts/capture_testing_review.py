"""Capture same-source testing evidence without changing code, Git or cloud state.

Run `capture` first. Download the listed GitHub artifact archives into each
feature directory as endpoints.zip, then run `assemble`. Existing evidence stays
untouched. The shared validator, not this collector or an LLM, decides status.
"""

import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile
from zoneinfo import ZoneInfo

import requests


ROOT = Path(__file__).resolve().parents[2]
API = "https://api.github.com/repos/egoldman2/ASD"
WORKFLOWS = {
    "product_catalogue": ".github/workflows/Chufeng.yml",
    "inventory": ".github/workflows/Ryan.yml",
    "customer_loyalty": ".github/workflows/student-3.yml",
    "order_returns": ".github/workflows/Howard.yml",
    "customer_support": ".github/workflows/EthanGoldman.yml",
}


def now():
    return datetime.now(ZoneInfo("Australia/Sydney")).isoformat()


def run(argv):
    return subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=False)  # noqa: S603 - Fixed argv for local scans/Git below; no shell.


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def reference(path):
    return {"path": str(path.relative_to(ROOT)), "sha256": sha256(path.read_bytes()).hexdigest()}


def api(path):
    response = requests.get(API + path, timeout=30, allow_redirects=False)
    response.raise_for_status()
    if response.status_code != 200:
        raise ValueError("GitHub API did not return HTTP 200.")
    return response.json()


def capture(output):
    if output.exists():
        raise ValueError("Choose a new output directory to preserve previous captures.")
    source = run(["git", "rev-parse", "HEAD"]).stdout.strip()
    # Only this evidence collector may differ from the selected source code.
    dirty = run(["git", "diff", "HEAD", "--name-only"]).stdout.splitlines()
    if dirty:
        raise ValueError("Commit or preserve tracked source edits before capturing a source SHA.")
    output.mkdir(parents=True)
    save(output / "provenance.json", {"source_sha": source, "captured_at": now(),
        "owner": "Ethan Ting", "working_tree_status": run(["git", "status", "--short"]).stdout.splitlines(),
        "scope": "Source is committed HEAD; collector and generated evidence may be untracked.",
        "commit_or_push_performed": False, "human_release_decision": "not_recorded"})
    commands = {
        "ruff": [sys.executable, "-m", "ruff", "check", ".", "--select", "S", "--output-format", "json"],
        "detect-secrets": [sys.executable, "-m", "detect_secrets", "scan", "--no-verify",
            "--exclude-files", r"(?x)^(docs/evidence/.*|ai-services/multi_agent_server/(coordination_audit|workflow_history)\.jsonl|.*\.min\.js|.*\.log)$"],
        "pip-audit": [sys.executable, "-m", "pip_audit", "-r", "requirements-audit.txt", "--format", "json", "--progress-spinner", "off"],
    }
    scans = []
    for tool, argv in commands.items():
        print(f"Capturing {tool}", flush=True)
        result = run(argv)
        report = output / "security" / f"{tool}.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(result.stdout, encoding="utf-8")
        report.with_suffix(".stderr.txt").write_text(result.stderr, encoding="utf-8")
        scans.append({"tool": tool, "exit_code": result.returncode, "captured_at": now(),
            "owner": "Ethan Ting", "source_sha": source, "command": " ".join(argv), "report": reference(report)})
        save(output / "scans.json", scans)
    refresh(output)


def refresh(output):
    source = json.loads((output / "provenance.json").read_text())["source_sha"]
    captures = api(f"/actions/runs?head_sha={source}&per_page=100")
    save(output / "workflow-runs.json", captures)
    plan = []
    for feature, workflow in WORKFLOWS.items():
        candidates = [r for r in captures["workflow_runs"] if r["path"] == workflow
            and r["head_sha"] == source and r["event"] == "push" and r["head_branch"] == "main"]
        if not candidates:
            print(f"No matching push run: {feature}", flush=True)
            continue
        row = max(candidates, key=lambda r: r["id"])
        directory = output / feature
        jobs = api(f"/actions/runs/{row['id']}/jobs?per_page=100")
        artifacts = api(f"/actions/runs/{row['id']}/artifacts?per_page=100")
        save(directory / "run.json", row)
        save(directory / "jobs.json", jobs)
        save(directory / "artifacts.json", artifacts)
        save(directory / "actions.json", {**row, "jobs": jobs["jobs"]})
        archive_marker = "goldman-release2-tests-" if feature == "customer_support" else "release2-endpoints-"
        archive = [a for a in artifacts["artifacts"] if not a["expired"]
            and archive_marker in a["name"].lower() and source in a["name"]]
        print(f"{feature}: {row['status']} / {row['conclusion']}", flush=True)
        if len(archive) == 1:
            plan.append({"feature": feature, "artifact_id": archive[0]["id"], "digest": archive[0]["digest"],
                "run_id": row["id"], "archive": str((directory / "endpoints.zip").relative_to(ROOT))})
    save(output / "download-plan.json", plan)


def assemble(output):
    provenance = json.loads((output / "provenance.json").read_text())
    config = json.loads((ROOT / "shared/agentic/review_config.json").read_text())
    scans = json.loads((output / "scans.json").read_text())
    # Retain only already documented exceptions, never grant a new acceptance.
    existing = json.loads((ROOT / "docs/evidence/release2-testing-manifest.json").read_text())
    old_audit = next(row for row in existing["security"] if row["tool"] == "pip-audit")
    scans[-1]["exceptions"] = old_audit.get("exceptions", [])
    students = []
    for item in json.loads((output / "download-plan.json").read_text()):
        directory = output / item["feature"]
        archive = ROOT / item["archive"]
        if "sha256:" + sha256(archive.read_bytes()).hexdigest() != item["digest"]:
            raise ValueError("Downloaded archive does not match GitHub's artifact digest.")
        with ZipFile(archive) as zipped:
            # Extract exactly the three bounded evidence files, not arbitrary paths.
            for name in ("test-context.json", "endpoint-functions.xml", "python-versions.txt"):
                matches = [row for row in zipped.infolist() if Path(row.filename).name == name]
                if len(matches) != 1 or matches[0].file_size > 1024 * 1024:
                    raise ValueError("Artifact has missing, duplicate or oversized evidence.")
                (directory / name).write_bytes(zipped.read(matches[0]))
        context = json.loads((directory / "test-context.json").read_text())
        students.append({"feature": item["feature"], "owner": context["owner"],
            "source_sha": provenance["source_sha"], "captured_at": now(),
            "command": f"python shared/endpoint_ci.py --feature {item['feature']} --owner '{context['owner']}'",
            "endpoints": config["testing_rules"]["expected_endpoints"][item["feature"]],
            "junit": reference(directory / "endpoint-functions.xml"),
            "context": reference(directory / "test-context.json"), "actions": reference(directory / "actions.json")})
    save(output / "testing-manifest.json", {"schema_version": 1, "kind": "testing", "owner": "Ethan Ting",
        "source_sha": provenance["source_sha"], "captured_at": now(),
        "command": "Capture native security scans and exact-main endpoint archives; verify archive digests and preserve findings.",
        "security": scans, "students": students})
    classify(output)


def classify(output):
    """Explain baseline matches separately; never remove or waive raw findings."""
    baseline_path = ROOT / ".secrets.baseline"
    baseline = json.loads(baseline_path.read_text())
    lines = baseline_path.read_text().splitlines()
    known = {name.replace("\\", "/"): rows for name, rows in baseline["results"].items()}
    scan = json.loads((output / "security/detect-secrets.json").read_text())
    classified = []
    for name, rows in scan["results"].items():
        for row in rows:
            category = "unclassified"
            if name == ".secrets.baseline" and 0 < row["line_number"] <= len(lines) and '"hashed_secret"' in lines[row["line_number"] - 1]:
                category = "baseline_hash_metadata"
            elif any(item["hashed_secret"] == row["hashed_secret"] and item["type"] == row["type"]
                     for item in known.get(name.replace("\\", "/"), [])):
                category = "existing_baseline_match"
            classified.append({"file": name, "line": row["line_number"], "type": row["type"], "category": category})
    save(output / "secret-classification.json", {"baseline": reference(baseline_path),
        "raw_scan": reference(output / "security/detect-secrets.json"), "findings": classified,
        "counts": {key: sum(row["category"] == key for row in classified)
            for key in ("baseline_hash_metadata", "existing_baseline_match", "unclassified")},
        "limitations": "Classification does not prove credentials are harmless, alter raw results or grant human risk acceptance."})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("capture", "refresh", "assemble", "classify"))
    parser.add_argument("--output", required=True, help="New repository-relative evidence directory")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT / "docs/evidence/release2-ethan-ting"):
        parser.error("Output must stay inside Ethan Ting's evidence directory.")
    {"capture": capture, "refresh": refresh, "assemble": assemble, "classify": classify}[args.action](output)


if __name__ == "__main__":
    main()
