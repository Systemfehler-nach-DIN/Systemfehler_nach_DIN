"""Official Discord incoming webhook publisher."""

from __future__ import annotations
from typing import Any
from platforms_connectors.base import dry_result, env, request_json, text

BACKEND = "Discord Webhook API"


def publish(payload: dict[str, Any], *, dry_run: bool = True) -> dict[str, Any]:
    endpoint = "<DISCORD_WEBHOOK_URL>" if dry_run else env("DISCORD_WEBHOOK_URL")
    endpoint = (
        endpoint + ("&" if "?" in endpoint else "?") + "wait=true"
        if not dry_run
        else endpoint
    )
    if dry_run:
        return dry_result("discord", BACKEND, endpoint=endpoint, payload=payload)
    response = request_json(
        endpoint, data={"content": text(payload), "allowed_mentions": {"parse": []}}
    )
    return {
        "platform": "discord",
        "backend": BACKEND,
        "mode": "LIVE",
        "published": True,
        "validated": True,
        "external_id": response.get("id"),
    }
