"""Retain a read-only loyalty review with before/after workflow/log checks."""

import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-services"))
import agentic_loop as runner


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def fingerprints(config):
    result = {}
    for relative in config["multi_agent_rules"]["log_files"].values():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ValueError("Evidence logs must be existing project-local files.")
        result[relative] = sha256(path.read_bytes()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="New repository-relative evidence directory")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT / "docs/evidence/release2-ethan-ting") or output.exists():
        parser.error("Choose a new directory inside Ethan Ting's evidence folder.")
    config, _ = runner.load_feature("student-Ethan Ting")
    output.mkdir(parents=True)
    source_paths = config["multi-agent_files"] + [
        "student-Ethan Ting/agentic/review_config.json",
        "student-Ethan Ting/agentic/review_prompt.txt",
        "student-Ethan Ting/agentic/multi_agent_prompt.txt",
        "student-Ethan Ting/scripts/review_loyalty_multi_agent.py",
    ]
    git = shutil.which("git")
    if not git:
        raise RuntimeError("Git is required to record source provenance.")
    source = subprocess.run([git, "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()  # noqa: S603 - Resolved executable and fixed read-only Git argv, no shell.
    changed = subprocess.run([git, "status", "--short"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()  # noqa: S603 - Resolved executable and fixed read-only Git argv, no shell.
    provenance = {"base_source_sha": source, "captured_at": datetime.now(ZoneInfo("Australia/Sydney")).isoformat(),
        "owner": "Ethan Ting", "review_model": runner.OLLAMA_MODEL, "working_tree_status": changed,
        "source_files": [{"path": name, "sha256": sha256((ROOT / name).read_bytes()).hexdigest()} for name in source_paths],
        "limitations": ["Configuration, prompt and tests can be uncommitted; base SHA alone does not identify the reviewed working tree.",
            "The selected workflow is historical; a live GET is not a new three-agent execution.",
            "A prior automated UI test decision does not establish new student participation or a release approval."]}
    save(output / "provenance.json", provenance)
    logs_before = fingerprints(config)
    before = runner.collect_multi_agent_evidence(config)
    save(output / "before.json", before)
    error = None
    result = None
    try:
        result = runner.run_agentic_loop("student-Ethan Ting", "multi-agent")
    except runner.AgenticLoopError as exc:
        error = str(exc)
        print(f"Review failed: {error}", flush=True)
    after = runner.collect_multi_agent_evidence(config)
    save(output / "after.json", after)
    static = after["verified_checks"]
    runtime = after["runtime"]
    checks = {key: static.get(key) is True for key in (
        "all_required_agents_wired", "agent_order_in_coordinator", "all_group_features_supported",
        "all_required_endpoints_registered", "human_review_gate_present", "multi_agent_server_not_in_compose")}
    checks.update({key: runtime.get(key) is True for key in (
        "scope_verified", "three_agents_completed", "evidence_ids_verified", "history_verified",
        "audit_chain_verified", "human_review_recorded", "review_evidence_complete")})
    checks.update({"all_source_checks": bool(static["source_checks"]) and all(static["source_checks"].values()),
        "all_files_present": not static["missing_files"], "logs_unchanged": logs_before == fingerprints(config),
        "workflow_observation_unchanged": before["runtime"] == runtime})
    validation = {"captured_at": datetime.now(ZoneInfo("Australia/Sydney")).isoformat(), "base_source_sha": source,
        "checks": checks, "structural_evidence_complete": all(checks.values()) and result is not None,
        "model_review_error": error, "student_release_decision": "not_recorded",
        "factual_accuracy_guaranteed": False, "new_workflow_or_decision_created": False,
        "historical_decision_origin": "Automated local UI validation; not a new student decision.",
        "review_file": str(Path(result["output_path"]).relative_to(ROOT)) if result and result["output_path"] else None}
    save(output / "validation.json", validation)
    print(json.dumps(validation, indent=2), flush=True)
    return 0 if validation["structural_evidence_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
