"""Exercise the integrated gateway; report only checks, never credentials/user data."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid


class SameOriginRedirect(HTTPRedirectHandler):
    max_redirections = 3
    max_repeats = 1

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        original, target = urlsplit(req.full_url), urlsplit(newurl)
        if (req.get_method() not in {"GET", "HEAD"} or target.username or target.password
                or (original.scheme, original.hostname, original.port) != (target.scheme, target.hostname, target.port)):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


urlopen = build_opener(SameOriginRedirect()).open


class SmokeFailure(AssertionError):
    def __init__(self, report):
        super().__init__("Gateway smoke failed; inspect its sanitized check/cleanup report.")
        self.report = report


class SmokeCheckError(AssertionError):
    """Only fixed harness messages are safe to include in report artifacts."""


def run(base_url, values):
    url = urlsplit(base_url)
    if (url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password
            or url.query or url.fragment or url.path not in {"", "/"}
            or (url.scheme == "http" and url.hostname not in {"localhost", "127.0.0.1", "::1"})):
        raise ValueError("Use an HTTPS public origin or a loopback HTTP gateway.")
    url.port
    base_url = base_url.rstrip("/")
    origin = values.get("PUBLIC_ORIGIN", base_url)
    password = values["SEED_PASSWORD"]
    checks, cleanup, cleanup_errors = [], [], []
    pending_creations = set()
    identifier = uuid.uuid4().hex[:12]
    failure = None

    def request(path, method="GET", payload=None, cookie="", expected=200, *, feature=None, operation=None, disabled=None):
        row = {"method": method, "path": path.split("?")[0], "expected_status": expected, "passed": False}
        if feature:
            row.update(feature=feature, operation=operation)
        if disabled:
            row["disabled_integration"] = disabled
        checks.append(row)
        if operation == "create":
            pending_creations.add(row["path"])
        headers = {"Origin": origin}
        if values.get("ORIGIN_TOKEN"):
            headers["X-Origin-Verify"] = values["ORIGIN_TOKEN"]
        if cookie:
            headers["Cookie"] = cookie
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        try:
            response = urlopen(Request(base_url + path, data=data, headers=headers, method=method), timeout=30)  # noqa: S310 - Root schemes/credentials are validated; redirects are bounded same-origin reads only.
        except HTTPError as error:
            response = error
        with response:
            status, content, response_headers = response.code, response.read(1024 * 1024 + 1), response.headers
        row.update(status=status, response_bytes=len(content))
        if len(content) > 1024 * 1024:
            raise ValueError("Gateway response exceeds its size limit.")
        if status != expected:
            raise SmokeCheckError("Gateway returned an unexpected HTTP status.")
        body = json.loads(content) if content and "application/json" in response_headers.get("Content-Type", "") else content.decode()
        if disabled:
            error = body.get("error") if isinstance(body, dict) else None
            code = error.get("code") if isinstance(error, dict) else body.get("code") if isinstance(body, dict) else None
            message = error.get("message") if isinstance(error, dict) else error
            row["safe_disabled"] = code in {"AI_MODE_DISABLED", "MCP_DISABLED", "RAG_DISABLED", "MULTI_AGENT_DISABLED"} or message in {
                "AI mode is disabled.", "MCP mode is disabled.", "RAG mode is disabled.", "AI or RAG mode is disabled.",
                "MCP integration is disabled.", "Multi-Agent integration is disabled.",
            }
            if not row["safe_disabled"]:
                raise SmokeCheckError("The endpoint did not establish disabled behaviour.")
        row["passed"] = True
        return body, response_headers

    def created_id(payload, *keys):
        value = payload
        for key in keys:
            value = value.get(key) if isinstance(value, dict) else None
        if type(value) is not int or value < 1:
            cleanup_errors.append({"path": checks[-1]["path"], "error_type": "unidentified_created_record"})
            raise ValueError("A created record did not provide a safe identifier.")
        pending_creations.discard(checks[-1]["path"])
        return value

    def login(email):
        result, headers = request("/account-api/api/login", "POST", {"email": email, "password": password})
        cookie = headers.get("Set-Cookie", "")
        if not all(marker in cookie for marker in ("Secure", "HttpOnly", "SameSite=Lax")):
            raise SmokeCheckError("Login cookie safeguards were missing.")
        return cookie.split(";", 1)[0], result["user"]

    try:
        for path in ("/", "/catalogue/", "/inventory/", "/account/", "/assets/js/site-header.js", "/assets/css/styles.css"):
            body, _ = request(path)
            if "http://localhost" in body:
                raise SmokeCheckError("A browser asset still references localhost.")
        for path in ("/account-api/api/profile", "/api/order-returns/orders", "/inventory-api/api/inventory/products", "/api/support/customer/tickets"):
            request(path, expected=401)
        admin, _ = login("admin@asd.local")
        customer, user = login("customer@asd.local")
        request("/account-api/api/profile", cookie=customer)
        request("/account-api/api/loyalty", cookie=customer)
        for path in ("/account-api/api/admin/customers", "/inventory-api/api/inventory/products", "/api/support/admin/tickets"):
            request(path, cookie=customer, expected=403)
        for path, cookie in (("/orders/", admin), ("/support/", admin), ("/support/", customer),
                             ("/inventory-api/api/inventory/suppliers", admin), ("/api/order-returns/orders", customer),
                             ("/api/support/customer/tickets", customer), ("/api/support/admin/tickets", admin)):
            request(path, cookie=cookie)
        for mode, path, payload in (
            ("ai", "/account-api/api/admin/ai/customer-insight", {"question": "Summarise customer accounts"}),
            ("mcp", "/account-api/api/admin/mcp/loyalty-tier", {"user_id": user["id"]}),
            ("rag", "/account-api/api/admin/rag/answer", {"question": "How do loyalty tiers work?"}),
        ):
            request(path, "POST", payload, cookie=admin, expected=503, disabled="customer_loyalty:" + mode)

        email = f"cloud-check-{identifier}@example.test"
        account, _ = request("/account-api/api/admin/customers", "POST", {"full_name": "Cloud deployment check", "email": email, "password": password},
                             cookie=admin, expected=201, feature="customer_loyalty", operation="create")
        account_id = created_id(account, "user", "id")
        account_path = f"/account-api/api/admin/customers/{account_id}"
        cleanup.append((account_path, admin, 200, "customer_loyalty"))
        request(account_path, "PUT", {"full_name": "Cloud deployment check updated"}, cookie=admin, feature="customer_loyalty", operation="update")
        accounts, _ = request("/account-api/api/admin/customers", cookie=admin, feature="customer_loyalty", operation="read")
        if not any(row["id"] == account_id and row["full_name"] == "Cloud deployment check updated" for row in accounts["users"]):
            raise SmokeCheckError("Account changes did not persist.")
        other_customer, other = login(email)
        if other["id"] != account_id:
            raise SmokeCheckError("The temporary account login did not match its record.")

        inventory_path = "/inventory-api/api/inventory/products"
        product_payload = {"name": f"Cloud check {identifier}", "category": "Books", "price": 5.0, "stock_quantity": 5, "status": "active"}
        product, _ = request(inventory_path, "POST", product_payload, cookie=admin, expected=201, feature="inventory", operation="create")
        product_id = created_id(product, "id")
        product_path = f"{inventory_path}/{product_id}"
        cleanup.append((product_path, admin, 204, "inventory"))
        request(product_path, "PUT", {**product_payload, "price": 6.0}, cookie=admin, feature="inventory", operation="update")
        persisted, _ = request(product_path, cookie=admin, feature="inventory", operation="read")
        if persisted.get("id") != product_id or persisted.get("price") != 6.0:
            raise SmokeCheckError("Product changes did not persist.")
        catalogue, _ = request("/api/products?" + urlencode({"search": identifier}))
        if not any(row["id"] == product_id for row in catalogue["products"]):
            raise SmokeCheckError("The shared catalogue did not expose the new product.")
        request("/api/chufeng/multi-agent/workflows", "POST", {"question": "Review this deployment fixture product.", "product_id": product_id},
                cookie=admin, expected=503, disabled="product_catalogue:multi_agent")

        cart, _ = request("/api/cart-items", "POST", {"product_id": product_id, "quantity": 1}, cookie=customer, expected=201,
                          feature="product_catalogue", operation="create")
        cart_id = created_id(cart, "item", "id")
        cart_path = f"/api/cart-items/{cart_id}"
        cleanup.append((cart_path, customer, 200, "product_catalogue"))
        request(cart_path, "PUT", {"quantity": 2}, cookie=customer, feature="product_catalogue", operation="update")
        cart, _ = request("/api/cart-items", cookie=customer, feature="product_catalogue", operation="read")
        if not any(row["id"] == cart_id and row["quantity"] == 2 for row in cart["items"]):
            raise SmokeCheckError("Cart changes did not persist.")

        order, _ = request("/api/order-returns/orders", "POST", {"customer_id": user["id"], "order_date": "2026-10-09T00:00:00", "total": 12.0},
                           cookie=customer, expected=201, feature="order_returns", operation="create")
        order_path = f"/api/order-returns/orders/{created_id(order, 'order_id')}"
        cleanup.append((order_path, admin, 200, "order_returns"))
        request(order_path + "/status", "PATCH", {"status": "shipped"}, cookie=admin, feature="order_returns", operation="update")
        order, _ = request(order_path, cookie=customer, feature="order_returns", operation="read")
        if order.get("status") != "shipped":
            raise SmokeCheckError("Order status changes did not persist.")

        support, _ = request("/api/support/customer/tickets", "POST", {"subject": f"Cloud deployment check {identifier}",
                            "message": "Please verify this temporary deployment test ticket."}, cookie=customer, expected=201,
                            feature="customer_support", operation="create")
        ticket_id = created_id(support, "ticket", "id")
        ticket_path = f"/api/support/admin/tickets/{ticket_id}"
        cleanup.append((ticket_path, admin, 200, "customer_support"))
        before, _ = request(ticket_path, cookie=admin, feature="customer_support", operation="read")
        request(f"/api/support/customer/tickets/{ticket_id}", cookie=other_customer, expected=404)
        request(ticket_path, "PUT", {"status": "solved"}, cookie=customer, expected=403)
        for mode, path, payload in (
            ("ai", ticket_path + "/ai-analysis", {}),
            ("mcp", "/api/support/admin/mcp/tools/call", {"tool": "ethan_goldman_get_queue_summary", "arguments": {}}),
            ("rag", "/api/support/admin/rag/answer", {"question": "How do staff update a ticket?"}),
            ("multi_agent", f"/api/support/admin/multi-agent/tickets/{ticket_id}/workflows", {"question": "Review this deployment fixture."}),
        ):
            request(path, "POST", payload, cookie=admin, expected=503, disabled="customer_support:" + mode)
        after, _ = request(ticket_path, cookie=admin)
        if before["ticket"] != after["ticket"]:
            raise SmokeCheckError("Disabled AI requests changed ticket data.")
        reply = "Synthetic deployment verification staff reply."
        request(ticket_path + "/messages", "POST", {"message": reply}, cookie=admin, expected=201, feature="customer_support", operation="reply")
        request(ticket_path, "PUT", {"status": "solved"}, cookie=admin, feature="customer_support", operation="update")
        persisted, _ = request(ticket_path, cookie=admin)
        if persisted["ticket"].get("status") != "solved" or not any(row.get("sender_role") == "staff" and row.get("message") == reply for row in persisted["ticket"]["messages"]):
            raise SmokeCheckError("The support update/staff reply did not persist.")
    except Exception as error:
        failure = error
    finally:
        for path, cookie, expected, feature in reversed(cleanup):
            try:
                request(path, "DELETE", cookie=cookie, expected=expected, feature=feature, operation="delete")
                if feature in {"inventory", "order_returns", "customer_support"}:
                    request(path, cookie=cookie, expected=404)
                elif feature == "product_catalogue":
                    remaining, _ = request("/api/cart-items", cookie=cookie)
                    if any(row.get("id") == int(path.rsplit("/", 1)[1]) for row in remaining["items"]):
                        raise SmokeCheckError("The temporary cart item survived deletion.")
                else:
                    remaining, _ = request("/account-api/api/admin/customers", cookie=cookie)
                    if not any(row.get("id") == int(path.rsplit("/", 1)[1]) and row.get("is_active") in {False, 0} for row in remaining["users"]):
                        raise SmokeCheckError("The temporary account was not deactivated.")
            except Exception as error:
                cleanup_errors.append({"path": path, "error_type": type(error).__name__})
    for path in pending_creations:
        if not any(error["path"] == path for error in cleanup_errors):
            cleanup_errors.append({"path": path, "error_type": "unconfirmed_create"})
    matrix = {}
    for row in checks:
        if row.get("feature") and row["passed"]:
            matrix.setdefault(row["feature"], set()).add(row["operation"])
    report = {"status": "failed" if failure or cleanup_errors else "passed", "checks": checks,
              "captured_at": datetime.now(timezone.utc).isoformat(), "base_url": base_url,
              "source_sha": values.get("ASD_SOURCE_SHA"), "release_id": values.get("RELEASE_ID"),
              "temporary_identifier": identifier, "cleanup_status": "failed" if cleanup_errors else "passed",
              "cleanup_errors": cleanup_errors, "unconfirmed_creations": sorted(pending_creations),
              "feature_crud": {key: sorted(value) for key, value in matrix.items()},
              "note": "Cleanup uses only IDs from successful creates. Account DELETE deactivates its data; other deletes use existing APIs. Inspect cleanup errors/unconfirmed creates on failure."}
    if failure:
        report["failure"] = {"error_type": type(failure).__name__}
        if isinstance(failure, SmokeCheckError):
            report["failure"]["safe_reason"] = str(failure)
    if failure or cleanup_errors:
        raise SmokeFailure(report) from failure
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--report", type=Path)
    arguments = parser.parse_args(argv)
    values = dict(os.environ)
    try:
        if arguments.env_file:
            values.update(line.split("=", 1) for line in arguments.env_file.read_text().splitlines() if line and not line.startswith("#"))
        report = run(arguments.base_url, values)
    except SmokeFailure as error:
        report = error.report
    except (ValueError, KeyError, OSError):
        report = {"status": "failed", "failure": {"error_type": "invalid_smoke_configuration"}, "checks": []}
    if arguments.report:
        arguments.report.parent.mkdir(parents=True, exist_ok=True)
        arguments.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
