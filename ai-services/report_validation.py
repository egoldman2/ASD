"""Read-only validation of captured Release 2 reports; prose cannot pass a gate."""

from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from mcp_validation import public_evidence


TOOLS = {"ruff", "detect-secrets", "pip-audit"}
FEATURES = {
    "product_catalogue",
    "inventory",
    "customer_loyalty",
    "order_returns",
    "customer_support",
}
FEATURE_DIRECTORIES = {
    "product_catalogue": "student-Chufeng",
    "inventory": "student-Ryan_Nolan",
    "customer_loyalty": "student-Ethan Ting",
    "order_returns": "student-Howard",
    "customer_support": "student-Ethan Goldman",
}
FLAGS = {"AI_MODE_ENABLED", "MCP_ENABLED", "RAG_ENABLED", "MULTI_AGENT_ENABLED"}
LIVE_OPT_INS = {
    "RUN_LIVE_AI",
    "RUN_LIVE_MCP_AI",
    "RUN_LIVE_RAG_AI",
    "RUN_LIVE_VALIDATION",
    "RUN_LIVE_RELEASE1_VALIDATION",
    "RUN_LIVE_MULTI_AGENT",
    "RUN_NGINX_PROXY_CHECK",
}


def _require(condition):
    if not condition:
        raise ValueError("Evidence does not satisfy the report contract.")


def _text(value, maximum=200):
    return isinstance(value, str) and 0 < len(value.strip()) <= maximum


def _timestamp(value):
    _require(_text(value, 80))
    _require(
        datetime.fromisoformat(value.replace("Z", "+00:00")).utcoffset() is not None
    )


class EvidenceInputs:
    """Confine and hash bounded files before parsing any untrusted report."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.files = []
        self.total_bytes = 0

    def read(self, reference, *, limit=1024 * 1024):
        _require(isinstance(reference, dict) and _text(reference.get("path"), 300))
        relative = Path(reference["path"])
        path = (self.root / relative).resolve()
        _require(
            not relative.is_absolute()
            and path.is_relative_to(self.root)
            and path.is_file()
        )
        _require(len(self.files) < 40)
        with path.open("rb") as stream:
            raw = stream.read(limit + 1)
        self.total_bytes += len(raw)
        _require(len(raw) <= limit and self.total_bytes <= 8 * 1024 * 1024)
        digest = sha256(raw).hexdigest()
        _require(reference.get("sha256", digest) == digest)
        self.files.append({"path": str(relative), "sha256": digest, "bytes": len(raw)})
        return raw

    def json(self, reference):
        _require(
            isinstance(reference, dict)
            and re.fullmatch(r"[a-f0-9]{64}", str(reference.get("sha256", "")))
        )
        return json.loads(self.read(reference))


def _capture(entry, source_sha):
    _require(isinstance(entry, dict) and entry.get("source_sha") == source_sha)
    _require(_text(entry.get("owner")) and _text(entry.get("command"), 1000))
    _timestamp(entry.get("captured_at"))


def _scan(entry, inputs, source_sha, accepted_advisories):
    _capture(entry, source_sha)
    tool = entry.get("tool")
    _require(tool in TOOLS and type(entry.get("exit_code")) is int)
    report = inputs.json(entry.get("report"))
    exceptions = []
    rejected_exceptions = 0
    if tool == "ruff":
        _require(isinstance(report, list))
        _require(
            all(isinstance(row, dict) and _text(row.get("code")) for row in report)
        )
        findings = len(report)
        execution_ok = entry["exit_code"] == (1 if findings else 0)
    elif tool == "detect-secrets":
        _require(isinstance(report, dict) and _text(report.get("version")))
        _require(
            isinstance(report.get("plugins_used"), list)
            and bool(report["plugins_used"])
        )
        rows = report.get("results")
        _require(
            isinstance(rows, dict)
            and all(isinstance(items, list) for items in rows.values())
        )
        _require(
            all(
                isinstance(item, dict) and _text(item.get("type"))
                for items in rows.values()
                for item in items
            )
        )
        findings = sum(len(items) for items in rows.values())
        execution_ok = entry["exit_code"] == 0
    else:
        _require(
            isinstance(report, dict)
            and isinstance(report.get("dependencies"), list)
            and bool(report["dependencies"])
        )
        advisories = set()
        for dependency in report["dependencies"]:
            _require(
                isinstance(dependency, dict)
                and _text(dependency.get("name"))
                and _text(dependency.get("version"))
            )
            _require(
                isinstance(dependency.get("vulns"), list)
                and not dependency.get("skip_reason")
            )
            for finding in dependency["vulns"]:
                _require(isinstance(finding, dict) and _text(finding.get("id")))
                advisories.add(finding["id"])
        findings = len(advisories)
        execution_ok = entry["exit_code"] == (1 if findings else 0)
        for exception in entry.get("exceptions", []):
            try:
                _require(
                    isinstance(exception, dict)
                    and exception.get("id") in accepted_advisories
                )
                _require(
                    exception["id"] in advisories
                    and exception["id"] not in exceptions
                    and _text(exception.get("reason"), 1000)
                )
                record = exception.get("record")
                _require(
                    isinstance(record, dict)
                    and re.fullmatch(r"[a-f0-9]{64}", str(record.get("sha256", "")))
                )
                _require(bool(inputs.read(record).strip()))
                exceptions.append(exception["id"])
            except (ValueError, TypeError, OSError):
                rejected_exceptions += 1
        findings -= len(exceptions)
    return {
        "tool": tool,
        "execution_ok": execution_ok,
        "exit_code": entry["exit_code"],
        "finding_count": findings + len(exceptions),
        "unexcepted_findings": findings,
        "accepted_advisories": exceptions,
        "rejected_exceptions": rejected_exceptions,
        "status": "fail"
        if not execution_ok or findings or rejected_exceptions
        else "pass_with_exceptions"
        if exceptions
        else "pass",
    }


def _junit(raw, endpoints):
    root = ElementTree.fromstring(
        raw, forbid_dtd=True, forbid_entities=True, forbid_external=True
    )
    _require(root.tag in {"testsuites", "testsuite"})
    _require(sum(1 for _ in root.iter()) <= 20000)
    suites = [root] if root.tag == "testsuite" else list(root)
    _require(all(suite.tag == "testsuite" for suite in suites))
    _require(len(list(root.iter("testsuite"))) == len(suites))
    _require(
        all(
            child.tag in {"testcase", "properties", "system-out", "system-err"}
            for suite in suites
            for child in suite
        )
    )
    cases = list(root.iter("testcase"))
    _require(bool(cases))
    _require(
        len(cases)
        == sum(child.tag == "testcase" for suite in suites for child in suite)
    )
    for suite in (
        node for node in root.iter() if node.tag in {"testsuite", "testsuites"}
    ):
        counts = {
            "tests": len(list(suite.iter("testcase"))),
            "failures": len(list(suite.iter("failure"))),
            "errors": len(list(suite.iter("error"))),
            "skipped": len(list(suite.iter("skipped"))),
        }
        for name, count in counts.items():
            if suite.get(name) is not None:
                _require(suite.get(name).isdigit() and int(suite.get(name)) == count)
    indexed = {}
    for case in cases:
        _require(_text(case.get("classname"), 300) and _text(case.get("name"), 300))
        node = case.get("classname").replace(".", "/") + ".py::" + case.get("name")
        indexed.setdefault(node, []).append(case)
    results = []
    for endpoint in endpoints:
        matched = indexed.get(endpoint["test_node_id"], [])
        passed = len(matched) == 1 and not any(
            matched[0].find(tag) is not None for tag in ("failure", "error", "skipped")
        )
        results.append(
            {
                "function": endpoint["function"],
                "test_node_id": endpoint["test_node_id"],
                "passed": passed,
            }
        )
    return {
        "test_count": len(cases),
        "failures": len(list(root.iter("failure"))),
        "errors": len(list(root.iter("error"))),
        "skipped": len(list(root.iter("skipped"))),
        "endpoints": results,
    }


def _student(entry, inputs, source_sha, expected_endpoints):
    _capture(entry, source_sha)
    feature, owner = entry.get("feature"), entry["owner"]
    _require(feature in FEATURES)
    endpoints = entry.get("endpoints")
    _require(isinstance(endpoints, list) and len(endpoints) == 2)
    for endpoint in endpoints:
        _require(
            isinstance(endpoint, dict)
            and all(
                _text(endpoint.get(key), 300)
                for key in ("function", "path", "test_node_id")
            )
        )
        _require(endpoint.get("method") in {"GET", "POST", "PUT", "PATCH", "DELETE"})
        _require(
            endpoint["test_node_id"].startswith(
                FEATURE_DIRECTORIES[feature] + "/tests/"
            )
        )
    _require(
        len({item["function"] for item in endpoints})
        == len({item["test_node_id"] for item in endpoints})
        == 2
    )
    if feature in expected_endpoints:
        _require(endpoints == expected_endpoints[feature])
    context, actions = (
        inputs.json(entry.get("context")),
        inputs.json(entry.get("actions")),
    )
    _require(isinstance(context, dict) and isinstance(actions, dict))
    _require(context.get("source_sha") == actions.get("head_sha") == source_sha)
    _require(context.get("owner") == owner and context.get("feature") == feature)
    _require(
        str(context.get("run_id")) == str(actions.get("id"))
        and type(actions.get("id")) is int
        and actions["id"] > 0
    )
    run_url = f"https://github.com/egoldman2/ASD/actions/runs/{actions['id']}"
    _require(context.get("run_url") == actions.get("html_url") == run_url)
    _require(context.get("event") == actions.get("event") == "push")
    _require(context.get("ref") == "refs/heads/" + str(actions.get("head_branch")))
    _require(
        context.get("workflow") == actions.get("path")
        and re.fullmatch(
            r"\.github/workflows/[A-Za-z0-9_-]+\.ya?ml", str(actions.get("path"))
        )
    )
    _require(context.get("endpoint_functions") == endpoints)
    flags = context.get("ai_flags", {})
    opt_ins = context.get("live_opt_ins", {})
    _require(
        isinstance(flags, dict)
        and FLAGS <= flags.keys()
        and all(flags[name] == "false" for name in FLAGS)
    )
    _require(
        isinstance(opt_ins, dict)
        and LIVE_OPT_INS <= opt_ins.keys()
        and all(value == "0" for value in opt_ins.values())
    )
    _timestamp(context.get("captured_at"))
    junit_ref = entry.get("junit")
    _require(
        isinstance(junit_ref, dict)
        and re.fullmatch(r"[a-f0-9]{64}", str(junit_ref.get("sha256", "")))
    )
    _require(Path(junit_ref["path"]).name == context.get("endpoint_junit"))
    junit = _junit(inputs.read(junit_ref), endpoints)
    jobs = actions.get("jobs", [])
    _require(
        isinstance(jobs, list)
        and 0 < len(jobs) <= 30
        and all(isinstance(job, dict) for job in jobs)
    )
    ci_passed = (
        actions.get("status") == "completed"
        and actions.get("conclusion") == "success"
        and all(
            job.get("status") == "completed" and job.get("conclusion") == "success"
            for job in jobs
        )
    )
    return {
        "feature": feature,
        "owner": public_evidence(owner),
        "run_url": run_url,
        "ci_passed": ci_passed,
        **junit,
        "status": "pass"
        if ci_passed
        and not junit["failures"]
        and not junit["errors"]
        and all(item["passed"] for item in junit["endpoints"])
        else "fail",
    }


def collect_testing_evidence(
    root,
    manifest_path,
    source_sha,
    required_features,
    *,
    expected_endpoints=None,
    accepted_advisories=(),
):
    """Validate structured captures; never execute commands or contact services."""
    _require(isinstance(source_sha, str) and re.fullmatch(r"[a-f0-9]{40}", source_sha))
    _require(
        isinstance(required_features, list)
        and bool(required_features)
        and set(required_features) <= FEATURES
    )
    inputs = EvidenceInputs(root)
    evidence = {
        "kind": "testing",
        "read_only": True,
        "source_sha": source_sha,
        "required_features": required_features,
        "status": "incomplete",
        "security": [],
        "students": [],
        "issues": [],
        "limitations": [
            "Supplied Actions/scan captures are parsed offline; their remote authenticity is not independently verified.",
            "Recorded findings/exceptions and skipped tests remain visible; prose cannot change gate results.",
        ],
    }
    try:
        manifest = json.loads(inputs.read({"path": manifest_path}, limit=128 * 1024))
        _require(
            isinstance(manifest, dict)
            and manifest.get("schema_version") == 1
            and manifest.get("kind") == "testing"
        )
        _require(
            manifest.get("source_sha") == source_sha and _text(manifest.get("owner"))
        )
        _timestamp(manifest.get("captured_at"))
        scans, students = manifest.get("security"), manifest.get("students")
        _require(
            isinstance(scans, list)
            and len(scans) <= 3
            and isinstance(students, list)
            and len(students) <= 5
        )
        for entry in scans:
            try:
                evidence["security"].append(
                    _scan(entry, inputs, source_sha, accepted_advisories)
                )
            except (ValueError, TypeError, KeyError, OSError, RecursionError):
                evidence["issues"].append("invalid_security_capture")
        for entry in students:
            try:
                evidence["students"].append(
                    _student(entry, inputs, source_sha, expected_endpoints or {})
                )
            except (
                ValueError,
                TypeError,
                KeyError,
                OSError,
                RecursionError,
                ElementTree.ParseError,
                DefusedXmlException,
            ):
                evidence["issues"].append("invalid_student_capture")
        if {entry["tool"] for entry in evidence["security"]} != TOOLS or len(
            evidence["security"]
        ) != 3:
            evidence["issues"].append("missing_or_duplicate_security_tool")
        features = [entry["feature"] for entry in evidence["students"]]
        owners = [entry["owner"] for entry in evidence["students"]]
        if set(features) != set(required_features) or len(features) != len(
            set(features)
        ):
            evidence["issues"].append("missing_or_duplicate_student")
        if len(owners) != len(set(owners)):
            evidence["issues"].append("duplicate_student_owner")
        results = evidence["security"] + evidence["students"]
        evidence["status"] = (
            "fail"
            if any(item["status"] == "fail" for item in results)
            else "incomplete"
            if evidence["issues"]
            else "pass_with_exceptions"
            if any(item["status"] == "pass_with_exceptions" for item in results)
            else "pass"
        )
    except (ValueError, TypeError, KeyError, OSError, RecursionError):
        evidence["issues"].append("invalid_testing_manifest")
    evidence["inputs"] = inputs.files
    return evidence
