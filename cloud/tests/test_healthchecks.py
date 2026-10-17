"""Keep cloud readiness checks effective within the measured idle CPU budget."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
from threading import Thread

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SERVICES = {
    "shared-backend": (5000, "/api/products"),
    "ethan-backend": (6002, "/ready"),
    "inventory-backend": (8102, "/health"),
    "customer-support-backend": (6005, "/health"),
    "product-database": (6001, "/health"),
    "ethan-database": (6003, "/health"),
    "customer-support-database": (6006, "/health"),
}


def configuration():
    return yaml.safe_load((ROOT / "cloud/compose.yml").read_text())


def test_probe_schedule_reduces_steady_execs_and_keeps_startup_and_failure_window():
    services = configuration()["services"]
    checks = {name: service["healthcheck"] for name, service in services.items()
              if "healthcheck" in service}
    assert set(checks) == set(SERVICES)
    for check in checks.values():
        assert check["interval"] == "30s"
        assert check["start_interval"] == "5s"
        assert check["start_period"] == "30s"
        assert check["timeout"] == "3s"
        assert check["retries"] == 5
        assert 30 * check["retries"] == 5 * 30  # Preserve the configured 150s failure budget.


@pytest.mark.parametrize("service", SERVICES)
@pytest.mark.parametrize("status", [200, 503])
def test_actual_probe_checks_its_endpoint_and_rejects_http_failure(service, status):
    port, endpoint = SERVICES[service]
    command = configuration()["services"][service]["healthcheck"]["test"]
    assert command[:3] == ["CMD", "python", "-c"]
    assert len(command) == 4
    url = f"http://127.0.0.1:{port}{endpoint}"
    assert command[3] == f"import urllib.request; urllib.request.urlopen('{url}', timeout=2)"
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(status)
            self.end_headers()

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        probe = command[3].replace(f":{port}/", f":{server.server_port}/")
        try:
            result = subprocess.run(  # noqa: S603 - Exact repository probe asserted above; only fixture port is substituted, no shell.
                [sys.executable, "-c", probe], capture_output=True, timeout=10,
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)
    assert requests == [endpoint]
    assert (result.returncode == 0) is (status == 200)
