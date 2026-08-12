"""Official X API v2 publisher (user-context access token)."""

from __future__ import annotations
from typing import Any
from platforms_connectors.base import dry_result, env, published, request_json, text

BACKEND = "X API v2"


def publish(payload: dict[str, Any], *, dry_run: bool = True) -> dict[str, Any]:
    endpoint = "https://api.x.com/2/tweets"
    if dry_run:
        return dry_result("x", BACKEND, endpoint=endpoint, payload=payload)
    token = env("X_ACCESS_TOKEN")
    body: dict[str, Any] = {"text": text(payload)}
    media_ids = (
        payload.get("x", {}).get("media_ids")
        if isinstance(payload.get("x"), dict)
        else None
    )
    if media_ids:
        body["media"] = {"media_ids": list(media_ids)}
    response = request_json(
        endpoint, headers={"Authorization": f"Bearer {token}"}, data=body
    )
    return published("x", BACKEND, response.get("data", response))
