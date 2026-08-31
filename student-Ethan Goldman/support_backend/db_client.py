"""HTTP client for the separately owned Customer Support database service."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

import requests


DEFAULT_DATABASE_API_URL = "http://customer-support-database:6006"
DEFAULT_TICKETS_PATH = "/api/tickets"
MAX_TIMEOUT_SECONDS = 15.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class SupportDatabaseError(Exception):
    """Base error with a safe public status and message."""

    status_code = 502
    public_message = "The support database could not complete the request."

    def __init__(self, *_args: Any, status_code: int | None = None):
        self.status_code = status_code or type(self).status_code
        super().__init__(type(self).public_message)


class DatabaseBadRequestError(SupportDatabaseError):
    status_code = 400
    public_message = "The support database rejected the request."


class DatabaseNotFoundError(SupportDatabaseError):
    status_code = 404
    public_message = "The requested support record was not found."


class DatabaseConflictError(SupportDatabaseError):
    status_code = 409
    public_message = "The support database reported a conflict."


class DatabaseServerError(SupportDatabaseError):
    status_code = 502
    public_message = "The support database is temporarily unavailable."


class DatabaseUnavailableError(SupportDatabaseError):
    status_code = 503
    public_message = "The support database is unavailable."


class DatabaseMalformedResponseError(SupportDatabaseError):
    status_code = 502
    public_message = "The support database returned an invalid response."


def _bounded_timeout(value: Any) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 5.0
    return min(MAX_TIMEOUT_SECONDS, max(0.1, value))


def _valid_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("SUPPORT_DATABASE_API_URL must be an HTTP(S) URL")
    return value.rstrip("/")


def _ticket_id(ticket_id: Any) -> int:
    if isinstance(ticket_id, bool):
        raise ValueError("ticket_id must be a positive integer")
    try:
        parsed = int(ticket_id)
    except (TypeError, ValueError):
        raise ValueError("ticket_id must be a positive integer") from None
    if parsed < 1 or str(parsed) != str(ticket_id).strip():
        raise ValueError("ticket_id must be a positive integer")
    return parsed


class SupportDatabaseClient:
    """Small bounded HTTP client with status-safe upstream translation."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: Any = None,
    ):
        self.base_url = _valid_base_url(
            base_url
            or os.getenv("SUPPORT_DATABASE_API_URL", DEFAULT_DATABASE_API_URL)
        )
        self.timeout = _bounded_timeout(
            timeout if timeout is not None else os.getenv("SUPPORT_DATABASE_TIMEOUT", 5)
        )
        self.tickets_path = DEFAULT_TICKETS_PATH

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        payload: Mapping[str, Any] | None = None,
        expected: tuple[int, ...] = (200, 201),
    ) -> Any:
        url = f"{self.base_url}{path}"
        params = {
            str(key): str(value)
            for key, value in (query or {}).items()
            if value is not None and value != ""
        }
        headers = {"Accept": "application/json"}
        try:
            response = requests.request(
                method.upper(),
                url,
                params=params or None,
                json=dict(payload) if payload is not None else None,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise DatabaseUnavailableError() from exc

        status = getattr(response, "status_code", None)
        if not isinstance(status, int):
            raise DatabaseUnavailableError()
        if status not in expected:
            if status == 400:
                raise DatabaseBadRequestError()
            if status == 404:
                raise DatabaseNotFoundError()
            if status == 409:
                raise DatabaseConflictError()
            if 500 <= status <= 599:
                raise DatabaseServerError()
            raise SupportDatabaseError(status_code=502)
        if status == 204:
            return None

        raw = getattr(response, "content", b"")
        if isinstance(raw, (bytes, bytearray)) and len(raw) > MAX_RESPONSE_BYTES:
            raise DatabaseMalformedResponseError()
        try:
            result = response.json()
        except (ValueError, TypeError, AttributeError) as exc:
            raise DatabaseMalformedResponseError() from exc
        if not isinstance(result, (Mapping, list)):
            raise DatabaseMalformedResponseError()
        return result

    def list_tickets(
        self,
        *,
        customer_user_id: Any = None,
        filters: Mapping[str, Any] | None = None,
    ) -> Any:
        query = dict(filters or {})
        if customer_user_id is not None:
            query["owner_user_id"] = customer_user_id
        return self._request("GET", self.tickets_path, query=query, expected=(200,))

    def get_ticket(self, ticket_id: Any, *, customer_user_id: Any = None) -> Any:
        query = (
            {"owner_user_id": customer_user_id}
            if customer_user_id is not None
            else None
        )
        return self._request(
            "GET",
            f"{self.tickets_path}/{_ticket_id(ticket_id)}",
            query=query,
            expected=(200,),
        )

    def create_ticket(
        self,
        *,
        customer_user_id: Any,
        customer_name_snapshot: str,
        customer_email_snapshot: str,
        subject: str,
        message: str,
    ) -> Any:
        return self._request(
            "POST",
            self.tickets_path,
            payload={
                "customer_user_id": customer_user_id,
                "customer_name_snapshot": customer_name_snapshot,
                "customer_email_snapshot": customer_email_snapshot,
                "subject": subject,
                "message": message,
            },
            expected=(200, 201),
        )

    def update_ticket(self, ticket_id: Any, updates: Mapping[str, Any]) -> Any:
        return self._request(
            "PUT",
            f"{self.tickets_path}/{_ticket_id(ticket_id)}",
            payload=updates,
            expected=(200, 204),
        )

    def delete_ticket(self, ticket_id: Any) -> Any:
        return self._request(
            "DELETE",
            f"{self.tickets_path}/{_ticket_id(ticket_id)}",
            expected=(200, 204),
        )

    def create_message(
        self,
        ticket_id: Any,
        *,
        message: str,
        sender_role: str,
        author_name: str,
        customer_user_id: Any = None,
    ) -> Any:
        payload: dict[str, Any] = {
            "message": message,
            "sender_role": sender_role,
            "author_name": author_name,
        }
        if customer_user_id is not None:
            payload["owner_user_id"] = customer_user_id
        return self._request(
            "POST",
            f"{self.tickets_path}/{_ticket_id(ticket_id)}/messages",
            payload=payload,
            expected=(200, 201),
        )
