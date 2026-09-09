import os

import requests


class DatabaseServiceError(Exception):
    def __init__(self, message, status_code=503, payload=None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {"error": message}


def database_request(method, path, **kwargs):
    base_url = os.getenv(
        "PRODUCT_DATABASE_API_URL", "http://127.0.0.1:6001/api/database"
    ).rstrip("/")
    try:
        response = requests.request(
            method, f"{base_url}/{path.lstrip('/')}", timeout=5, **kwargs
        )
    except requests.RequestException as exc:
        raise DatabaseServiceError("Product database service is unavailable.") from exc

    if response.status_code == 204:
        return None
    try:
        payload = response.json()
    except ValueError as exc:
        raise DatabaseServiceError("Product database returned an invalid response.", 502) from exc
    if not response.ok:
        raise DatabaseServiceError(
            payload.get("error", "Product database request failed."),
            response.status_code,
            payload,
        )
    return payload
