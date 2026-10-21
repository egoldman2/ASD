"""Read-only validation of captured Release 2 reports; prose cannot pass a gate."""

from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

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


CLOUD_CRUD = {
    "product_catalogue": r"/api/cart-items(?:/\d+)?",
    "inventory": r"/inventory-api/api/inventory/products(?:/\d+)?",
    "customer_loyalty": r"/account-api/api/admin/customers(?:/\d+)?",
    "order_returns": r"/api/order-returns/orders(?:/\d+)?(?:/status)?",
    "customer_support": r"/api/support/(?:customer|admin)/tickets(?:/\d+)?(?:/messages)?",
}
DISABLED_PATHS = {
    "customer_support:ai": r"/api/support/admin/tickets/\d+/ai-analysis",
    "customer_support:mcp": r"/api/support/admin/mcp/(?:tools/call|assistant)",
    "customer_support:rag": r"/api/support/admin/rag/answer",
    "customer_support:multi_agent": r"/api/support/admin/multi-agent/tickets/\d+/workflows",
    "customer_loyalty:ai": r"/account-api/api/admin/ai/customer-insight",
    "customer_loyalty:mcp": r"/account-api/api/admin/mcp/loyalty-tier",
    "customer_loyalty:rag": r"/account-api/api/admin/rag/answer",
    "product_catalogue:multi_agent": r"/api/chufeng/multi-agent/workflows",
    "customer_loyalty:multi_agent": r"/account-api/api/admin/multi-agent/workflows",
    "inventory:multi_agent": r"/inventory-api/api/inventory/multi-agent/workflows",
    "order_returns:multi_agent": r"/api/order-returns/multi-agent/workflows",
}
DISABLED_INTEGRATIONS = set(DISABLED_PATHS)


def _main_run(run, source_sha):
    _require(isinstance(run, dict) and run.get("head_sha") == source_sha)
    _require(run.get("head_branch") == "main" and run.get("event") == "push")
    _require(type(run.get("id")) is int and run["id"] > 0)
    _require(
        run.get("html_url")
        == f"https://github.com/egoldman2/ASD/actions/runs/{run['id']}"
    )
    jobs = run.get("jobs")
    _require(
        isinstance(jobs, list)
        and 0 < len(jobs) <= 30
        and all(isinstance(job, dict) for job in jobs)
    )
    return (
        run.get("status") == "completed"
        and run.get("conclusion") == "success"
        and all(
            job.get("status") == "completed" and job.get("conclusion") == "success"
            for job in jobs
        )
    )


def _cloud_smoke(smoke, source_sha, release, target):
    _require(isinstance(smoke, dict) and smoke.get("source_sha") == source_sha)
    _require(smoke.get("release_id") == release and smoke.get("base_url") == target)
    _timestamp(smoke.get("captured_at"))
    rows = smoke.get("checks")
    _require(
        isinstance(rows, list)
        and 0 < len(rows) <= 300
        and all(isinstance(row, dict) for row in rows)
    )
    matrix = {feature: set() for feature in FEATURES}
    disabled = set()
    methods = {
        "create": {"POST"},
        "read": {"GET"},
        "update": {"PUT", "PATCH"},
        "delete": {"DELETE"},
        "reply": {"POST"},
    }
    statuses = {
        "create": {201},
        "read": {200},
        "update": {200},
        "delete": {200, 204},
        "reply": {201},
    }
    for row in rows:
        feature, operation = row.get("feature"), row.get("operation")
        if feature in matrix and operation in methods and row.get("passed") is True:
            if (
                row.get("method") in methods[operation]
                and row.get("status") in statuses[operation]
                and re.fullmatch(CLOUD_CRUD[feature], str(row.get("path")))
            ):
                matrix[feature].add(operation)
        if (
            row.get("disabled_integration") in DISABLED_INTEGRATIONS
            and row.get("status") == 503
            and row.get("safe_disabled") is True
            and row.get("method") == "POST"
            and re.fullmatch(
                DISABLED_PATHS[row["disabled_integration"]], str(row.get("path"))
            )
        ):
            disabled.add(row["disabled_integration"])
    missing = {
        feature: sorted(
            (
                {"create", "read", "update", "delete", "reply"}
                if feature == "customer_support"
                else {"create", "read", "update", "delete"}
            )
            - operations
        )
        for feature, operations in matrix.items()
    }
    passed = (
        smoke.get("status") == "passed"
        and smoke.get("cleanup_status") == "passed"
        and all(row.get("passed") is True for row in rows)
        and not any(missing.values())
        and disabled == DISABLED_INTEGRATIONS
    )
    return {
        "status": "pass" if passed else "fail",
        "check_count": len(rows),
        "missing_crud": missing,
        "missing_disabled": sorted(DISABLED_INTEGRATIONS - disabled),
        "cleanup_status": smoke.get("cleanup_status"),
    }


def collect_cloud_evidence(root, manifest_path, source_sha, required_workflows):
    """Validate captured main Actions, accepted release and public/runtime evidence."""
    _require(isinstance(source_sha, str) and re.fullmatch(r"[a-f0-9]{40}", source_sha))
    _require(
        isinstance(required_workflows, list)
        and len(required_workflows) == len(set(required_workflows)) == 5
    )
    _require(
        all(
            isinstance(path, str)
            and re.fullmatch(r"\.github/workflows/[A-Za-z0-9_-]+\.ya?ml", path)
            and path != ".github/workflows/cloud-deployment.yml"
            for path in required_workflows
        )
    )
    inputs = EvidenceInputs(root)
    evidence = {
        "kind": "cloud-deployment",
        "read_only": True,
        "source_sha": source_sha,
        "status": "incomplete",
        "technical_status": "incomplete",
        "checks": [],
        "issues": [],
        "human_release": {"recorded": False},
        "remote_authenticity_verified": False,
        "limitations": [
            "Supplied captures are checked offline; remote authenticity is not independently verified.",
            "A technical result or model recommendation cannot grant a human release approval.",
            "Recorded core CRUD does not establish unrecorded returns/supplier operations or production capacity.",
        ],
    }
    manifest = {}
    try:
        manifest = json.loads(inputs.read({"path": manifest_path}, limit=128 * 1024))
        _require(
            isinstance(manifest, dict)
            and manifest.get("schema_version") == 1
            and manifest.get("kind") == "cloud-deployment"
        )
        _capture(manifest, source_sha)
        deploy = inputs.json(manifest.get("deployment"))
        _capture(deploy, source_sha)
        release, digest, target = (
            deploy.get("release_id"),
            deploy.get("source_sha256"),
            deploy.get("public_url"),
        )
        _require(
            isinstance(release, str)
            and re.fullmatch(re.escape(source_sha) + r"-[1-9][0-9]{0,8}", release)
        )
        _require(
            type(deploy.get("run_id")) is int
            and deploy["run_id"] > 0
            and type(deploy.get("run_attempt")) is int
            and deploy["run_attempt"] > 0
        )
        _require(release == source_sha + "-" + str(deploy["run_attempt"]))
        _require(isinstance(digest, str) and re.fullmatch(r"[a-f0-9]{64}", digest))
        url = urlsplit(target)
        _require(
            url.scheme == "https"
            and url.hostname
            and re.fullmatch(r"[A-Za-z0-9.-]+", url.hostname)
            and url.port in {None, 443}
            and not url.username
            and not url.password
            and url.path in {"", "/"}
            and not url.query
            and not url.fragment
        )
        _require(
            deploy.get("environment") == "aws-cloud"
            and deploy.get("region") == "ap-southeast-2"
        )
        _require(
            isinstance(deploy.get("command_id"), str)
            and re.fullmatch(
                r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", deploy["command_id"]
            )
        )
        _require(
            isinstance(deploy.get("target_instance"), str)
            and re.fullmatch(
                r"i-(?:[a-f0-9]{8}|[a-f0-9]{17})", deploy["target_instance"]
            )
        )
        evidence["release"] = {
            "release_id": release,
            "source_sha256": digest,
            "target_url": target,
            "command_id": deploy["command_id"],
            "environment": "aws-cloud",
            "region": "ap-southeast-2",
        }
        evidence["checks"].append(
            {
                "name": "ssm_acceptance",
                "status": "pass"
                if deploy.get("status") == "Success"
                and deploy.get("trigger") == "github_actions"
                and deploy.get("acceptance") == "passed"
                else "fail",
            }
        )
        for name in ("actions", "workflow_gate", "public_smoke", "runtime", "health"):
            try:
                report = inputs.json(manifest.get(name))
                _require(isinstance(report, dict))
                if name == "actions":
                    passed = _main_run(report, source_sha)
                    _require(
                        report.get("id") == deploy["run_id"]
                        and report.get("run_attempt") == deploy["run_attempt"]
                    )
                    _require(
                        report.get("path") == ".github/workflows/cloud-deployment.yml"
                    )
                    passed &= any(job.get("name") == "deploy" for job in report["jobs"])
                    detail = {"run_url": report["html_url"]}
                elif name == "workflow_gate":
                    _require(report.get("source_sha") == source_sha)
                    runs = report.get("workflows")
                    _require(
                        isinstance(runs, list)
                        and len(runs) == 5
                        and all(isinstance(run, dict) for run in runs)
                    )
                    _require(
                        {run.get("path") for run in runs} == set(required_workflows)
                    )
                    _require(len({run.get("id") for run in runs}) == 5)
                    passed = report.get("status") == "passed" and all(
                        _main_run(run, source_sha) for run in runs
                    )
                    detail = {"workflow_count": len(runs)}
                elif name == "public_smoke":
                    detail = _cloud_smoke(report, source_sha, release, target)
                    passed = detail.pop("status") == "pass"
                elif name == "runtime":
                    _capture(report, source_sha)
                    _require(report.get("origin") == "ssm-runtime")
                    _require(
                        report.get("release_id") == release
                        and report.get("source_sha256") == digest
                    )
                    expected_path = f"/srv/asd/releases/{release}-{digest[:12]}"
                    _require(report.get("current_release") == expected_path)
                    flags, services, ports = (
                        report.get("ai_flags"),
                        report.get("service_names"),
                        report.get("listening_ports"),
                    )
                    _require(isinstance(flags, dict) and FLAGS <= flags.keys())
                    _require(
                        isinstance(services, list)
                        and services
                        and all(_text(service, 100) for service in services)
                    )
                    _require(
                        isinstance(ports, list)
                        and ports
                        and all(
                            type(port) is int and 0 < port <= 65535 for port in ports
                        )
                    )
                    passed = (
                        all(flags[name] == "false" for name in FLAGS)
                        and not any(
                            re.search(
                                r"ollama|multi[-_]?agent|(?:mcp|rag)[-_]?server|(?:^|[-_])(?:mcp|rag)(?:$|[-_])",
                                service,
                                re.IGNORECASE,
                            )
                            for service in services
                        )
                        and not ({11434, 8765, 5003, 5004} & set(ports))
                    )
                    detail = {
                        "baseline_flags_disabled": all(
                            flags[name] == "false" for name in FLAGS
                        ),
                        "current_release": expected_path,
                    }
                else:
                    _capture(report, source_sha)
                    _require(
                        report.get("release_id") == release
                        and report.get("target_instance") == deploy["target_instance"]
                    )
                    _require(
                        type(report.get("observation_seconds")) is int
                        and report["observation_seconds"] > 0
                    )
                    _require(
                        all(
                            type(report.get(field)) is int and report[field] >= 0
                            for field in ("new_oom_events", "unexpected_restarts")
                        )
                    )
                    passed = (
                        report.get("status") == "stable"
                        and report.get("instance_status")
                        == report.get("system_status")
                        == "ok"
                        and report.get("new_oom_events")
                        == report.get("unexpected_restarts")
                        == 0
                    )
                    detail = {
                        "observation_seconds": report["observation_seconds"],
                        "capacity_limit": "Only the recorded observation window is covered.",
                    }
                evidence["checks"].append(
                    {"name": name, "status": "pass" if passed else "fail", **detail}
                )
            except (ValueError, TypeError, KeyError, OSError, RecursionError):
                evidence["issues"].append("invalid_" + name + "_capture")
        evidence["technical_status"] = (
            "fail"
            if any(check["status"] == "fail" for check in evidence["checks"])
            else "incomplete"
            if evidence["issues"]
            else "pass"
        )
        human_ref = manifest.get("human_release")
        if human_ref:
            try:
                human = inputs.json(human_ref)
                _require(
                    isinstance(human, dict) and human.get("source_sha") == source_sha
                )
                _require(
                    human.get("decision") in {"accept", "conditional_accept", "reject"}
                )
                _require(
                    _text(human.get("identity")) and _text(human.get("reason"), 2000)
                )
                _timestamp(human.get("decided_at"))
                _require(
                    datetime.fromisoformat(human["decided_at"].replace("Z", "+00:00"))
                    >= datetime.fromisoformat(
                        deploy["captured_at"].replace("Z", "+00:00")
                    )
                )
                if human["decision"] == "conditional_accept":
                    _require(_text(human.get("conditions"), 2000))
                evidence["human_release"] = {
                    "recorded": True,
                    "decision": human["decision"],
                    "identity": public_evidence(human["identity"]),
                    "reason_present": True,
                    "conditions_pending": human["decision"] == "conditional_accept",
                }
            except (ValueError, TypeError, KeyError, OSError, RecursionError):
                evidence["issues"].append("invalid_human_release_record")
        decision = evidence["human_release"].get("decision")
        evidence["status"] = (
            "fail"
            if evidence["technical_status"] == "fail" or decision == "reject"
            else "incomplete"
            if evidence["technical_status"] != "pass"
            or decision != "accept"
            or evidence["issues"]
            else "pass"
        )
        if not evidence["human_release"]["recorded"]:
            evidence["issues"].append("human_release_decision_missing")
    except (ValueError, TypeError, KeyError, OSError, RecursionError):
        evidence["issues"].append("invalid_cloud_manifest_or_deployment")
        # A failed preflight produces no accepted deployment artifact.
        try:
            _require(isinstance(manifest, dict))
            _require(manifest.get("schema_version") == 1)
            _require(manifest.get("kind") == "cloud-deployment")
            _capture(manifest, source_sha)
            actions = inputs.json(manifest.get("actions"))
            _main_run(actions, source_sha)
            _require(actions.get("path") == ".github/workflows/cloud-deployment.yml")
            if (
                actions.get("status") == "completed"
                and actions.get("conclusion") == "failure"
                and any(
                    job.get("status") == "completed"
                    and job.get("conclusion") == "failure"
                    for job in actions["jobs"]
                )
            ):
                evidence["checks"].append(
                    {"name": "actions", "status": "fail", "run_url": actions["html_url"]}
                )
                evidence["technical_status"] = evidence["status"] = "fail"
        except (ValueError, TypeError, KeyError, OSError, RecursionError):
            pass
    evidence["inputs"] = inputs.files
    return evidence
