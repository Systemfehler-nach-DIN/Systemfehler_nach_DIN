"""Official Reddit OAuth submit connector."""

from __future__ import annotations
from typing import Any
from platforms_connectors.base import (
    ConnectorError,
    dry_result,
    env,
    published,
    request_json,
    text,
)

BACKEND = "Reddit OAuth API"


def publish(payload: dict[str, Any], *, dry_run: bool = True) -> dict[str, Any]:
    cfg = payload.get("reddit") if isinstance(payload.get("reddit"), dict) else {}
    subreddit = str(
        cfg.get("subreddit") or __import__("os").getenv("REDDIT_SUBREDDIT", "")
    ).strip()
    endpoint = "https://oauth.reddit.com/api/submit"
    if dry_run:
        return dry_result("reddit", BACKEND, endpoint=endpoint, payload=payload)
    if not subreddit:
        raise ConnectorError("Reddit requires reddit.subreddit or REDDIT_SUBREDDIT")
    token = env("REDDIT_ACCESS_TOKEN")
    user_agent = env("REDDIT_USER_AGENT")
    form = {
        "api_type": "json",
        "sr": subreddit,
        "kind": "self",
        "title": str(payload.get("title") or text(payload)),
        "text": text(payload),
    }
    response = request_json(
        endpoint,
        headers={"Authorization": f"bearer {token}", "User-Agent": user_agent},
        form=form,
    )
    things = response.get("json", {}).get("data", {}).get("things", [])
    external_id = things[0].get("data", {}).get("name") if things else None
    return published("reddit", BACKEND, response, external_id=external_id)
