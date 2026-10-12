"""Tests for feature-neutral Multi-Agent Server request contracts."""

from dataclasses import FrozenInstanceError
import math

import pytest

from multi_agent_server.contracts import (
    ContractValidationError,
    Feature,
    HumanReviewDecision,
    HumanReviewRequest,
    MAX_EVIDENCE_ITEMS,
    WorkflowRequest,
)


def evidence_item(evidence_id="inventory-product-12", data=None):
    return {
        "evidence_id": evidence_id,
        "source": {
            "service": "inventory-backend",
            "endpoint": "/api/inventory/products/12",
            "retrieved_at": "2026-10-12T10:00:00Z",
        },
        "data": data
        if data is not None
        else {
            "product_id": 12,
            "product_name": "Wireless Mouse",
            "stock_quantity": 3,
            "minimum_stock": 10,
        },
    }


def workflow_payload(feature="inventory", evidence=None):
    return {
        "user_request": " Determine whether product 12 needs restocking. ",
        "feature": feature,
        "evidence": evidence or [evidence_item()],
    }


def assert_contract_error(payload, code, field):
    with pytest.raises(ContractValidationError) as caught:
        WorkflowRequest.from_dict(payload)
    assert caught.value.code == code
    assert caught.value.field == field


def test_inventory_request_is_parsed_trimmed_and_serialised():
    request = WorkflowRequest.from_dict(workflow_payload())

    assert request.user_request == "Determine whether product 12 needs restocking."
    assert request.feature is Feature.INVENTORY
    assert request.evidence[0].source.service == "inventory-backend"
    assert request.to_dict() == {
        "user_request": "Determine whether product 12 needs restocking.",
        "feature": "inventory",
        "evidence": [evidence_item()],
    }


@pytest.mark.parametrize("feature", [member.value for member in Feature])
def test_all_release_two_features_use_the_same_contract(feature):
    request = WorkflowRequest.from_dict(
        workflow_payload(
            feature=feature,
            evidence=[
                evidence_item(
                    evidence_id=f"{feature}-evidence",
                    data={
                        "feature_specific_field": feature,
                        "nested": {"items": [1, True, None]},
                    },
                )
            ],
        )
    )

    assert request.feature.value == feature
    assert request.evidence[0].to_dict()["data"]["feature_specific_field"] == feature


def test_multiple_evidence_sources_are_supported():
    first = evidence_item()
    second = evidence_item(
        "supplier-product-12", {"supplier_stock": 50, "lead_days": 2}
    )
    second["source"] = {
        "service": "supplier-backend",
        "endpoint": "https://supplier.example/api/products/12?include=stock",
        "retrieved_at": "2026-10-12T18:00:00+08:00",
    }

    request = WorkflowRequest.from_dict(workflow_payload(evidence=[first, second]))

    assert len(request.evidence) == 2
    assert request.evidence[1].source.service == "supplier-backend"


def test_contracts_are_immutable_and_copy_nested_input():
    payload = workflow_payload()
    request = WorkflowRequest.from_dict(payload)
    payload["evidence"][0]["data"]["stock_quantity"] = 999

    assert request.evidence[0].data["stock_quantity"] == 3
    with pytest.raises(FrozenInstanceError):
        request.feature = Feature.CUSTOMER_SUPPORT
    with pytest.raises(TypeError):
        request.evidence[0].data["stock_quantity"] = 999


@pytest.mark.parametrize(
    ("payload", "code", "field"),
    [
        (None, "invalid_type", "request"),
        ({"feature": "inventory", "evidence": [evidence_item()]},
         "invalid_type", "user_request"),
        (workflow_payload(feature="unknown"), "invalid_choice", "feature"),
        ({**workflow_payload(), "evidence": {}}, "invalid_type", "evidence"),
        ({**workflow_payload(), "evidence": []}, "required_field", "evidence"),
        (workflow_payload(evidence=[{"evidence_id": "x"}]),
         "invalid_type", "evidence[0].data"),
        (workflow_payload(evidence=[evidence_item(data={})]),
         "required_field", "evidence[0].data"),
    ],
)
def test_invalid_top_level_shapes_are_rejected(payload, code, field):
    assert_contract_error(payload, code, field)


def test_duplicate_evidence_ids_are_rejected():
    item = evidence_item("duplicate")
    assert_contract_error(
        workflow_payload(evidence=[item, evidence_item("duplicate")]),
        "duplicate_evidence_id",
        "evidence",
    )


def test_too_many_evidence_items_are_rejected():
    items = [evidence_item(str(index)) for index in range(MAX_EVIDENCE_ITEMS + 1)]
    assert_contract_error(
        workflow_payload(evidence=items), "too_many_items", "evidence"
    )


@pytest.mark.parametrize(
    ("retrieved_at", "valid"),
    [
        ("2026-10-12T10:00:00Z", True),
        ("2026-10-12T18:00:00+08:00", True),
        ("2026-10-12T10:00:00", False),
        ("yesterday", False),
    ],
)
def test_evidence_timestamp_requires_iso_8601_timezone(retrieved_at, valid):
    item = evidence_item()
    item["source"]["retrieved_at"] = retrieved_at
    if valid:
        assert WorkflowRequest.from_dict(workflow_payload(evidence=[item]))
    else:
        assert_contract_error(
            workflow_payload(evidence=[item]),
            "invalid_timestamp",
            "evidence[0].source.retrieved_at",
        )


@pytest.mark.parametrize(
    "endpoint",
    ["inventory/products/12", "ftp://example.test/item", "//example.test/item"],
)
def test_invalid_source_endpoints_are_rejected(endpoint):
    item = evidence_item()
    item["source"]["endpoint"] = endpoint
    assert_contract_error(
        workflow_payload(evidence=[item]),
        "invalid_endpoint",
        "evidence[0].source.endpoint",
    )


@pytest.mark.parametrize("bad_value", [math.inf, math.nan, {1: "bad"}, {1, 2}])
def test_non_json_evidence_values_are_rejected(bad_value):
    item = evidence_item(data={"bad": bad_value})
    with pytest.raises(ContractValidationError):
        WorkflowRequest.from_dict(workflow_payload(evidence=[item]))


def test_overly_deep_evidence_is_rejected():
    nested = "value"
    for _ in range(12):
        nested = {"nested": nested}
    item = evidence_item(data={"root": nested})

    with pytest.raises(ContractValidationError) as caught:
        WorkflowRequest.from_dict(workflow_payload(evidence=[item]))

    assert caught.value.code == "json_too_deep"


@pytest.mark.parametrize(
    ("decision", "expected"),
    [(member.value, member) for member in HumanReviewDecision],
)
def test_human_review_decisions_are_validated(decision, expected):
    review = HumanReviewRequest.from_dict(
        {
            "decision": decision,
            "reason": " Evidence checked by a team member. ",
            "reviewed_by": " Chufeng ",
        }
    )

    assert review.decision is expected
    assert review.reason == "Evidence checked by a team member."
    assert review.reviewed_by == "Chufeng"
    assert review.to_dict()["decision"] == decision


def test_invalid_human_review_returns_client_safe_error():
    with pytest.raises(ContractValidationError) as caught:
        HumanReviewRequest.from_dict(
            {"decision": "maybe", "reason": "ok", "reviewed_by": "tester"}
        )

    assert caught.value.to_dict() == {
        "error": {
            "code": "invalid_choice",
            "field": "decision",
            "message": "must be one of: accept, partially_accept, reject.",
        }
    }
