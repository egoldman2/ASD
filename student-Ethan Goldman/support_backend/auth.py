"""Session authentication for the standalone Customer Support service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

import requests
from flask import current_app, request


AUTH_SERVICE_URL = "http://ethan-backend:6002"
AUTH_SESSION_COOKIE = "ethan_session"
SESSION_ENDPOINT = "/api/session"
DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_TIMEOUT_SECONDS = 30.0

class AuthError(Exception):
    """Base type for safe expected authentication failures."""


class InvalidSession(AuthError):
    """The request has no valid authenticated session."""


class AuthServiceUnavailable(AuthError):
    """The auth service could not provide a trustworthy answer."""


class PrincipalMalformed(AuthServiceUnavailable):
    """The auth service returned a successful but invalid payload."""


@dataclass(frozen=True)
class Principal:
    """Stable identity extracted from the verified auth response."""

    id: Any
    name: str | None = None
    email: str | None = None
    role: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "full_name": self.name,
            "email": self.email,
            "role": self.role,
        }


def _text(value: Any, *, lower: bool = False) -> str | None:
    if value is None or isinstance(value, (dict, list, tuple, set)):
        return None
    value = str(value).strip()
    if not value:
        return None
    return value.casefold() if lower else value


def normalize_session_payload(payload: Any) -> Principal:
    """Validate the response contract published by the authentication service."""

    if not isinstance(payload, Mapping) or payload.get("authenticated") is not True:
        if isinstance(payload, Mapping) and payload.get("authenticated") is False:
            raise InvalidSession()
        raise PrincipalMalformed()
    user = payload.get("user")
    if not isinstance(user, Mapping):
        raise PrincipalMalformed()

    principal_id = user.get("id")
    if (
        principal_id is None
        or isinstance(principal_id, bool)
        or isinstance(principal_id, (dict, list, tuple, set))
        or (isinstance(principal_id, str) and not principal_id.strip())
    ):
        raise PrincipalMalformed()

    role = _text(user.get("role"), lower=True)
    if role not in {"admin", "customer"}:
        raise PrincipalMalformed()
    return Principal(
        id=principal_id,
        name=_text(user.get("full_name")),
        email=_text(user.get("email"), lower=True),
        role=role,
    )


def _timeout(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = DEFAULT_TIMEOUT_SECONDS
    return min(MAX_TIMEOUT_SECONDS, max(0.1, parsed))


class AuthClient:
    """Bounded client for Customer & Loyalty's session endpoint."""

    def __init__(self, base_url: str | None = None, timeout: Any = None):
        self.base_url = (
            base_url or os.getenv("AUTH_SERVICE_URL", AUTH_SERVICE_URL)
        ).strip().rstrip("/")
        self.timeout = _timeout(
            timeout
            if timeout is not None
            else os.getenv("AUTH_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
        )

    def authenticate(
        self,
        session_cookie: str | None,
        *,
        correlation_id: str | None = None,
    ) -> Principal:
        if not session_cookie or any(char in session_cookie for char in "\r\n"):
            raise InvalidSession()
        headers = (
            {"X-Correlation-ID": correlation_id}
            if correlation_id
            else {}
        )
        try:
            response = requests.get(
                f"{self.base_url}{SESSION_ENDPOINT}",
                cookies={AUTH_SESSION_COOKIE: session_cookie},
                headers=headers,
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise AuthServiceUnavailable() from exc

        status = getattr(response, "status_code", None)
        if not isinstance(status, int):
            raise AuthServiceUnavailable()
        if status in {401, 403, 404}:
            raise InvalidSession()
        if status < 200 or status >= 300:
            raise AuthServiceUnavailable()
        try:
            payload = response.json()
        except (ValueError, TypeError, AttributeError) as exc:
            raise PrincipalMalformed() from exc
        return normalize_session_payload(payload)

def _request_correlation_id() -> str | None:
    value = request.headers.get("X-Correlation-ID", "").strip()
    if not value or len(value) > 80 or any(char in value for char in "\r\n"):
        return None
    return value


def authenticate_request() -> Principal:
    client = AuthClient(
        base_url=current_app.config.get(
            "AUTH_SERVICE_URL", os.getenv("AUTH_SERVICE_URL", AUTH_SERVICE_URL)
        ),
        timeout=current_app.config.get("AUTH_TIMEOUT_SECONDS"),
    )
    cookie_name = current_app.config.get(
        "AUTH_SESSION_COOKIE_NAME", AUTH_SESSION_COOKIE
    )
    return client.authenticate(
        request.cookies.get(cookie_name),
        correlation_id=_request_correlation_id(),
    )
