"""Read-only RAG knowledge adapter for Chufeng's product catalogue."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Callable

import requests

from rag_server.config import RAGSettings, get_settings
from rag_server.sources.base import (
    KnowledgeDocument,
    KnowledgeSource,
    SourceDataError,
    SourceUnavailableError,
)


CHUFENG_CATALOGUE_SCOPE = "chufeng_catalogue"
CHUFENG_CATALOGUE_SOURCE_NAME = "Chufeng Product Catalogue"
MAX_PRODUCTS = 5000
MAX_TEXT_FIELD_LENGTH = 5000

SettingsLoader = Callable[[], RAGSettings]
HttpGet = Callable[..., Any]


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SourceDataError(
            f"The product service returned an invalid {field_name}."
        )
    cleaned = value.strip()
    if len(cleaned) > MAX_TEXT_FIELD_LENGTH:
        raise SourceDataError(
            f"The product service returned an oversized {field_name}."
        )
    return cleaned


def _optional_text(value: Any, field_name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise SourceDataError(
            f"The product service returned an invalid {field_name}."
        )
    cleaned = value.strip()
    if len(cleaned) > MAX_TEXT_FIELD_LENGTH:
        raise SourceDataError(
            f"The product service returned an oversized {field_name}."
        )
    return cleaned


def _positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SourceDataError(
            f"The product service returned an invalid {field_name}."
        )
    return value


def _stock_quantity(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SourceDataError(
            "The product service returned an invalid stock quantity."
        )
    return value


def _public_price(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise SourceDataError("The product service returned an invalid price.")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise SourceDataError(
            "The product service returned an invalid price."
        ) from exc
    if not amount.is_finite() or amount < 0:
        raise SourceDataError("The product service returned an invalid price.")
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _product_document(product: Any) -> KnowledgeDocument:
    if not isinstance(product, dict):
        raise SourceDataError(
            "The product service returned an invalid product record."
        )

    # This is deliberately a whitelist. Private/internal fields returned by the
    # database API are never copied into either the text or document metadata.
    product_id = _positive_integer(product.get("id"), "product ID")
    name = _required_text(product.get("name"), "product name")
    category = _required_text(product.get("category"), "product category")
    description = _optional_text(product.get("description"), "description")
    price = _public_price(product.get("price"))
    stock_quantity = _stock_quantity(product.get("stock_quantity"))
    status = _optional_text(product.get("status"), "status") or "unknown"
    available = status.casefold() == "active" and stock_quantity > 0
    availability = "in stock" if available else "out of stock"

    description_text = description or "No public description is available."
    text = "\n".join(
        (
            f"Product: {name}",
            f"Category: {category}",
            f"Description: {description_text}",
            f"Price: AUD {price:.2f}",
            f"Availability: {availability}",
            f"Stock quantity: {stock_quantity}",
        )
    )

    return KnowledgeDocument(
        document_id=f"{CHUFENG_CATALOGUE_SCOPE}:product:{product_id}",
        scope=CHUFENG_CATALOGUE_SCOPE,
        source_id=f"product-catalogue:{product_id}",
        citation_label=name,
        text=text,
        metadata={
            "source_type": "product_catalogue",
            "product_id": product_id,
            "product_name": name,
            "category": category,
            "price_aud": float(price),
            "stock_quantity": stock_quantity,
            "availability": availability,
            "public": True,
        },
    )


class ChufengCatalogueSource(KnowledgeSource):
    """Load a safe product snapshot through the Product Database HTTP API."""

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
        return CHUFENG_CATALOGUE_SCOPE

    @property
    def source_name(self) -> str:
        return CHUFENG_CATALOGUE_SOURCE_NAME

    def load_documents(self) -> list[KnowledgeDocument]:
        settings = self._settings_loader()
        request_get = self._http_get or requests.get

        try:
            response = request_get(
                settings.product_database_api_url,
                timeout=settings.request_timeout_seconds,
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise SourceUnavailableError(
                "The product catalogue source is currently unavailable."
            ) from exc
        except requests.RequestException as exc:
            raise SourceUnavailableError(
                "The product catalogue source request failed."
            ) from exc

        status_code = getattr(response, "status_code", None)
        if not isinstance(status_code, int) or not 200 <= status_code < 300:
            raise SourceUnavailableError(
                "The product catalogue source returned an error."
            )

        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise SourceDataError(
                "The product catalogue source returned invalid JSON."
            ) from exc

        if not isinstance(payload, list):
            raise SourceDataError(
                "The product catalogue source returned an invalid product list."
            )
        if len(payload) > MAX_PRODUCTS:
            raise SourceDataError(
                f"The product catalogue source returned more than {MAX_PRODUCTS} products."
            )

        documents: list[KnowledgeDocument] = []
        product_ids: set[int] = set()
        for product in payload:
            document = _product_document(product)
            product_id = int(document.metadata["product_id"])
            if product_id in product_ids:
                raise SourceDataError(
                    "The product catalogue source returned duplicate product IDs."
                )
            product_ids.add(product_id)
            documents.append(document)

        return sorted(
            documents,
            key=lambda document: int(document.metadata["product_id"]),
        )
