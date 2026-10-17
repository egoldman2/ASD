"""Opt-in Docker Desktop proxy checks with synthetic agents/disposable databases."""

import os
from pathlib import Path
import shutil
import subprocess
import time

import pytest

from test_support_multi_agent_routes import multi_agent_host


pytestmark = pytest.mark.skipif(os.getenv("RUN_NGINX_PROXY_CHECK") != "1",
                                reason="Opt-in local Docker Desktop/nginx check")
ROOT = Path(__file__).resolve().parents[2]


def docker(*args):
    executable = shutil.which("docker")
    if executable is None:
        pytest.fail("Docker is required for the requested proxy check")
    return subprocess.run([executable, *args], check=True, capture_output=True, text=True, timeout=30).stdout.strip()  # noqa: S603 - Fixed CLI with test-owned arguments.


@pytest.fixture
def frontend(support_stack, tmp_path):
    config = (ROOT / "student-Ethan Goldman/support_frontend_nginx.conf").read_text()
    # shortcut: Docker Desktop host routing; add Linux fixture wiring when running this opt-in on Linux.
    config = config.replace("customer-support-backend:6005", "host.docker.internal:" + support_stack.backend.url.rsplit(":", 1)[1])
    path = tmp_path / "nginx.conf"
    path.write_text(config)
    container = docker("run", "--detach", "--rm", "--publish", "127.0.0.1::80",
                       "--volume", f"{path}:/etc/nginx/nginx.conf:ro", "asd-support-frontend:release2-s08")
    try:
        address = docker("port", container, "80/tcp")
        docker("exec", container, "nginx", "-t")
        yield "http://" + address
    finally:
        docker("rm", "--force", container)


def test_workflow_creation_and_decision_through_nginx(support_stack, multi_agent_host, frontend):
    admin = support_stack.admin()
    path = "/api/support/ui/admin/multi-agent/tickets/2002/workflows"
    loaded = admin.get(frontend + path, timeout=10)
    assert loaded.status_code == 200 and "No workflows have been recorded" in loaded.text
    created = admin.post(frontend + path, data={"question": "Fixture proxy review."},
                         headers=support_stack.htmx_headers, timeout=10)
    assert created.status_code == 201 and "Reviewer" in created.text
    workflow_id = multi_agent_host.store.list_workflows()[0]["workflow_id"]
    reviewed = admin.post(frontend + path + "/" + workflow_id + "/review",
                          data={"decision": "reject", "reason": "Fixture proxy decision; no ticket changes."},
                          headers=support_stack.htmx_headers, timeout=10)
    assert reviewed.status_code == 200 and "Human decision: Reject" in reviewed.text


def test_nginx_allows_slow_success_beyond_previous_100_seconds(support_stack, frontend):
    app = support_stack.backend.server.app

    @app.get("/api/support/ui/admin/multi-agent/proxy-delay-fixture")
    def delayed_fixture():
        time.sleep(105)
        return "slow fixture completed"

    started = time.monotonic()
    response = support_stack.admin().get(frontend + "/api/support/ui/admin/multi-agent/proxy-delay-fixture", timeout=120)
    elapsed = time.monotonic() - started
    assert response.status_code == 200 and response.text == "slow fixture completed"
    assert elapsed > 100
    print(f"nginx slow fixture: HTTP {response.status_code}, {elapsed:.2f} seconds")
