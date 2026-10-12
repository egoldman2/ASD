"""Upload a cloud bundle and deploy it through SSM; uses CLI/OIDC credentials."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import tarfile
import tempfile
import time

from prepare import prepare


REGION = "ap-southeast-2"


def aws(*arguments):
    result = subprocess.run(["aws", *arguments, "--region", REGION, "--output", "json"], check=True, capture_output=True, text=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


def outputs(stack):
    result = aws("cloudformation", "describe-stacks", "--stack-name", stack)
    return {entry["OutputKey"]: entry["OutputValue"] for entry in result["Stacks"][0]["Outputs"]}


def deploy(stack, release_id):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}", release_id):
        raise ValueError("Release ID must be a short alphanumeric identifier.")
    resources = outputs(stack)
    with tempfile.TemporaryDirectory(prefix="asd-cloud-release-") as temporary:
        directory = Path(temporary)
        context = prepare(directory / "source")
        bundle = directory / "source.tar.gz"
        with tarfile.open(bundle, "w:gz") as archive:
            for path in sorted(context.rglob("*")):
                if path.is_file():
                    archive.add(path, arcname=path.relative_to(context), recursive=False)
        digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
        key = f"releases/{release_id}-{digest[:12]}.tar.gz"
        subprocess.run([
            "aws", "s3", "cp", str(bundle), f"s3://{resources['ReleaseBucket']}/{key}",
            "--region", REGION, "--sse", "AES256", "--only-show-errors",
        ], check=True)
    remote = f"/srv/asd/releases/{release_id}-{digest[:12]}"
    commands = [
        "set -euo pipefail",
        # An instance can register with SSM before cloud-init finishes.
        "for attempt in $(seq 1 120); do test -f /srv/asd/bootstrap-ready && break; sleep 2; done",
        "test -f /srv/asd/bootstrap-ready",
        f"mkdir -p {shlex.quote(remote)}",
        "aws s3 cp " + shlex.quote(f"s3://{resources['ReleaseBucket']}/{key}") + " " + shlex.quote(remote + "/source.tar.gz") + f" --region {REGION} --only-show-errors",
        f"echo '{digest}  {remote}/source.tar.gz' | sha256sum --check",
        f"tar --extract --gzip --file {shlex.quote(remote + '/source.tar.gz')} --directory {shlex.quote(remote)} --no-same-owner",
        "bash " + shlex.quote(remote + "/cloud/install.sh") + " " + " ".join(shlex.quote(value) for value in (
            release_id, resources["PublicUrl"], resources["OriginSecretArn"], resources["DemoPasswordArn"], REGION,
        )),
    ]
    response = aws(
        "ssm", "send-command", "--document-name", "AWS-RunShellScript",
        "--instance-ids", resources["InstanceId"],
        "--parameters", json.dumps({"commands": ["bash -lc " + shlex.quote("\n".join(commands))], "executionTimeout": ["3600"]}),
        "--comment", f"ASD release {release_id}",
    )
    command_id = response["Command"]["CommandId"]
    print(f"Deployment command: {command_id}", flush=True)
    for attempt in range(360):
        time.sleep(10)
        try:
            result = aws("ssm", "get-command-invocation", "--command-id", command_id, "--instance-id", resources["InstanceId"])
        except subprocess.CalledProcessError as error:
            # SSM can acknowledge a command before its invocation is readable.
            if "InvocationDoesNotExist" in (error.stderr or ""):
                continue
            raise
        status = result["Status"]
        if attempt % 6 == 0:
            print(f"Deployment status: {status}", flush=True)
        if status == "Success":
            print(result.get("StandardOutputContent", "")[-3500:])
            return {"release_id": release_id, "source_sha256": digest, "command_id": command_id, "status": status, "public_url": resources["PublicUrl"]}
        if status in {"Failed", "Cancelled", "TimedOut", "Cancelling"}:
            print(result.get("StandardOutputContent", "")[-3500:])
            print(result.get("StandardErrorContent", "")[-3500:])
            raise RuntimeError(f"Deployment ended with {status}.")
    raise TimeoutError("Deployment has not completed within one hour; inspect its SSM command before retrying.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack", default="asd-release2")
    parser.add_argument("--release", default=datetime.now(timezone.utc).strftime("manual-%Y%m%d-%H%M%S"))
    parser.add_argument("--report", type=Path)
    arguments = parser.parse_args()
    try:
        report = deploy(arguments.stack, arguments.release)
        if arguments.report:
            arguments.report.parent.mkdir(parents=True, exist_ok=True)
            arguments.report.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.stderr or "AWS command failed.") from None
