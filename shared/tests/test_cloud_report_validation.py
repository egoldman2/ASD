"""Synthetic deployment/report fixtures; no AWS, live CI or human approval."""

import pytest

from test_report_validation import capture, SOURCE, WHEN  # noqa: F401


@pytest.fixture
def cloud_capture(capture):
    module = capture.module
    paths = [
        f".github/workflows/fixture-student-{number}.yml" for number in range(1, 6)
    ]
    release, digest = SOURCE + "-1", "b" * 64
    target = "https://fixture.cloudfront.net"
    meta = {
        "source_sha": SOURCE,
        "owner": "Fixture operator",
        "captured_at": WHEN,
        "command": "fixture capture",
    }

    def run(number, path):
        return {
            "id": number,
            "head_sha": SOURCE,
            "head_branch": "main",
            "event": "push",
            "html_url": f"https://github.com/egoldman2/ASD/actions/runs/{number}",
            "path": path,
            "status": "completed",
            "conclusion": "success",
            "run_attempt": 1,
            "jobs": [
                {
                    "name": "deploy" if number == 10 else "test",
                    "status": "completed",
                    "conclusion": "success",
                }
            ],
        }

    checks = []
    prefixes = {
        "product_catalogue": "/api/cart-items",
        "inventory": "/inventory-api/api/inventory/products",
        "customer_loyalty": "/account-api/api/admin/customers",
        "order_returns": "/api/order-returns/orders",
        "customer_support": "/api/support/admin/tickets",
    }
    for feature, prefix in prefixes.items():
        for operation, method, status in (
            ("create", "POST", 201),
            ("read", "GET", 200),
            ("update", "PUT", 200),
            ("delete", "DELETE", 200),
        ):
            checks.append(
                {
                    "feature": feature,
                    "operation": operation,
                    "method": method,
                    "path": prefix
                    + ("/1" if operation in {"update", "delete"} else ""),
                    "status": status,
                    "passed": True,
                }
            )
    checks.append(
        {
            "feature": "customer_support",
            "operation": "reply",
            "method": "POST",
            "path": "/api/support/admin/tickets/1/messages",
            "status": 201,
            "passed": True,
        }
    )
    disabled_paths = {
        "customer_support:ai": "/api/support/admin/tickets/1/ai-analysis",
        "customer_support:mcp": "/api/support/admin/mcp/tools/call",
        "customer_support:rag": "/api/support/admin/rag/answer",
        "customer_support:multi_agent": "/api/support/admin/multi-agent/tickets/1/workflows",
        "customer_loyalty:ai": "/account-api/api/admin/ai/customer-insight",
        "customer_loyalty:mcp": "/account-api/api/admin/mcp/loyalty-tier",
        "customer_loyalty:rag": "/account-api/api/admin/rag/answer",
        "product_catalogue:multi_agent": "/api/chufeng/multi-agent/workflows",
    }
    checks.extend(
        {
            "disabled_integration": name,
            "method": "POST",
            "path": disabled_paths[name],
            "status": 503,
            "safe_disabled": True,
            "passed": True,
        }
        for name in module.DISABLED_INTEGRATIONS
    )
    reports = {
        "deployment": {
            **meta,
            "release_id": release,
            "source_sha256": digest,
            "public_url": target,
            "environment": "aws-cloud",
            "region": "ap-southeast-2",
            "command_id": "11111111-1111-1111-1111-111111111111",
            "target_instance": "i-0123456789abcdef0",
            "status": "Success",
            "trigger": "github_actions",
            "acceptance": "passed",
            "run_id": 10,
            "run_attempt": 1,
        },
        "actions": run(10, ".github/workflows/cloud-deployment.yml"),
        "workflow_gate": {
            "source_sha": SOURCE,
            "status": "passed",
            "workflows": [run(n, path) for n, path in enumerate(paths, 1)],
        },
        "public_smoke": {
            **meta,
            "release_id": release,
            "base_url": target,
            "status": "passed",
            "cleanup_status": "passed",
            "checks": checks,
        },
        "runtime": {
            **meta,
            "origin": "ssm-runtime",
            "release_id": release,
            "source_sha256": digest,
            "current_release": f"/srv/asd/releases/{release}-{digest[:12]}",
            "ai_flags": {flag: "false" for flag in module.FLAGS},
            "service_names": ["gateway", "backend", "database"],
            "listening_ports": [22, 80, 6000],
        },
        "health": {
            **meta,
            "release_id": release,
            "target_instance": "i-0123456789abcdef0",
            "observation_seconds": 300,
            "status": "stable",
            "instance_status": "ok",
            "system_status": "ok",
            "new_oom_events": 0,
            "unexpected_restarts": 0,
        },
        "human_release": {
            "source_sha": SOURCE,
            "decision": "accept",
            "identity": "Fixture reviewer",
            "decided_at": WHEN,
            "reason": "Synthetic fixture decision only.",
        },
    }
    manifest = {**meta, "schema_version": 1, "kind": "cloud-deployment"}

    def collect(**kwargs):
        manifest.clear()
        manifest.update({**meta, "schema_version": 1, "kind": "cloud-deployment"})
        for name, report in reports.items():
            manifest[name] = capture.write(name + ".json", report)
        capture.write("cloud-manifest.json", manifest)
        return module.collect_cloud_evidence(
            capture.root, "cloud-manifest.json", SOURCE, kwargs.get("workflows", paths)
        )

    (
        capture.reports,
        capture.cloud_manifest,
        capture.cloud_paths,
        capture.cloud_collect,
    ) = reports, manifest, paths, collect
    return capture


def test_good_technical_capture_and_recorded_fixture_decision(cloud_capture):
    result = cloud_capture.cloud_collect()
    assert result["technical_status"] == result["status"] == "pass"
    assert len(result["checks"]) == 6 and all(
        check["status"] == "pass" for check in result["checks"]
    )
    assert (
        result["human_release"]["recorded"]
        and not result["remote_authenticity_verified"]
    )


@pytest.mark.parametrize(
    "change",
    ["manual", "failed", "skipped", "branch", "sha", "missing_gate", "stale_gate"],
)
def test_manual_wrong_or_failed_actions_cannot_establish_release(cloud_capture, change):
    reports = cloud_capture.reports
    if change == "manual":
        reports["deployment"]["trigger"] = "manual"
    elif change == "failed":
        reports["actions"]["conclusion"] = "failure"
    elif change == "skipped":
        reports["actions"]["jobs"][0]["conclusion"] = "skipped"
    elif change == "branch":
        reports["actions"]["head_branch"] = "ethan-goldman"
    elif change == "sha":
        reports["actions"]["head_sha"] = "c" * 40
    elif change == "missing_gate":
        reports["workflow_gate"]["workflows"].pop()
    else:
        reports["workflow_gate"]["workflows"][0]["head_sha"] = "c" * 40
    assert cloud_capture.cloud_collect()["status"] in {"fail", "incomplete"}


@pytest.mark.parametrize(
    "change",
    [
        "homepage",
        "old_44",
        "missing_feature",
        "missing_reply",
        "504",
        "disabled",
        "cleanup",
    ],
)
def test_smoke_needs_public_crud_and_actual_disabled_behaviour(cloud_capture, change):
    smoke = cloud_capture.reports["public_smoke"]
    if change == "homepage":
        smoke["checks"] = [
            {"method": "GET", "path": "/", "status": 200, "passed": True}
        ]
    elif change == "old_44":
        cloud_capture.reports["public_smoke"] = {
            "status": "passed",
            "checks": [{}] * 44,
        }
    elif change == "missing_feature":
        smoke["checks"] = [
            row for row in smoke["checks"] if row.get("feature") != "inventory"
        ]
    elif change == "missing_reply":
        smoke["checks"] = [
            row for row in smoke["checks"] if row.get("operation") != "reply"
        ]
    elif change == "504":
        smoke["checks"][0].update(status=504, passed=False)
    elif change == "disabled":
        smoke["checks"] = [
            row
            for row in smoke["checks"]
            if row.get("disabled_integration") != "customer_support:multi_agent"
        ]
    else:
        smoke["cleanup_status"] = "failed"
    assert cloud_capture.cloud_collect()["status"] in {"fail", "incomplete"}


@pytest.mark.parametrize(
    "change",
    [
        "enabled",
        "port",
        "service",
        "config_only",
        "stale_release",
        "bundle",
        "oom",
        "restart",
    ],
)
def test_runtime_and_health_captures_must_match_accepted_release(cloud_capture, change):
    runtime = cloud_capture.reports["runtime"]
    if change == "enabled":
        runtime["ai_flags"]["MULTI_AGENT_ENABLED"] = "true"
    elif change == "port":
        runtime["listening_ports"].append(5004)
    elif change == "service":
        runtime["service_names"].append("multi-agent-server")
    elif change == "config_only":
        runtime["origin"] = "source-compose"
    elif change == "stale_release":
        runtime["current_release"] = "/srv/asd/releases/old"
    elif change == "bundle":
        runtime["source_sha256"] = "c" * 64
    elif change == "oom":
        cloud_capture.reports["health"]["new_oom_events"] = 1
    else:
        cloud_capture.reports["health"]["unexpected_restarts"] = 1
    assert cloud_capture.cloud_collect()["status"] in {"fail", "incomplete"}


@pytest.mark.parametrize(
    "decision,status",
    [(None, "incomplete"), ("conditional_accept", "incomplete"), ("reject", "fail")],
)
def test_human_release_is_separate_and_never_generated(cloud_capture, decision, status):
    if decision is None:
        cloud_capture.reports.pop("human_release")
    else:
        cloud_capture.reports["human_release"].update(
            decision=decision, conditions="Fixture conditions remain pending."
        )
    result = cloud_capture.cloud_collect()
    assert result["technical_status"] == "pass" and result["status"] == status
    assert result["human_release"]["recorded"] == (decision is not None)


@pytest.mark.parametrize(
    "change",
    [
        "run_id",
        "attempt",
        "gate_id",
        "disabled_path",
        "human_sha",
        "human_time",
        "health_type",
        "wrong_region",
    ],
)
def test_unrelated_or_malformed_provenance_cannot_pass(cloud_capture, change):
    reports = cloud_capture.reports
    if change == "run_id":
        reports["deployment"]["run_id"] = 99
    elif change == "attempt":
        reports["actions"]["run_attempt"] = 2
    elif change == "gate_id":
        reports["workflow_gate"]["workflows"][0]["id"] = 2
    elif change == "disabled_path":
        reports["public_smoke"]["checks"][-1]["path"] = "/unrelated"
    elif change == "human_sha":
        reports["human_release"]["source_sha"] = "c" * 40
    elif change == "human_time":
        reports["human_release"]["decided_at"] = "2000-01-01T00:00:00+00:00"
    elif change == "health_type":
        reports["health"]["new_oom_events"] = False
    else:
        reports["deployment"]["region"] = "us-east-1"
    assert cloud_capture.cloud_collect()["status"] in {"fail", "incomplete"}
