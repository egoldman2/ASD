"""Retain actual local security output, without committing or altering the index."""

from datetime import datetime
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs/evidence/release2-ethan-ting/step2"
OWNED = ["student-Ethan Ting", "ai-services/mcp_server/tests/test_ethan_ting_customer_tools.py"]


def run(command):
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)  # noqa: S603 - Fixed tool argv and repository-owned paths below; no shell or user-supplied command.


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source = run(["git", "rev-parse", "HEAD"]).stdout.strip()
    files = run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", *OWNED]).stdout.splitlines()
    files = sorted(set(files))
    manifest = {"owner": "Ethan Ting", "source_sha": source,
        "captured_at": datetime.now(ZoneInfo("Australia/Sydney")).isoformat(),
        "scope": "Local working tree, not a new commit or a GitHub Actions run",
        "commit_executed": False,
        "tools": {name: version(name) for name in ("pre-commit", "ruff", "detect-secrets", "pip-audit")},
        "hook_installed": (ROOT / ".git/hooks/pre-commit").is_file(),
        "hook_sha256": sha256((ROOT / ".git/hooks/pre-commit").read_bytes()).hexdigest(),
        "configuration_files": [{"path": name, "sha256": sha256((ROOT / name).read_bytes()).hexdigest()}
            for name in (".pre-commit-config.yaml", ".secrets.baseline", "requirements-audit.txt")],
        "working_tree_status": run(["git", "status", "--short"]).stdout.splitlines(),
        "source_files": [{"path": name, "sha256": sha256((ROOT / name).read_bytes()).hexdigest()} for name in files],
        "commands": []}
    commands = [
        ("ruff-feature", [sys.executable, "-m", "ruff", "check", "--select", "S", *OWNED, "--output-format", "json"]),
        ("ruff-whole-repository", [sys.executable, "-m", "ruff", "check", "--select", "S", ".", "--output-format", "json"]),
        ("detect-secrets-feature", [sys.executable, "-m", "detect_secrets", "scan", "--all-files", *OWNED]),
        ("pip-audit-unfiltered", [sys.executable, "-m", "pip_audit", "-r", "requirements-audit.txt", "--format", "json", "--progress-spinner", "off"]),
        ("pre-commit-owned-files", [sys.executable, "-m", "pre_commit", "run", "--hook-stage", "pre-commit", "--files", *files]),
    ]
    for label, command in commands:
        print(f"Running {label}...", flush=True)
        result = run(command)
        stdout = OUTPUT / f"{label}.stdout.txt"
        stderr = OUTPUT / f"{label}.stderr.txt"
        stdout.write_text(result.stdout)
        stderr.write_text(result.stderr)
        entry = {"name": label, "command": command, "exit_code": result.returncode,
            "stdout": {"path": str(stdout.relative_to(ROOT)), "sha256": sha256(stdout.read_bytes()).hexdigest()},
            "stderr": {"path": str(stderr.relative_to(ROOT)), "sha256": sha256(stderr.read_bytes()).hexdigest()}}
        manifest["commands"].append(entry)
        (OUTPUT / "capture.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"{label}: exit {result.returncode}", flush=True)
    scan = json.loads((OUTPUT / "detect-secrets-feature.stdout.txt").read_text())
    baseline = json.loads((ROOT / ".secrets.baseline").read_text())
    known = {name.replace("\\", "/"): rows for name, rows in baseline["results"].items()}
    reviewed = []
    for name, rows in scan["results"].items():
        for finding in rows:
            reviewed.append({"file": name, "line": finding["line_number"], "type": finding["type"],
                "matches_existing_baseline": any(row["hashed_secret"] == finding["hashed_secret"]
                    and row["type"] == finding["type"] for row in known.get(name.replace("\\", "/"), []))})
    (OUTPUT / "secret-digest-review.json").write_text(json.dumps({"baseline_changed": False,
        "finding_count": len(reviewed), "unclassified_count": sum(not row["matches_existing_baseline"] for row in reviewed),
        "findings": reviewed}, indent=2) + "\n")
    print(f"Actual output saved in {OUTPUT}")
    return 0 if manifest["commands"][0]["exit_code"] == 0 and manifest["commands"][-1]["exit_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
