"""Official Mastodon REST API status publisher."""

from __future__ import annotations
import os
from typing import Any
from platforms_connectors.base import dry_result, env, published, request_json, text

BACKEND = "Mastodon REST API"


def publish(payload: dict[str, Any], *, dry_run: bool = True) -> dict[str, Any]:
    base = os.getenv("MASTODON_BASE_URL", "https://mastodon.social").rstrip("/")
    endpoint = f"{base}/api/v1/statuses"
    if dry_run:
        return dry_result("mastodon", BACKEND, endpoint=endpoint, payload=payload)
    token = env("MASTODON_ACCESS_TOKEN")
    return published(
        "mastodon",
        BACKEND,
        request_json(
            endpoint,
            headers={"Authorization": f"Bearer {token}"},
            form={
                "status": text(payload),
                "visibility": payload.get("visibility", "public"),
            },
        ),
    )
