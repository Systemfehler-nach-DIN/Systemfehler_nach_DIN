"""Official Threads API publisher."""

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

BACKEND = "Threads API"


def publish(payload: dict[str, Any], *, dry_run: bool = True) -> dict[str, Any]:
    user = env("THREADS_USER_ID", required=not dry_run)
    token = env("THREADS_ACCESS_TOKEN", required=not dry_run)
    endpoint = f"https://graph.threads.net/v1.0/{user}/threads"
    if dry_run:
        return dry_result("threads", BACKEND, endpoint=endpoint, payload=payload)
    form = {"access_token": token, "media_type": "TEXT", "text": text(payload)}
    if media_url(payload):
        form.update(media_type="IMAGE", image_url=media_url(payload))
    draft = request_json(endpoint, form=form)
    creation_id = draft.get("id")
    if not creation_id:
        raise ConnectorError("Threads container did not return id")
    result = request_json(
        f"https://graph.threads.net/v1.0/{user}/threads_publish",
        form={"access_token": token, "creation_id": creation_id},
    )
    return published("threads", BACKEND, result)
