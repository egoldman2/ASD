"""Read-only RAG knowledge adapter for Ryan's inventory management feature."""

from __future__ import annotations

from typing import Any, Callable

import requests

from rag_server.config import RAGSettings, get_settings
from rag_server.sources.base import (
    KnowledgeDocument,
    KnowledgeSource,
    SourceDataError,
    SourceUnavailableError,
)


RYAN_INVENTORY_SCOPE = "ryan_inventory"
RYAN_INVENTORY_SOURCE_NAME = "Ryan Inventory Management"
MAX_RECORDS = 5000
MAX_TEXT_FIELD_LENGTH = 5000

SettingsLoader = Callable[[], RAGSettings]
HttpGet = Callable[..., Any]


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SourceDataError(
            f"The inventory data source returned an invalid {field_name}."
        )
    cleaned = value.strip()
    if len(cleaned) > MAX_TEXT_FIELD_LENGTH:
        raise SourceDataError(
            f"The inventory data source returned an oversized {field_name}."
        )
    return cleaned


def _optional_text(value: Any, field_name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise SourceDataError(
            f"The inventory data source returned an invalid {field_name}."
        )
    cleaned = value.strip()
    if len(cleaned) > MAX_TEXT_FIELD_LENGTH:
        raise SourceDataError(
            f"The inventory data source returned an oversized {field_name}."
        )
    return cleaned


def _positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SourceDataError(
            f"The inventory data source returned an invalid {field_name}."
        )
    return value


def _non_negative_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SourceDataError(
            f"The inventory data source returned an invalid {field_name}."
        )
    return value

def _product_document(product: Any) -> KnowledgeDocument:
    if not isinstance(product, dict):
        raise SourceDataError(
            "The inventory data source returned an invalid product record."
        )

    # Whitelist only. unit_cost and other internal-only fields are never
    # copied into either the text or the document metadata.
    product_id = _positive_integer(product.get("id"), "product ID")
    name = _required_text(product.get("name"), "product name")
    category = _required_text(product.get("category"), "product category")
    stock_quantity = _non_negative_integer(
        product.get("stock_quantity"), "stock quantity"
    )
    reorder_threshold = _non_negative_integer(
        product.get("reorder_threshold"), "reorder threshold"
    )
    reorder_quantity = _non_negative_integer(
        product.get("reorder_quantity"), "reorder quantity"
    )
    status = _optional_text(product.get("status"), "status") or "unknown"
    supplier_name = _optional_text(product.get("supplier_name"), "supplier name")
    last_restocked_at = _optional_text(
        product.get("last_restocked_at"), "last restocked date"
    )

    needs_reorder = stock_quantity <= reorder_threshold
    supplier_line = (
        f"Supplier: {supplier_name}"
        if supplier_name
        else "Supplier: unassigned"
    )
    restocked_line = (
        f"Last restocked: {last_restocked_at}"
        if last_restocked_at
        else "Last restocked: never restocked since being added"
    )

    # The two branches deliberately use different vocabulary. Repeating
    # "reorder"/"restock" in both the needed and not-needed case would make
    # every product's document look equally relevant to a "reorder" query
    # under the shared hash-based embedder, so only products that actually
    # need reordering carry that vocabulary.
    if needs_reorder:
        summary_sentence = (
            f"{name} needs to be reordered and restocked. Only "
            f"{stock_quantity} units remain, at or below the reorder "
            f"threshold of {reorder_threshold} units. Order "
            f"{reorder_quantity} units from {supplier_name or 'its supplier'}."
        )
    else:
        summary_sentence = (
            f"{name} has {stock_quantity} units on hand, comfortably above "
            f"its minimum stocking level of {reorder_threshold} units."
        )

    text = "\n".join(
        (
            summary_sentence,
            f"Product: {name}",
            f"Category: {category}",
            f"Status: {status}",
            f"Current stock quantity: {stock_quantity} units",
            f"Minimum stocking threshold: {reorder_threshold} units",
            supplier_line,
            restocked_line,
        )
    )

    return KnowledgeDocument(
        document_id=f"{RYAN_INVENTORY_SCOPE}:product:{product_id}",
        scope=RYAN_INVENTORY_SCOPE,
        source_id=f"inventory-product:{product_id}",
        citation_label=f"{name} (inventory record)",
        text=text,
        metadata={
            "source_type": "inventory_product",
            "product_id": product_id,
            "product_name": name,
            "category": category,
            "stock_quantity": stock_quantity,
            "reorder_threshold": reorder_threshold,
            "reorder_quantity": reorder_quantity,
            "needs_reorder": needs_reorder,
            "supplier_name": supplier_name or "unassigned",
        },
    )


def _supplier_document(supplier: Any, supplied_product_names: list[str]) -> KnowledgeDocument:
    if not isinstance(supplier, dict):
        raise SourceDataError(
            "The inventory data source returned an invalid supplier record."
        )

    supplier_id = _positive_integer(supplier.get("id"), "supplier ID")
    name = _required_text(supplier.get("name"), "supplier name")
    contact_name = _optional_text(supplier.get("contact_name"), "contact name")
    address = _optional_text(supplier.get("address"), "address")

    contact_line = (
        f"Contact person: {contact_name}"
        if contact_name
        else "Contact person: not on file"
    )
    address_line = f"Address: {address}" if address else "Address: not on file"
    products_line = (
        "Supplies: " + ", ".join(supplied_product_names)
        if supplied_product_names
        else "Supplies: no products currently assigned to this supplier"
    )

    # Email and phone are deliberately excluded from the indexed text so a
    # RAG answer never surfaces direct contact details; that data stays
    # available only through the authenticated MCP supplier-details tool.
    text = "\n".join(
        (
            f"Supplier: {name}",
            contact_line,
            address_line,
            products_line,
        )
    )

    return KnowledgeDocument(
        document_id=f"{RYAN_INVENTORY_SCOPE}:supplier:{supplier_id}",
        scope=RYAN_INVENTORY_SCOPE,
        source_id=f"inventory-supplier:{supplier_id}",
        citation_label=f"{name} (supplier record)",
        text=text,
        metadata={
            "source_type": "inventory_supplier",
            "supplier_id": supplier_id,
            "supplier_name": name,
            "product_count": len(supplied_product_names),
        },
    )


class RyanInventorySource(KnowledgeSource):
    """Load inventory and supplier snapshots through the Product Database API."""

    def __init__(
        self,
        *,
        settings_loader: SettingsLoader = get_settings,
        http_get: HttpGet | None = None,
    ) -> None:
        self._settings_loader = settings_loader
        self._http_get = http_get

    @property
    def scope(self) -> str:
        return RYAN_INVENTORY_SCOPE

    @property
    def source_name(self) -> str:
        return RYAN_INVENTORY_SOURCE_NAME

    def _get(self, url: str, settings: RAGSettings) -> Any:
        request_get = self._http_get or requests.get
        try:
            response = request_get(url, timeout=settings.request_timeout_seconds)
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise SourceUnavailableError(
                "The inventory data source is currently unavailable."
            ) from exc
        except requests.RequestException as exc:
            raise SourceUnavailableError(
                "The inventory data source request failed."
            ) from exc

        status_code = getattr(response, "status_code", None)
        if not isinstance(status_code, int) or not 200 <= status_code < 300:
            raise SourceUnavailableError(
                "The inventory data source returned an error."
            )
        try:
            return response.json()
        except (TypeError, ValueError) as exc:
            raise SourceDataError(
                "The inventory data source returned invalid JSON."
            ) from exc

    def load_documents(self) -> list[KnowledgeDocument]:
        settings = self._settings_loader()
        base_url = settings.product_database_api_url.rstrip("/")
        # product_database_api_url points at .../api/database/products;
        # suppliers is a sibling collection under the same API root.
        products_url = base_url
        suppliers_url = base_url.rsplit("/", 1)[0] + "/suppliers"

        products_payload = self._get(products_url, settings)
        if not isinstance(products_payload, list):
            raise SourceDataError(
                "The inventory data source returned an invalid product list."
            )
        if len(products_payload) > MAX_RECORDS:
            raise SourceDataError(
                f"The inventory data source returned more than {MAX_RECORDS} products."
            )

        suppliers_payload = self._get(suppliers_url, settings)
        if not isinstance(suppliers_payload, list):
            raise SourceDataError(
                "The inventory data source returned an invalid supplier list."
            )
        if len(suppliers_payload) > MAX_RECORDS:
            raise SourceDataError(
                f"The inventory data source returned more than {MAX_RECORDS} suppliers."
            )

        documents: list[KnowledgeDocument] = []
        seen_ids: set[str] = set()

        product_ids: set[int] = set()
        products_by_supplier: dict[int, list[str]] = {}
        for product in products_payload:
            document = _product_document(product)
            product_id = int(document.metadata["product_id"])
            if product_id in product_ids:
                raise SourceDataError(
                    "The inventory data source returned duplicate product IDs."
                )
            product_ids.add(product_id)
            seen_ids.add(document.document_id)
            documents.append(document)

            supplier_id = product.get("supplier_id")
            if isinstance(supplier_id, int) and not isinstance(supplier_id, bool):
                products_by_supplier.setdefault(supplier_id, []).append(
                    document.metadata["product_name"]
                )

        supplier_ids: set[int] = set()
        for supplier in suppliers_payload:
            supplier_id_value = supplier.get("id") if isinstance(supplier, dict) else None
            document = _supplier_document(
                supplier,
                products_by_supplier.get(supplier_id_value, []),
            )
            supplier_id = int(document.metadata["supplier_id"])
            if supplier_id in supplier_ids:
                raise SourceDataError(
                    "The inventory data source returned duplicate supplier IDs."
                )
            supplier_ids.add(supplier_id)
            seen_ids.add(document.document_id)
            documents.append(document)

        return sorted(documents, key=lambda document: document.document_id)