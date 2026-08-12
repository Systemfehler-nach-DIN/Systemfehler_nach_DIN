"""Official Pinterest API v5 pin creator."""

from __future__ import annotations
from typing import Any
from platforms_connectors.base import (
    ConnectorError,
    dry_result,
    env,
    media_url,
    published,
    request_json,
    text,
)

BACKEND = "Pinterest API v5"


def publish(payload: dict[str, Any], *, dry_run: bool = True) -> dict[str, Any]:
    endpoint = "https://api.pinterest.com/v5/pins"
    if dry_run:
        return dry_result("pinterest", BACKEND, endpoint=endpoint, payload=payload)
    token = env("PINTEREST_ACCESS_TOKEN")
    board = env("PINTEREST_BOARD_ID")
    image = media_url(payload)
    if not image:
        raise ConnectorError("Pinterest requires media_url")
    body = {
        "board_id": board,
        "title": str(payload.get("title") or text(payload))[:100],
        "description": text(payload),
        "link": payload.get("url") or None,
        "media_source": {"source_type": "image_url", "url": image},
    }
    return published(
        "pinterest",
        BACKEND,
        request_json(endpoint, headers={"Authorization": f"Bearer {token}"}, data=body),
    )
