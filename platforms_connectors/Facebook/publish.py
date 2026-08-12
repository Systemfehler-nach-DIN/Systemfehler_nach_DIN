"""Official Meta Graph API publisher for Facebook Pages."""

from __future__ import annotations
from typing import Any
from platforms_connectors.base import dry_result, env, published, request_json, text

BACKEND = "Meta Graph API / Pages"


def publish(payload: dict[str, Any], *, dry_run: bool = True) -> dict[str, Any]:
    page = env("FACEBOOK_PAGE_ID", required=not dry_run)
    token = env("FACEBOOK_PAGE_ACCESS_TOKEN", required=not dry_run)
    endpoint = f"https://graph.facebook.com/v23.0/{page}/feed"
    if dry_run:
        return dry_result("facebook", BACKEND, endpoint=endpoint, payload=payload)
    form = {
        "access_token": token,
        "message": text(payload),
        "link": payload.get("url") or None,
    }
    return published("facebook", BACKEND, request_json(endpoint, form=form))
