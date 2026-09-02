import importlib.util
from pathlib import Path
from urllib.error import URLError

import pytest


STUDENT_FOLDER = Path(__file__).resolve().parents[1]
BACKEND_APP_PATH = STUDENT_FOLDER / "backend" / "app.py"


def load_module(module_name):
    specification = importlib.util.spec_from_file_location(
        module_name,
        BACKEND_APP_PATH,
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.fixture
def auth_module():
    module = load_module("ethan_customer_insight_app")
    module.app.config.update(TESTING=True, SECRET_KEY="unit-test-key")
    return module


def login_session(client, role="admin", user_id=1):
    with client.session_transaction() as current_session:
        current_session["user"] = {
            "id": user_id,
            "email": f"{role}@asd.local",
            "full_name": f"Test {role.title()}",
            "role": role,
        }


def admin_user():
    return {
        "id": 1,
        "email": "admin@asd.local",
        "full_name": "Test Admin",
        "role": "admin",
        "is_active": 1,
    }


def customer_data_request(path, method="GET", payload=None):
    if path == "/internal/users/1":
        return {"user": admin_user()}
    if path == "/internal/users?role=customer":
        return {
            "users": [
                {
                    "id": 2,
                    "email": "customer@asd.local",
                    "full_name": "Demo Customer",
                    "role": "customer",
                    "is_active": 1,
                    "password_hash": "".join(
                        ("TEST", "_VALUE", "_NOT", "_FOR", "_AI")
                    ),
                    "internal_note": "not-allow-listed",
                },
                {
                    "id": 3,
                    "email": "disabled@example.test",
                    "full_name": "Disabled Customer",
                    "role": "customer",
                    "is_active": 0,
                },
            ]
        }
    if path == "/internal/loyalty":
        return {
            "loyalty_accounts": [
                {
                    "user_id": 2,
                    "points_balance": 499,
                    "tier": "Bronze",
                    "next_tier": "Silver",
                    "points_to_next_tier": 1,
                },
                {
                    "user_id": 3,
                    "points_balance": 1000,
                    "tier": "Gold",
                    "next_tier": None,
                    "points_to_next_tier": 0,
                },
            ]
        }
    raise AssertionError(f"Unexpected database request: {method} {path} {payload}")


def valid_ai_answer(customer_id=2):
    return (
        "ANSWER\n"
        f"Customer #{customer_id} is one point from the Silver tier.\n\n"
        "EVIDENCE\n"
        "The supplied record has 499 points and needs 1 more point.\n\n"
        "LIMITATIONS\n"
        "This is read-only analysis of the supplied records."
    )


def test_customer_insight_requires_an_administrator(auth_module, monkeypatch):
    monkeypatch.setattr(
        auth_module,
        "ollama_customer_insight",
        lambda prompt: pytest.fail("Ollama must not be called"),
    )

    with auth_module.app.test_client() as client:
        signed_out = client.post(
            "/api/admin/ai/customer-insight",
            json={"question": "Find a customer."},
        )
        login_session(client, role="customer", user_id=2)
        customer = client.post(
            "/api/admin/ai/customer-insight",
            json={"question": "Find a customer."},
        )

    assert signed_out.status_code == 401
    assert customer.status_code == 403


def test_customer_insight_validates_question_before_ai(
    auth_module,
    monkeypatch,
):
    monkeypatch.setattr(
        auth_module,
        "database_request",
        lambda path, method="GET", payload=None: {"user": admin_user()},
    )
    monkeypatch.setattr(
        auth_module,
        "ollama_customer_insight",
        lambda prompt: pytest.fail("Ollama must not be called"),
    )

    with auth_module.app.test_client() as client:
        login_session(client)
        missing_json = client.post(
            "/api/admin/ai/customer-insight",
            data="not json",
        )
        empty_question = client.post(
            "/api/admin/ai/customer-insight",
            json={"question": "   "},
        )
        long_question = client.post(
            "/api/admin/ai/customer-insight",
            json={
                "question": "x" * (auth_module.MAX_INSIGHT_QUESTION_LENGTH + 1)
            },
        )

    assert missing_json.status_code == 400
    assert empty_question.status_code == 400
    assert long_question.status_code == 400


def test_customer_insight_sends_only_allow_listed_fields(
    auth_module,
    monkeypatch,
):
    captured_prompts = []
    monkeypatch.setattr(auth_module, "database_request", customer_data_request)
    monkeypatch.setattr(
        auth_module,
        "ollama_customer_insight",
        lambda prompt: captured_prompts.append(prompt) or valid_ai_answer(),
    )

    with auth_module.app.test_client() as client:
        login_session(client)
        response = client.post(
            "/api/admin/ai/customer-insight",
            json={"question": "Who is closest to Silver?"},
        )

    assert response.status_code == 200
    result = response.get_json()
    assert result["read_only"] is True
    assert result["customers_analyzed"] == 2
    assert result["model"] == auth_module.OLLAMA_MODEL
    assert result["workflow"]["adapt"] == "Accepted the first validated response."
    assert len(captured_prompts) == 1
    assert "password_hash" not in captured_prompts[0]
    assert "internal_note" not in captured_prompts[0]
    assert "admin@asd.local" not in captured_prompts[0]
    assert '"customer_id": 2' in captured_prompts[0]
    assert '"points_balance": 499' in captured_prompts[0]


def test_customer_insight_adapts_an_unsafe_first_response(
    auth_module,
    monkeypatch,
):
    answers = iter([
        "I have updated Customer #2 and added loyalty points.",
        valid_ai_answer(),
    ])
    captured_prompts = []
    monkeypatch.setattr(auth_module, "database_request", customer_data_request)
    monkeypatch.setattr(
        auth_module,
        "ollama_customer_insight",
        lambda prompt: captured_prompts.append(prompt) or next(answers),
    )

    with auth_module.app.test_client() as client:
        login_session(client)
        response = client.post(
            "/api/admin/ai/customer-insight",
            json={"question": "Add points to the closest customer."},
        )

    assert response.status_code == 200
    result = response.get_json()
    assert result["workflow"]["adapt"] == (
        "Requested and accepted a corrected response."
    )
    assert len(captured_prompts) == 2
    assert "Do not claim that any customer data was changed." in captured_prompts[1]
    assert result["answer"] == valid_ai_answer()


def test_customer_change_prepares_validated_proposal_without_writing(
    auth_module,
    monkeypatch,
):
    database_calls = []

    def recorded_database_request(path, method="GET", payload=None):
        database_calls.append((path, method, payload))
        return customer_data_request(path, method, payload)

    monkeypatch.setattr(
        auth_module,
        "database_request",
        recorded_database_request,
    )
    monkeypatch.setattr(
        auth_module,
        "ollama_customer_change",
        lambda prompt: (
            '{"full_name":"Jordan Lee",'
            '"email":"jordan.lee@example.test"}'
        ),
    )
    monkeypatch.setattr(
        auth_module,
        "ollama_customer_insight",
        lambda prompt: pytest.fail("The general insight model must not be called"),
    )

    with auth_module.app.test_client() as client:
        login_session(client)
        response = client.post(
            "/api/admin/ai/customer-insight",
            json={
                "question": (
                    "Change the full name for customer@asd.local to Jordan Lee "
                    "and change their email to jordan.lee@example.test."
                )
            },
        )

    assert response.status_code == 200
    result = response.get_json()
    assert result["read_only"] is True
    assert result["proposal"] == {
        "customer_id": 2,
        "current": {
            "full_name": "Demo Customer",
            "email": "customer@asd.local",
        },
        "changes": {
            "full_name": "Jordan Lee",
            "email": "jordan.lee@example.test",
        },
        "confirmation_required": True,
    }
    assert "Nothing has been saved" in result["answer"]
    assert all(method == "GET" for _, method, _ in database_calls)


def test_customer_change_requires_one_backend_matched_customer(
    auth_module,
    monkeypatch,
):
    monkeypatch.setattr(auth_module, "database_request", customer_data_request)
    monkeypatch.setattr(
        auth_module,
        "ollama_customer_change",
        lambda prompt: pytest.fail("Ollama must not be called without a target"),
    )

    with auth_module.app.test_client() as client:
        login_session(client)
        response = client.post(
            "/api/admin/ai/customer-insight",
            json={"question": "Change the customer's name to Jordan Lee."},
        )

    assert response.status_code == 422
    assert "current email address or Customer #ID" in response.get_json()["error"]


def test_customer_change_rejects_model_invented_values(
    auth_module,
    monkeypatch,
):
    database_calls = []

    def recorded_database_request(path, method="GET", payload=None):
        database_calls.append((path, method, payload))
        return customer_data_request(path, method, payload)

    monkeypatch.setattr(
        auth_module,
        "database_request",
        recorded_database_request,
    )
    monkeypatch.setattr(
        auth_module,
        "ollama_customer_change",
        lambda prompt: '{"full_name":"Invented Name","email":null}',
    )

    with auth_module.app.test_client() as client:
        login_session(client)
        response = client.post(
            "/api/admin/ai/customer-insight",
            json={
                "question": (
                    "Change the name for customer@asd.local to Jordan Lee."
                )
            },
        )

    assert response.status_code == 422
    assert "could not safely understand" in response.get_json()["error"]
    assert all(method == "GET" for _, method, _ in database_calls)


def test_customer_insight_rejects_unverified_model_output(
    auth_module,
    monkeypatch,
):
    monkeypatch.setattr(auth_module, "database_request", customer_data_request)
    monkeypatch.setattr(
        auth_module,
        "ollama_customer_insight",
        lambda prompt: valid_ai_answer(customer_id=999),
    )

    with auth_module.app.test_client() as client:
        login_session(client)
        response = client.post(
            "/api/admin/ai/customer-insight",
            json={"question": "Find customer 999."},
        )

    assert response.status_code == 502
    assert response.get_json()["error"] == (
        "Customer Insight AI returned an unverified response."
    )


def test_customer_insight_handles_ollama_unavailable(
    auth_module,
    monkeypatch,
):
    monkeypatch.setattr(auth_module, "database_request", customer_data_request)

    def unavailable(prompt):
        raise auth_module.OllamaUnavailableError

    monkeypatch.setattr(auth_module, "ollama_customer_insight", unavailable)

    with auth_module.app.test_client() as client:
        login_session(client)
        response = client.post(
            "/api/admin/ai/customer-insight",
            json={"question": "Summarise customer loyalty."},
        )

    assert response.status_code == 503
    assert "Ollama" in response.get_json()["error"]
    assert auth_module.OLLAMA_MODEL in response.get_json()["error"]


def test_customer_insight_handles_database_unavailable(
    auth_module,
    monkeypatch,
):
    def unavailable_database(path, method="GET", payload=None):
        if path == "/internal/users/1":
            return {"user": admin_user()}
        raise URLError("database unavailable")

    monkeypatch.setattr(
        auth_module,
        "database_request",
        unavailable_database,
    )
    monkeypatch.setattr(
        auth_module,
        "ollama_customer_insight",
        lambda prompt: pytest.fail("Ollama must not be called"),
    )

    with auth_module.app.test_client() as client:
        login_session(client)
        response = client.post(
            "/api/admin/ai/customer-insight",
            json={"question": "Summarise customer loyalty."},
        )

    assert response.status_code == 503
    assert response.get_json()["error"] == (
        "The customer database is unavailable."
    )


def test_customer_insight_validation_rejects_html_and_false_changes(
    auth_module,
):
    records = [{"customer_id": 2}]
    answer = (
        "ANSWER\n<div>I have disabled Customer #2.</div>\n"
        "EVIDENCE\nUnknown\nLIMITATIONS\nNone"
    )

    issues = auth_module.customer_insight_issues(answer, records)

    assert "Do not output HTML." in issues
    assert "Do not claim that any customer data was changed." in issues


def test_customer_insight_preserves_backend_verified_tier_ranking(
    auth_module,
):
    records = [
        {
            "customer_id": 2,
            "email": "two@example.test",
            "account_status": "active",
            "next_tier": "Silver",
            "points_to_next_tier": 250,
        },
        {
            "customer_id": 7,
            "email": "seven@example.test",
            "account_status": "active",
            "next_tier": "Silver",
            "points_to_next_tier": 70,
        },
        {
            "customer_id": 9,
            "email": "nine@example.test",
            "account_status": "active",
            "next_tier": "Gold",
            "points_to_next_tier": 100,
        },
    ]
    focus = auth_module.customer_insight_focus(
        "Which active customers are closest to their next loyalty tier?",
        records,
    )
    incorrect_answer = (
        "ANSWER\nCustomer #2, then Customer #7.\n"
        "EVIDENCE\nSupplied loyalty records.\n"
        "LIMITATIONS\nRead-only data."
    )
    correct_answer = (
        "ANSWER\nCustomer #7, then Customer #9.\n"
        "EVIDENCE\nSupplied loyalty records.\n"
        "LIMITATIONS\nRead-only data."
    )

    incorrect_issues = auth_module.customer_insight_issues(
        incorrect_answer,
        records,
        focus,
    )
    correct_issues = auth_module.customer_insight_issues(
        correct_answer,
        records,
        focus,
    )

    assert focus["ordered_customer_ids"] == [7, 9, 2]
    assert any("backend-verified closest-to-tier" in issue for issue in incorrect_issues)
    assert correct_issues == []
