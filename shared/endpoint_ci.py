"""Run the two allocated endpoint tests and retain their actual Actions context."""

import argparse
from datetime import datetime, timezone
from importlib.metadata import distributions
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "shared/agentic/review_config.json"
FLAGS = ("AI_MODE_ENABLED", "MCP_ENABLED", "RAG_ENABLED", "MULTI_AGENT_ENABLED")
LIVE_OPT_INS = (
    "RUN_LIVE_AI", "RUN_LIVE_MCP_AI", "RUN_LIVE_RAG_AI", "RUN_LIVE_VALIDATION",
    "RUN_LIVE_RELEASE1_VALIDATION", "RUN_LIVE_MULTI_AGENT", "RUN_NGINX_PROXY_CHECK",
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature", required=True)
    parser.add_argument("--owner", required=True)
    args = parser.parse_args(argv)
    mapping = json.loads(CONFIG.read_text())["testing_rules"]["expected_endpoints"]
    endpoints = mapping.get(args.feature, [])
    if len(endpoints) != 2 or not args.owner.strip():
        parser.error("A feature owner and exactly two allocated endpoint functions are required")
    nodes = [endpoint["test_node_id"] for endpoint in endpoints]
    if len(set(nodes)) != 2 or any(
        not re.fullmatch(r"student-[^/]+/tests/[A-Za-z0-9_]+\.py::test_[A-Za-z0-9_]+", node)
        or not (ROOT / node.split("::")[0]).is_file()
        or not (ROOT / node.split("::")[0]).resolve().is_relative_to(ROOT)
        for node in nodes
    ):
        parser.error("Endpoint selections must name two existing repository test functions")
    flags = {name: os.getenv(name) for name in FLAGS}
    opt_ins = {name: os.getenv(name) for name in LIVE_OPT_INS}
    if any(value != "false" for value in flags.values()) or any(value != "0" for value in opt_ins.values()):
        parser.error("CI requires disabled AI flags and zero live opt-ins")
    source = os.getenv("GITHUB_SHA", "")
    repository = os.environ["GITHUB_REPOSITORY"]
    workflow = os.environ["GITHUB_WORKFLOW_REF"].split("@", 1)[0].removeprefix(repository + "/")
    if not re.fullmatch(r"[a-f0-9]{40}", source) or not re.fullmatch(r"\.github/workflows/[A-Za-z0-9_-]+\.ya?ml", workflow):
        parser.error("Actual Actions source and workflow metadata are required")
    output = Path("artifacts")
    output.mkdir(exist_ok=True)
    report = {
        "owner": args.owner, "feature": args.feature, "source_sha": source,
        "event": os.environ["GITHUB_EVENT_NAME"], "ref": os.environ["GITHUB_REF"],
        "run_id": os.environ["GITHUB_RUN_ID"], "run_attempt": os.environ["GITHUB_RUN_ATTEMPT"],
        "run_url": f"https://github.com/{repository}/actions/runs/{os.environ['GITHUB_RUN_ID']}",
        "captured_at": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
        "workflow": workflow, "ai_flags": flags, "live_opt_ins": opt_ins,
        "endpoint_junit": "endpoint-functions.xml", "endpoint_functions": endpoints,
    }
    (output / "test-context.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "python-versions.txt").write_text("\n".join(sorted(
        f"{distribution.metadata['Name']}=={distribution.version}" for distribution in distributions()
    )) + "\n")
    command = [sys.executable, "-m", "pytest", *nodes, "-q", f"--junitxml={(output / 'endpoint-functions.xml').resolve()}"]
    return subprocess.run(command, cwd=ROOT, check=False).returncode  # noqa: S603 - Fixed interpreter and validated repository test nodes; no shell.


if __name__ == "__main__":
    sys.exit(main())
