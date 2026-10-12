"""Exercise the integrated cloud gateway without printing credentials or user data."""

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import uuid


def run(base_url, values):
    base_url = base_url.rstrip("/")
    origin = values.get("PUBLIC_ORIGIN", base_url)
    password = values["SEED_PASSWORD"]
    checks = []

    def request(path, method="GET", payload=None, cookie="", expected=200):
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
            response = urlopen(Request(base_url + path, data=data, headers=headers, method=method), timeout=30)
        except HTTPError as error:
            response = error
        with response:
            status, content, response_headers = response.code, response.read(), response.headers
        if status != expected:
            raise AssertionError(f"{method} {path.split('?')[0]}: expected {expected}, received {status}")
        checks.append({"method": method, "path": path.split("?")[0], "status": status})
        body = json.loads(content) if content and "application/json" in response_headers.get("Content-Type", "") else content.decode()
        return body, response_headers

    for path in ("/", "/catalogue/", "/inventory/", "/account/", "/assets/js/site-header.js", "/assets/css/styles.css"):
        body, _ = request(path)
        assert "http://localhost" not in body, f"Browser-local URL in {path}"
    request("/account-api/api/profile", expected=401)
    request("/api/order-returns/orders", expected=401)
    request("/inventory-api/api/inventory/products", expected=401)

    def login(email):
        result, headers = request("/account-api/api/login", "POST", {"email": email, "password": password})
        session_cookie = headers.get("Set-Cookie", "")
        assert "Secure" in session_cookie and "HttpOnly" in session_cookie and "SameSite=Lax" in session_cookie
        return session_cookie.split(";", 1)[0], result["user"]

    admin, _ = login("admin@asd.local")
    customer, user = login("customer@asd.local")
    request("/account-api/api/profile", cookie=customer)
    request("/account-api/api/loyalty", cookie=customer)
    request("/account-api/api/admin/customers", cookie=customer, expected=403)
    request("/inventory-api/api/inventory/products", cookie=customer, expected=403)
    request("/orders/", cookie=admin)
    request("/support/", cookie=admin)
    request("/support/", cookie=customer)
    request("/inventory-api/api/inventory/suppliers", cookie=admin)
    request("/api/order-returns/orders", cookie=customer)
    request("/api/support/customer/tickets", cookie=customer)
    request("/api/support/admin/tickets", cookie=admin)
    for path, payload in (
        ("/account-api/api/admin/ai/customer-insight", {"question": "Summarise customer accounts"}),
        ("/account-api/api/admin/mcp/loyalty-tier", {"user_id": user["id"]}),
        ("/account-api/api/admin/rag/answer", {"question": "How do loyalty tiers work?"}),
    ):
        request(path, "POST", payload, cookie=admin, expected=503)

    identifier = uuid.uuid4().hex[:12]
    cleanup = []
    try:
        account, _ = request("/account-api/api/admin/customers", "POST", {
            "full_name": "Cloud deployment check", "email": f"cloud-check-{identifier}@example.test", "password": password,
        }, cookie=admin, expected=201)
        account_path = f"/account-api/api/admin/customers/{account['user']['id']}"
        cleanup.append((account_path, admin, 200))
        request(account_path, "PUT", {"full_name": "Cloud deployment check updated"}, cookie=admin)

        inventory_path = "/inventory-api/api/inventory/products"
        product_payload = {"name": f"Cloud check {identifier}", "category": "Books", "price": 5.0, "stock_quantity": 5, "status": "active"}
        product, _ = request(inventory_path, "POST", product_payload, cookie=admin, expected=201)
        product_path = f"{inventory_path}/{product['id']}"
        cleanup.append((product_path, admin, 204))
        request(product_path, "PUT", {**product_payload, "price": 6.0}, cookie=admin)
        catalogue, _ = request("/api/products?" + urlencode({"search": identifier}))
        assert any(row["id"] == product["id"] for row in catalogue["products"])

        cart, _ = request("/api/cart-items", "POST", {"product_id": product["id"], "quantity": 1}, cookie=customer, expected=201)
        cart_path = f"/api/cart-items/{cart['item']['id']}"
        cleanup.append((cart_path, customer, 200))
        request(cart_path, "PUT", {"quantity": 2}, cookie=customer)
        request("/api/cart-items", cookie=customer)

        order, _ = request("/api/order-returns/orders", "POST", {
            "customer_id": user["id"], "order_date": "2026-10-09T00:00:00", "total": 12.0,
        }, cookie=customer, expected=201)
        order_path = f"/api/order-returns/orders/{order['order_id']}"
        cleanup.append((order_path, admin, 200))
        request(order_path, cookie=customer)
        request(order_path + "/status", "PATCH", {"status": "shipped"}, cookie=admin)

        support, _ = request("/api/support/customer/tickets", "POST", {
            "subject": f"Cloud deployment check {identifier}", "message": "Please verify this temporary deployment test ticket.",
        }, cookie=customer, expected=201)
        ticket_path = f"/api/support/admin/tickets/{support['ticket']['id']}"
        cleanup.append((ticket_path, admin, 200))
        request(ticket_path, cookie=admin)
        request(ticket_path, "PUT", {"status": "solved"}, cookie=admin)
    finally:
        for path, cookie, expected in reversed(cleanup):
            request(path, "DELETE", cookie=cookie, expected=expected)
    report = {"status": "passed", "checks": checks, "note": "Temporary account is deactivated by the application's existing DELETE behaviour; other temporary records are deleted."}
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--report", type=Path)
    arguments = parser.parse_args()
    values = dict(os.environ)
    if arguments.env_file:
        values.update(line.split("=", 1) for line in arguments.env_file.read_text().splitlines() if line and not line.startswith("#"))
    report = run(arguments.base_url, values)
    if arguments.report:
        arguments.report.parent.mkdir(parents=True, exist_ok=True)
        arguments.report.write_text(json.dumps(report, indent=2) + "\n")
