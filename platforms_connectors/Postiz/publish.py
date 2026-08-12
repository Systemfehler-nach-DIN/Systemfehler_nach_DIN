"""Optional Postiz API adapter; canonical connectors remain authoritative."""

from __future__ import annotations
import os
from typing import Any
from platforms_connectors.base import (
    ConnectorError,
    dry_result,
    env,
    published,
    request_json,
    text,
)

BACKEND = "Postiz self-hosted API (optional)"


def publish(payload: dict[str, Any], *, dry_run: bool = True) -> dict[str, Any]:
    endpoint = os.getenv("POSTIZ_API_URL", "http://127.0.0.1:5000/api/posts").rstrip(
        "/"
    )
    if dry_run:
        return dry_result("postiz", BACKEND, endpoint=endpoint, payload=payload)
    token = env("POSTIZ_API_TOKEN")
    channels = payload.get("platforms") or payload.get("postiz", {}).get("platforms")
    if not channels:
        raise ConnectorError("Postiz requires explicit target platforms")
    result = request_json(
        endpoint,
        headers={"Authorization": f"Bearer {token}"},
        data={"content": text(payload), "platforms": channels, "publish": False},
    )
    return published("postiz", BACKEND, result)
