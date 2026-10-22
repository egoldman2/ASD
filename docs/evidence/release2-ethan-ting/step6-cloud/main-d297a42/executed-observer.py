"""Read-only host capture for the selected release; run through authorised SSM.

No installation, credentials, customer records, CRUD, or container changes.
Only approved deployment JSON files and allowlisted health fields are exported.
"""

import argparse
import base64
from datetime import datetime
import gzip
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
from urllib.request import urlopen
from zoneinfo import ZoneInfo


SOURCE = "7218c437182feb42c202abf15232b535675576e2"  # pragma: allowlist secret - Public deployed Git commit ID, not a credential.
RELEASE = SOURCE + "-1"
DIRECTORY = Path("/srv/asd/releases/" + RELEASE + "-384b8f0652e8")
FLAGS = ("AI_MODE_ENABLED", "MCP_ENABLED", "RAG_ENABLED", "MULTI_AGENT_ENABLED")
APIS = {"shared-backend", "ethan-backend", "inventory-backend", "customer-support-backend"}


def now():
    return datetime.now(ZoneInfo("Australia/Sydney")).isoformat()


def command(*args):
    return subprocess.check_output(args, text=True, timeout=30)  # noqa: S603 - Fixed Docker observation commands below; no shell.


def selected_json(name):
    path = DIRECTORY / name
    if path.is_symlink() or path.stat().st_size > 1024 * 1024:
        raise ValueError("Invalid evidence file.")
    raw = path.read_bytes()
    value = json.loads(raw)
    if value.get("source_sha") != SOURCE or value.get("release_id") != RELEASE:
        raise ValueError("Host evidence identifies another release.")
    return raw, value


def snapshot():
    current = str(Path("/srv/asd/current").resolve())
    if current != str(DIRECTORY):
        raise ValueError("Current host release differs from the selected source.")
    ids = command("docker", "ps", "-q", "--filter", "label=com.docker.compose.project=asd-cloud").split()
    if not ids or any(len(identifier) != 12 or not all(c in "0123456789abcdef" for c in identifier) for identifier in ids):
        raise ValueError("Missing or invalid cloud containers.")
    containers = []
    for identifier in ids:
        row, = json.loads(command("docker", "inspect", identifier))
        service = row["Config"]["Labels"]["com.docker.compose.service"]
        state = row["State"]
        allowed = {"id": identifier, "service": service, "status": state["Status"],
            "health": state.get("Health", {}).get("Status", "not_configured"),
            "restart_count": row["RestartCount"], "started_at": state["StartedAt"],
            "oom_killed": state["OOMKilled"]}
        if service in APIS:
            env = dict(item.split("=", 1) for item in row["Config"]["Env"] if "=" in item)
            allowed["ai_flags"] = {key: env.get(key) for key in FLAGS}
        containers.append(allowed)
    vm = dict(line.split() for line in Path("/proc/vmstat").read_text().splitlines())
    mem = dict((parts[0].rstrip(":"), int(parts[1])) for line in Path("/proc/meminfo").read_text().splitlines() if len(parts := line.split()) >= 2)
    disk = shutil.disk_usage("/srv/asd")
    with urlopen("https://dww8d9hiqp0ce.cloudfront.net/", timeout=10) as response:  # noqa: S310 - Fixed public HTTPS origin; GET only.
        public_status = response.status
    return {"captured_at": now(), "current_release": current,
        "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "oom_kill_counter": int(vm["oom_kill"]), "containers": sorted(containers, key=lambda row: row["service"]),
        "load_average": Path("/proc/loadavg").read_text().split()[:3],
        "memory_available_kib": mem["MemAvailable"], "memory_total_kib": mem["MemTotal"],
        "data_disk_free_bytes": disk.free, "data_disk_total_bytes": disk.total,
        "public_home_status": public_status}


def main():
    global SOURCE, RELEASE, DIRECTORY
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=SOURCE)
    parser.add_argument("--release-directory", default=str(DIRECTORY))
    args = parser.parse_args()
    directory = Path(args.release_directory)
    if (not re.fullmatch(r"[a-f0-9]{40}", args.source)
            or directory.parent != Path("/srv/asd/releases")
            or not re.fullmatch(re.escape(args.source) + r"-[1-9][0-9]*-[a-f0-9]{12}", directory.name)):
        raise ValueError("Select an explicit committed source and its bounded release directory.")
    SOURCE, DIRECTORY = args.source, directory
    RELEASE = directory.name.rsplit("-", 1)[0]
    result_raw, result = selected_json("deployment-result.json")
    captures = {"deployment-result.json": {"sha256": sha256(result_raw).hexdigest(),
        "base64": base64.b64encode(result_raw).decode()}}
    for name in ("public-smoke.json", "runtime.json"):
        raw, _ = selected_json(name)
        digest = sha256(raw).hexdigest()
        if result["artifact_refs"][name]["sha256"] != digest:
            raise ValueError("Native evidence changed since accepted deployment.")
        captures[name] = {"sha256": digest, "base64": base64.b64encode(raw).decode()}
    start = time.monotonic()
    samples = []
    for offset in (0, 60, 120):
        remaining = start + offset - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
        samples.append(snapshot())
    payload = {"source_sha": SOURCE, "release_id": RELEASE,
        "target_instance": result["target_instance"], "source_sha256": result["source_sha256"],
        "owner": "Ethan Ting", "captured_at": now(),
        "command": "SSM read-only evidence export and Docker/proc/public-home observations at 0, 60 and 120 seconds",
        "observation_seconds": int(time.monotonic() - start),
        "customer_data_read": False, "application_mutation_performed": False,
        "captures": captures, "samples": samples,
        "limitations": ["Light public-home GETs only, not a production capacity test.",
            "EC2 instance/system status must be separately observed, never assumed."]}
    compressed = base64.b64encode(gzip.compress(json.dumps(payload, separators=(",", ":")).encode(), mtime=0)).decode()
    if len(compressed) > 20000:
        raise ValueError("Export exceeds the console's safe output budget.")
    print("ASD_READONLY_EVIDENCE_GZIP_BASE64=" + compressed)


if __name__ == "__main__":
    main()
