"""Buffer GraphQL publishing adapter.

The adapter is intentionally one-channel-per-call. Account keys and channel
IDs are runtime configuration from Infisical; no credentials are stored here.
"""

from __future__ import annotations

import json
import os
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

BACKEND = "Buffer API (GraphQL)"
ENDPOINT = "https://api.buffer.com"


def _input(payload: dict[str, Any]) -> dict[str, Any]:
    cfg = payload.get("buffer") if isinstance(payload.get("buffer"), dict) else {}
    channel_id = str(
        cfg.get("channel_id") or os.getenv("BUFFER_CHANNEL_ID", "")
    ).strip()
    if not channel_id:
        raise ConnectorError("Buffer requires buffer.channel_id or BUFFER_CHANNEL_ID")
    service = str(cfg.get("service") or os.getenv("BUFFER_SERVICE", "")).lower().strip()
    if not service:
        raise ConnectorError("Buffer requires buffer.service or BUFFER_SERVICE")
    value: dict[str, Any] = {
        "channelId": channel_id,
        "schedulingType": str(cfg.get("scheduling_type") or "automatic"),
        "mode": str(cfg.get("mode") or "addToQueue"),
        "text": text(payload),
    }
    due_at = cfg.get("due_at") or os.getenv("BUFFER_DUE_AT")
    if due_at:
        value["dueAt"] = str(due_at)
    asset = media_url(payload)
    if asset:
        media_type = str(
            cfg.get("media_type") or payload.get("media_type") or "image"
        ).lower()
        value["assets"] = [
            {"video" if media_type == "video" else "image": {"url": asset}}
        ]
    metadata: dict[str, Any] = {}
    if service == "instagram":
        metadata["instagram"] = {
            "type": str(cfg.get("instagram_type") or "post"),
            "shouldShareToFeed": bool(cfg.get("should_share_to_feed", True)),
        }
    elif service == "facebook":
        metadata["facebook"] = {"type": str(cfg.get("facebook_type") or "post")}
    elif service == "pinterest":
        board = str(
            cfg.get("board_service_id") or os.getenv("BUFFER_BOARD_SERVICE_ID", "")
        ).strip()
        if board:
            metadata["pinterest"] = {"boardServiceId": board}
    if metadata:
        value["metadata"] = metadata
    return value


def publish(payload: dict[str, Any], *, dry_run: bool = True) -> dict[str, Any]:
    value = _input(payload)
    if dry_run:
        return dry_result("buffer", BACKEND, endpoint=ENDPOINT, payload=payload)
    key = env("BUFFER_API_KEY")
    query = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        __typename
        ... on PostActionSuccess { post { id status dueAt } }
        ... on NotFoundError { message }
        ... on UnauthorizedError { message }
        ... on UnexpectedError { message }
        ... on RestProxyError { message }
        ... on LimitReachedError { message }
        ... on InvalidInputError { message }
      }
    }
    """
    response = request_json(
        ENDPOINT,
        headers={"Authorization": f"Bearer {key}"},
        data={"query": query, "variables": {"input": value}},
    )
    if response.get("errors"):
        raise ConnectorError("Buffer GraphQL request returned an error")
    result = response.get("data", {}).get("createPost", {})
    if result.get("__typename") != "PostActionSuccess":
        raise ConnectorError(str(result.get("message") or "Buffer rejected post"))
    post = result.get("post") or {}
    return published("buffer", BACKEND, post, external_id=post.get("id"))
