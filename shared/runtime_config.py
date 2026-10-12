"""Public web origins shared by local and cloud API deployments."""

import os
from urllib.parse import urlsplit


def allowed_origins():
    origin = os.getenv("PUBLIC_ORIGIN", "").rstrip("/")
    if not origin:
        return {f"http://localhost:{port}" for port in range(8000, 8006)}
    parsed = urlsplit(origin)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("PUBLIC_ORIGIN must be an HTTP(S) origin without a path.")
    return {origin}
