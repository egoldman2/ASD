"""Verify read-only SSM/UI observations and prepare a new cloud review manifest."""

import argparse
import base64
from datetime import datetime
from hashlib import sha256
import importlib.util
import io
import gzip
import json
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
SOURCE = "7218c437182feb42c202abf15232b535675576e2"  # pragma: allowlist secret - Public deployed Git commit ID, not a credential.
PREVIOUS = ROOT / "docs/evidence/release2-ethan-ting/step5-cloud/main-7218c43"
COMMAND_ID = "8a74b7fe-0888-4baa-82ce-b61ad027ac7f"


def reference(path):
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path.read_bytes()).hexdigest()}


def save(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def decode_capture(text):
    matches = re.findall(r"ASD_READONLY_EVIDENCE_GZIP_BASE64=([A-Za-z0-9+/=]+)", text)
    if len(matches) != 1 or len(matches[0]) > 20000:
        raise ValueError("Missing, duplicate or oversized SSM payload.")
    compressed = base64.b64decode(matches[0], validate=True)
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        raw = stream.read(256 * 1024 + 1)
    if len(raw) > 256 * 1024:
        raise ValueError("SSM payload exceeds its uncompressed budget.")
    return json.loads(raw)


def health_fields(payload):
    samples = payload["samples"]
    if len(samples) != 3 or payload["observation_seconds"] < 120:
        raise ValueError("A measured 120-second, three-sample observation is required.")
    if any(sample["current_release"] != samples[0]["current_release"] for sample in samples):
        raise ValueError("Release changed during observation.")
    if len({sample["boot_id"] for sample in samples}) != 1:
        raise ValueError("Host rebooted during observation; counters are not comparable.")
    start = {row["service"]: row for row in samples[0]["containers"]}
    new_oom = samples[-1]["oom_kill_counter"] - samples[0]["oom_kill_counter"]
    if new_oom < 0:
        raise ValueError("OOM counter decreased unexpectedly.")
    restarts = 0
    healthy = True
    for sample in samples:
        current = {row["service"]: row for row in sample["containers"]}
        healthy &= bool(current) and current.keys() == start.keys() and sample["public_home_status"] == 200
        for name, row in current.items():
            healthy &= row["status"] == "running" and row["health"] in {"healthy", "not_configured"} and not row["oom_killed"]
            if "ai_flags" in row:
                healthy &= len(row["ai_flags"]) == 4 and all(value == "false" for value in row["ai_flags"].values())
            baseline = start.get(name)
            if baseline:
                delta = row["restart_count"] - baseline["restart_count"]
                if delta < 0:
                    healthy = False
                restarts = max(restarts, delta + int(row["id"] != baseline["id"] or row["started_at"] != baseline["started_at"]))
    return {"new_oom_events": new_oom, "unexpected_restarts": max(0, restarts),
            "containers_healthy": bool(healthy), "container_count": len(start)}


def main():
    global SOURCE, PREVIOUS, COMMAND_ID
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source", default=SOURCE)
    parser.add_argument("--previous", default=PREVIOUS.relative_to(ROOT).as_posix())
    parser.add_argument("--command-id", default=COMMAND_ID)
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT / "docs/evidence/release2-ethan-ting/step6-cloud"):
        parser.error("Output must stay in Ethan Ting's Step 6 evidence.")
    previous = (ROOT / args.previous).resolve()
    if (not re.fullmatch(r"[a-f0-9]{40}", args.source)
            or not re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", args.command_id)
            or not previous.is_relative_to(ROOT / "docs/evidence/release2-ethan-ting")):
        parser.error("Select a full source SHA, actual SSM command and confined previous capture.")
    SOURCE, PREVIOUS, COMMAND_ID = args.source, previous, args.command_id
    stdout = (output / "ssm-output.dom.txt").read_text()
    payload = decode_capture(stdout)
    original = json.loads((PREVIOUS / "native/deployment-report.json").read_text())
    result_raw = (PREVIOUS / "native/deployment-evidence/deployment-result.json").read_bytes()
    result = json.loads(result_raw)
    for field in ("source_sha", "source_sha256", "release_id", "target_instance"):
        if payload[field] != original[field]:
            raise ValueError("The observed release differs from the selected deployment.")
    if payload["source_sha"] != SOURCE or payload["application_mutation_performed"] is not False:
        raise ValueError("Invalid source or non-read-only capture.")
    verified = []
    for name in ("deployment-result.json", "public-smoke.json", "runtime.json"):
        entry = payload["captures"][name]
        raw = base64.b64decode(entry["base64"], validate=True)
        expected = entry["sha256"] if name == "deployment-result.json" else result["artifact_refs"][name]["sha256"]
        if len(raw) > 1024 * 1024 or sha256(raw).hexdigest() != entry["sha256"] or entry["sha256"] != expected:
            raise ValueError("Retrieved native bytes do not match the accepted deployment hash.")
        parsed = json.loads(raw)
        # Actions retains safe_host_evidence's projection, not the full host file.
        # Compare every exported field; only smoke/runtime have native-byte hashes
        # independently anchored by that accepted projection.
        if name == "deployment-result.json" and not all(parsed.get(key) == value for key, value in result.items()):
            raise ValueError("Full host result disagrees with the accepted Actions projection.")
        if parsed["source_sha"] != SOURCE or parsed["release_id"] != original["release_id"]:
            raise ValueError("Retrieved file identifies another release.")
        with (output / name).open("xb") as stream:
            stream.write(raw)
        verified.append(reference(output / name))
    save(output / "host-observation.json", payload)
    ec2_text = (output / "ec2-status.dom.txt").read_text()
    statuses = {}
    for label in ("System status", "Instance status", "EBS status"):
        match = re.search(r"- generic: " + re.escape(label) + r"\s+- definition:\s+- text: Check passed", ec2_text)
        statuses[label] = "ok" if match else "unverified"
    fields = health_fields(payload)
    health = {key: payload[key] for key in ("source_sha", "release_id", "target_instance", "owner", "captured_at", "command", "observation_seconds")}
    health.update({"command_id": COMMAND_ID, **fields,
        "instance_status": statuses["Instance status"], "system_status": statuses["System status"],
        "ebs_status": statuses["EBS status"],
        "status": "stable" if fields["containers_healthy"] and fields["new_oom_events"] == fields["unexpected_restarts"] == 0 and all(value == "ok" for value in statuses.values()) else "unstable",
        "native_observation": reference(output / "host-observation.json"),
        "ec2_console_observation": reference(output / "ec2-status.dom.txt"),
        "limitations": payload["limitations"] + ["EC2 status is a console observation, not a continuously measured API status series."]})
    save(output / "health.json", health)
    manifest = json.loads((PREVIOUS / "cloud-manifest.json").read_text())
    manifest.update({"captured_at": datetime.now(ZoneInfo("Australia/Sydney")).isoformat(),
        "owner": "Ethan Ting", "command": "Read-only SSM retrieval of accepted same-SHA native records; measured 120-second host observation and EC2 console status; human approval remains absent.",
        "public_smoke": reference(output / "public-smoke.json"),
        "runtime": reference(output / "runtime.json"), "health": reference(output / "health.json")})
    save(output / "cloud-manifest.json", manifest)
    validate(output, verified, health)


def validate(output, verified, health):
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "ai-services"))
    spec = importlib.util.spec_from_file_location("cloud_report_validation", ROOT / "ai-services/report_validation.py")
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    required = json.loads((ROOT / "shared/agentic/review_config.json").read_text())["cloud_deployment_rules"]["required_workflows"]
    validation = validator.collect_cloud_evidence(ROOT, reference(output / "cloud-manifest.json")["path"], SOURCE, required)
    save(output / "pre-review-validation.json", validation)
    save(output / "retrieval-verification.json", {"source_sha": SOURCE, "command_id": COMMAND_ID,
        "native_files": verified, "health": reference(output / "health.json"),
        "host_result_comparison": "All accepted Actions projection fields match; full host file has additional provenance fields and different bytes.",
        "observer_source": reference(output / "executed-observer.py"),
        "assembler_source": reference(output / "executed-assembler.py"),
        "technical_status": validation["technical_status"], "review_status": validation["status"],
        "human_release_recorded": False, "customer_data_changed": False,
        "committed_or_pushed": False})
    print(json.dumps({"technical_status": validation["technical_status"], "status": validation["status"],
        "issues": validation["issues"], "health": health["status"], "verified_native_files": len(verified)}))


if __name__ == "__main__":
    main()
