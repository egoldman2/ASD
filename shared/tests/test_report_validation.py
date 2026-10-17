"""Synthetic structured report captures, never actual CI/security release evidence."""

from copy import deepcopy
from hashlib import sha256
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


SOURCE = "a" * 40
WHEN = "2026-10-17T00:00:00+00:00"


@pytest.fixture
def capture(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[2] / "ai-services")
    )
    module = importlib.import_module("report_validation")

    def write(name, value):
        raw = value if isinstance(value, bytes) else json.dumps(value).encode()
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return {"path": name, "sha256": sha256(raw).hexdigest()}

    metadata = {
        "owner": "Ethan Goldman",
        "source_sha": SOURCE,
        "captured_at": WHEN,
        "command": "fixture command",
    }
    scans = [
        {**metadata, "tool": "ruff", "exit_code": 0, "report": write("ruff.json", [])},
        {
            **metadata,
            "tool": "detect-secrets",
            "exit_code": 0,
            "report": write(
                "detector.json",
                {
                    "version": "1.5.0",
                    "plugins_used": [{"name": "fixture"}],
                    "results": {},
                },
            ),
        },
        {
            **metadata,
            "tool": "pip-audit",
            "exit_code": 0,
            "report": write(
                "audit.json",
                {"dependencies": [{"name": "fixture", "version": "1.0", "vulns": []}]},
            ),
        },
    ]
    endpoints = [
        {
            "function": "customer_create",
            "method": "POST",
            "path": "/api/support/customer/tickets",
            "test_node_id": "student-Ethan Goldman/tests/test_release2_endpoint_functions.py::test_customer_create_contract",
        },
        {
            "function": "admin_update",
            "method": "PUT",
            "path": "/api/support/admin/tickets/<int:ticket_id>",
            "test_node_id": "student-Ethan Goldman/tests/test_release2_endpoint_functions.py::test_admin_update_contract",
        },
    ]
    context = {
        **metadata,
        "feature": "customer_support",
        "run_id": "101",
        "event": "push",
        "ref": "refs/heads/main",
        "run_url": "https://github.com/egoldman2/ASD/actions/runs/101",
        "workflow": ".github/workflows/EthanGoldman.yml",
        "ai_flags": {flag: "false" for flag in module.FLAGS},
        "live_opt_ins": {name: "0" for name in module.LIVE_OPT_INS},
        "endpoint_functions": endpoints,
        "endpoint_junit": "endpoint-functions.xml",
    }
    actions = {
        "id": 101,
        "head_sha": SOURCE,
        "head_branch": "main",
        "event": "push",
        "html_url": context["run_url"],
        "path": context["workflow"],
        "status": "completed",
        "conclusion": "success",
        "jobs": [
            {"name": "test", "status": "completed", "conclusion": "success"},
            {"name": "docker", "status": "completed", "conclusion": "success"},
        ],
    }
    xml = b'<testsuites><testsuite name="fixture"><testcase classname="student-Ethan Goldman.tests.test_release2_endpoint_functions" name="test_customer_create_contract"/><testcase classname="student-Ethan Goldman.tests.test_release2_endpoint_functions" name="test_admin_update_contract"/></testsuite></testsuites>'
    student = {
        **metadata,
        "feature": "customer_support",
        "endpoints": endpoints,
        "junit": write("endpoint-functions.xml", xml),
        "context": write("context.json", context),
        "actions": write("actions.json", actions),
    }
    manifest = {
        **metadata,
        "schema_version": 1,
        "kind": "testing",
        "security": scans,
        "students": [student],
    }

    def collect(*, features=None, **kwargs):
        write("manifest.json", manifest)
        return module.collect_testing_evidence(
            tmp_path,
            "manifest.json",
            SOURCE,
            features or ["customer_support"],
            **kwargs,
        )

    return SimpleNamespace(
        root=tmp_path,
        module=module,
        write=write,
        manifest=manifest,
        scans=scans,
        student=student,
        context=context,
        actions=actions,
        xml=xml,
        collect=collect,
    )


def test_good_capture_verifies_hashes_scans_two_endpoints_and_ci(capture):
    before = {p: p.read_bytes() for p in capture.root.iterdir()}
    result = capture.collect(
        expected_endpoints={"customer_support": capture.student["endpoints"]}
    )
    assert result["status"] == "pass" and result["read_only"]
    assert (
        result["students"][0]["ci_passed"]
        and len(result["students"][0]["endpoints"]) == 2
    )
    assert all(item["passed"] for item in result["students"][0]["endpoints"])
    assert all(item["execution_ok"] for item in result["security"])
    assert all(p.read_bytes() == raw for p, raw in before.items())
    assert all(
        item["sha256"] == sha256((capture.root / item["path"]).read_bytes()).hexdigest()
        for item in result["inputs"]
    )


@pytest.mark.parametrize("tool", ["ruff", "detect-secrets", "pip-audit"])
def test_missing_tool_never_passes(capture, tool):
    capture.manifest["security"][:] = [
        entry for entry in capture.scans if entry["tool"] != tool
    ]
    assert capture.collect()["status"] == "incomplete"


@pytest.mark.parametrize("tool", ["ruff", "detect-secrets", "pip-audit"])
def test_execution_success_does_not_erase_findings(capture, tool):
    entry = next(row for row in capture.scans if row["tool"] == tool)
    if tool == "ruff":
        report = [{"code": "S104", "message": "private fixture text"}]
        entry["exit_code"] = 1
    elif tool == "detect-secrets":
        report = {
            "version": "1.5.0",
            "plugins_used": [{"name": "fixture"}],
            "results": {
                "file.py": [
                    {
                        "type": "Secret Keyword",
                        "hashed_secret": "fixture digest",  # pragma: allowlist secret - Synthetic detector metadata.
                    }
                ]
            },
        }
    else:
        report = {
            "dependencies": [
                {
                    "name": "fixture",
                    "version": "1.0",
                    "vulns": [{"id": "PYSEC-2026-311"}],
                }
            ]
        }
        entry["exit_code"] = 1
    entry["report"] = capture.write(tool + "-findings.json", report)
    result = capture.collect()
    assert result["status"] == "fail"
    scan = next(row for row in result["security"] if row["tool"] == tool)
    assert (
        scan["execution_ok"]
        and scan["finding_count"] == scan["unexcepted_findings"] == 1
    )
    assert "private fixture text" not in json.dumps(result)


def test_only_configured_documented_dependency_exceptions_are_accepted(capture):
    entry = capture.scans[2]
    entry["exit_code"] = 1
    entry["report"] = capture.write(
        "audit-findings.json",
        {
            "dependencies": [
                {
                    "name": "fixture",
                    "version": "1.0",
                    "vulns": [{"id": "PYSEC-2026-311"}],
                }
            ]
        },
    )
    entry["exceptions"] = [
        {
            "id": "PYSEC-2026-311",
            "reason": "Documented fixture exception.",
            "record": capture.write(
                "exception.md", b"Synthetic exception record, not human approval."
            ),
        }
    ]
    assert capture.collect()["status"] == "fail"
    result = capture.collect(accepted_advisories=["PYSEC-2026-311"])
    assert result["status"] == "pass_with_exceptions"
    assert (
        result["security"][2]["finding_count"] == 1
        and result["security"][2]["unexcepted_findings"] == 0
    )
    (capture.root / "exception.md").unlink()
    assert capture.collect(accepted_advisories=["PYSEC-2026-311"])["status"] == "fail"


@pytest.mark.parametrize(
    "change",
    [
        "failed",
        "error",
        "skipped",
        "missing",
        "duplicate",
        "malformed",
        "entity",
        "counts",
        "nested",
    ],
)
def test_endpoint_evidence_must_contain_two_passing_functions(capture, change):
    xml = capture.xml
    if change in {"failed", "error", "skipped"}:
        tag = {"failed": "failure", "error": "error", "skipped": "skipped"}[change]
        xml = xml.replace(
            b'name="test_admin_update_contract"/>',
            f'name="test_admin_update_contract"><{tag}/></testcase>'.encode(),
        )
    elif change == "missing":
        xml = xml.replace(b"test_admin_update_contract", b"test_other")
    elif change == "duplicate":
        xml = xml.replace(
            b"test_admin_update_contract", b"test_customer_create_contract"
        )
    elif change == "malformed":
        xml = b"invalid XML"
    elif change == "counts":
        xml = xml.replace(b'name="fixture"', b'name="fixture" failures="1"')
    elif change == "nested":
        xml = (
            b"<testsuites>"
            + b"<testsuite>" * 1000
            + b"</testsuite>" * 1000
            + b"</testsuites>"
        )
    else:
        xml = (
            b'<!DOCTYPE x [<!ENTITY sample "fixture">]><testsuite>&sample;</testsuite>'
        )
    capture.student["junit"] = capture.write("endpoint-functions.xml", xml)
    assert capture.collect()["status"] in {"fail", "incomplete"}


@pytest.mark.parametrize(
    "change",
    ["sha", "failed", "skipped_job", "no_jobs", "pending", "branch", "run", "event"],
)
def test_wrong_or_failed_actions_cannot_pass(capture, change):
    actions = deepcopy(capture.actions)
    if change == "sha":
        actions["head_sha"] = "b" * 40
    elif change == "failed":
        actions["conclusion"] = "failure"
    elif change == "skipped_job":
        actions["jobs"][0]["conclusion"] = "skipped"
    elif change == "no_jobs":
        actions["jobs"] = []
    elif change == "pending":
        actions["status"] = "in_progress"
    elif change == "branch":
        actions["head_branch"] = "different"
    elif change == "run":
        actions["id"] = 202
    else:
        actions["event"] = "workflow_dispatch"
    capture.student["actions"] = capture.write("actions.json", actions)
    assert capture.collect()["status"] in {"fail", "incomplete"}


def test_shared_requires_five_distinct_students(capture):
    assert (
        capture.collect(features=sorted(capture.module.FEATURES))["status"]
        == "incomplete"
    )
    students = []
    for feature in sorted(capture.module.FEATURES):
        student = deepcopy(capture.student)
        student["feature"] = feature
        student["owner"] = "Fixture " + feature
        directory = capture.module.FEATURE_DIRECTORIES[feature]
        for endpoint in student["endpoints"]:
            endpoint["test_node_id"] = endpoint["test_node_id"].replace(
                "student-Ethan Goldman", directory
            )
        context = deepcopy(capture.context)
        context["feature"] = feature
        context["owner"] = student["owner"]
        context["endpoint_functions"] = student["endpoints"]
        xml = capture.xml.replace(b"student-Ethan Goldman", directory.encode())
        student["junit"] = capture.write(feature + "/endpoint-functions.xml", xml)
        student["context"] = capture.write(feature + "-context.json", context)
        students.append(student)
    capture.manifest["students"] = students
    assert capture.collect(features=sorted(capture.module.FEATURES))["status"] == "pass"
    students[0]["owner"] = students[1]["owner"]
    context = json.loads((capture.root / students[0]["context"]["path"]).read_text())
    context["owner"] = students[0]["owner"]
    students[0]["context"] = capture.write("duplicate-owner.json", context)
    assert (
        capture.collect(features=sorted(capture.module.FEATURES))["status"]
        == "incomplete"
    )


@pytest.mark.parametrize(
    "change",
    [
        "parent",
        "absolute",
        "symlink",
        "oversized",
        "hash",
        "json",
        "stale_manifest",
        "stale_scan",
    ],
)
def test_invalid_or_unconfined_files_cannot_pass(capture, change):
    reference = capture.scans[0]["report"]
    if change == "parent":
        reference["path"] = "../outside.json"
    elif change == "absolute":
        reference["path"] = str(capture.root / "ruff.json")
    elif change == "symlink":
        (capture.root / "link.json").symlink_to(capture.root.parent / "outside.json")
        reference["path"] = "link.json"
    elif change == "oversized":
        capture.scans[0]["report"] = capture.write(
            "oversized.json", b" " * (1024 * 1024 + 1)
        )
    elif change == "hash":
        reference["sha256"] = "b" * 64
    elif change == "json":
        capture.scans[0]["report"] = capture.write("invalid.json", b"not JSON")
    elif change == "stale_manifest":
        capture.manifest["source_sha"] = "b" * 40
    else:
        capture.scans[0]["source_sha"] = "b" * 40
    assert capture.collect()["status"] == "incomplete"


def test_reports_cannot_inject_secret_prose_into_the_digest(capture):
    xml = capture.xml.replace(
        b"</testsuite>",
        b"<system-out>password=fixture-private-value</system-out></testsuite>",
    )
    capture.student["junit"] = capture.write("endpoint-functions.xml", xml)
    capture.student["owner"] = capture.context["owner"] = "private@example.test"
    capture.student["context"] = capture.write("context.json", capture.context)
    result = capture.collect()
    assert result["status"] == "pass"
    assert "fixture-private-value" not in json.dumps(
        result
    ) and "private@example.test" not in json.dumps(result)


@pytest.mark.parametrize(
    "change", ["owner", "feature", "source", "endpoint", "enabled_ai", "missing_opt_in"]
)
def test_context_cannot_misattribute_a_test_run(capture, change):
    context = deepcopy(capture.context)
    if change == "owner":
        context["owner"] = "Different fixture owner"
    elif change == "feature":
        context["feature"] = "product_catalogue"
    elif change == "source":
        context["source_sha"] = "b" * 40
    elif change == "endpoint":
        context["endpoint_functions"].pop()
    elif change == "enabled_ai":
        context["ai_flags"]["MULTI_AGENT_ENABLED"] = "true"
    else:
        context["live_opt_ins"].pop("RUN_LIVE_MULTI_AGENT")
    capture.student["context"] = capture.write("context.json", context)
    assert capture.collect()["status"] == "incomplete"


def test_invalid_manifest_and_total_read_budget_are_bounded(capture):
    for raw in (b"invalid JSON", b" " * (128 * 1024 + 1)):
        capture.write("bad-manifest.json", raw)
        result = capture.module.collect_testing_evidence(
            capture.root, "bad-manifest.json", SOURCE, ["customer_support"]
        )
        assert result["status"] == "incomplete" and result["issues"] == [
            "invalid_testing_manifest"
        ]
    reader = capture.module.EvidenceInputs(capture.root)
    reference = capture.write("large.txt", b"x" * (1024 * 1024))
    for _ in range(8):
        reader.read(reference)
    with pytest.raises(ValueError):
        reader.read(reference)


def test_known_failure_is_preserved_when_another_capture_is_invalid(capture):
    capture.scans[0]["report"] = capture.write("ruff.json", [{"code": "S104"}])
    capture.scans[0]["exit_code"] = 1
    capture.student["source_sha"] = "b" * 40
    result = capture.collect()
    assert result["status"] == "fail" and result["issues"]
