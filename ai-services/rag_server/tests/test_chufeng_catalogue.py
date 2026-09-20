"""Main behaviour tests for Chufeng's read-only catalogue source."""

import requests
import pytest

from rag_server.sources.base import SourceDataError, SourceUnavailableError
from rag_server.sources.chufeng_catalogue import ChufengCatalogueSource


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.status_code = 200

    def json(self):
        return self.payload


def product(product_id=1, **changes):
    record = {
        "id": product_id,
        "name": "Mechanical Keyboard",
        "category": "Electronics",
        "description": "Compact keyboard with adjustable backlighting.",
        "price": 109,
        "stock_quantity": 20,
        "status": "active",
        "unit_cost": 40,
        "supplier_id": 9,
        "internal_notes": "must never be indexed",
    }
    record.update(changes)
    return record


def make_source(rag_settings, response_or_error):
    def http_get(*_, **__):
        if isinstance(response_or_error, Exception):
            raise response_or_error
        return response_or_error

    return ChufengCatalogueSource(
        settings_loader=lambda: rag_settings,
        http_get=http_get,
    )


def test_catalogue_records_become_safe_sorted_documents(rag_settings):
    source = make_source(
        rag_settings,
        FakeResponse(
            [
                product(2, name="USB-C Hub", stock_quantity=0),
                product(1),
            ]
        ),
    )

    documents = source.load_documents()

    assert [document.document_id for document in documents] == [
        "chufeng_catalogue:product:1",
        "chufeng_catalogue:product:2",
    ]
    assert "Price: AUD 109.00" in documents[0].text
    assert "Availability: in stock" in documents[0].text
    assert documents[1].metadata["availability"] == "out of stock"
    serialised = repr([document.to_record() for document in documents])
    assert "unit_cost" not in serialised
    assert "supplier_id" not in serialised
    assert "internal_notes" not in serialised


def test_invalid_product_record_is_rejected(rag_settings):
    source = make_source(rag_settings, FakeResponse([product(price=-1)]))

    with pytest.raises(SourceDataError, match="invalid price"):
        source.load_documents()


def test_duplicate_product_ids_are_rejected(rag_settings):
    source = make_source(rag_settings, FakeResponse([product(), product()]))

    with pytest.raises(SourceDataError, match="duplicate product IDs"):
        source.load_documents()


def test_unavailable_product_api_returns_safe_error(rag_settings):
    source = make_source(
        rag_settings,
        requests.ConnectionError("private connection details"),
    )

    with pytest.raises(SourceUnavailableError, match="currently unavailable"):
        source.load_documents()
