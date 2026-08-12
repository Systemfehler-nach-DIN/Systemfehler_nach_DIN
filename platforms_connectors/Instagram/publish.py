"""Official Instagram Graph API content publisher."""

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

BACKEND = "Instagram Graph API"


def publish(payload: dict[str, Any], *, dry_run: bool = True) -> dict[str, Any]:
    user = env("INSTAGRAM_USER_ID", required=not dry_run)
    token = env("INSTAGRAM_ACCESS_TOKEN", required=not dry_run)
    endpoint = f"https://graph.facebook.com/v23.0/{user}/media"
    image = media_url(payload)
    if not image:
        raise ConnectorError("Instagram publishing requires media_url")
    if dry_run:
        return dry_result("instagram", BACKEND, endpoint=endpoint, payload=payload)
    params = {"access_token": token, "caption": text(payload)}
    params[
        "video_url"
        if str(payload.get("media_type", "")).lower() == "video"
        else "image_url"
    ] = image
    container = request_json(endpoint, form=params)
    creation_id = container.get("id")
    if not creation_id:
        raise ConnectorError("Instagram media container did not return id")
    result = request_json(
        f"https://graph.facebook.com/v23.0/{user}/media_publish",
        form={"access_token": token, "creation_id": creation_id},
    )
    return published("instagram", BACKEND, result, external_id=result.get("id"))
