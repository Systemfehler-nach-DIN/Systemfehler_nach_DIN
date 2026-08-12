"""Official Bluesky AT Protocol publisher."""

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

BACKEND = "Bluesky AT Protocol"


def publish(payload: dict[str, Any], *, dry_run: bool = True) -> dict[str, Any]:
    service = os.getenv("BLUESKY_SERVICE_URL", "https://bsky.social").rstrip("/")
    endpoint = f"{service}/xrpc/com.atproto.repo.createRecord"
    if dry_run:
        return dry_result("bluesky", BACKEND, endpoint=endpoint, payload=payload)
    handle = env("BLUESKY_HANDLE")
    password = env("BLUESKY_APP_PASSWORD")
    session = request_json(
        f"{service}/xrpc/com.atproto.server.createSession",
        data={"identifier": handle, "password": password},
    )
    did, token = session.get("did"), session.get("accessJwt")
    if not did or not token:
        raise ConnectorError("Bluesky session did not return did/accessJwt")
    record = {
        "$type": "app.bsky.feed.post",
        "text": text(payload),
        "createdAt": __import__("datetime")
        .datetime.now(__import__("datetime").timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
    }
    response = request_json(
        endpoint,
        headers={"Authorization": f"Bearer {token}"},
        data={"repo": did, "collection": "app.bsky.feed.post", "record": record},
    )
    return published("bluesky", BACKEND, response, external_id=response.get("uri"))
