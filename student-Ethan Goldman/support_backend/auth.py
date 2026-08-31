"""Session authentication for the standalone Customer Support service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Mapping, TypeVar, cast

import requests
from flask import Flask, Response, current_app, g, jsonify, request


AUTH_SERVICE_URL = "http://ethan-backend:6002"
AUTH_SESSION_COOKIE = "ethan_session"
SESSION_ENDPOINT = "/api/session"
DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_TIMEOUT_SECONDS = 30.0

F = TypeVar("F", bound=Callable[..., Any])


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
    principal = client.authenticate(
        request.cookies.get(cookie_name),
        correlation_id=_request_correlation_id(),
    )
    return set_current_principal(principal)


def set_current_principal(principal: Principal) -> Principal:
    g.principal = principal
    return principal


def get_current_principal() -> Principal:
    principal = getattr(g, "principal", None)
    if not isinstance(principal, Principal):
        raise InvalidSession()
    return principal


def _auth_error(error: AuthError) -> tuple[Response, int]:
    if isinstance(error, AuthServiceUnavailable):
        return jsonify({"error": "Authentication service unavailable."}), 503
    return jsonify({"error": "You must sign in."}), 401


def auth_required(function: F) -> F:
    @wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        try:
            authenticate_request()
        except AuthError as error:
            return _auth_error(error)
        return function(*args, **kwargs)

    return cast(F, wrapped)


def role_required(*roles: str) -> Callable[[F], F]:
    allowed = {str(role).strip().casefold() for role in roles}
    if not allowed:
        raise ValueError("At least one role is required")

    def decorator(function: F) -> F:
        @wraps(function)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            try:
                principal = authenticate_request()
            except AuthError as error:
                return _auth_error(error)
            if (principal.role or "").casefold() not in allowed:
                return jsonify({"error": "You do not have permission for this resource."}), 403
            return function(*args, **kwargs)

        return cast(F, wrapped)

    return decorator


customer_required = role_required("customer")
admin_required = role_required("admin")
