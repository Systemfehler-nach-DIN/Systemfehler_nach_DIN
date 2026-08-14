"""Buffer GraphQL publishing adapter.

The adapter is intentionally one-channel-per-call. Account keys and channel
IDs are runtime configuration from Infisical; no credentials are stored here.
"""

from __future__ import annotations

import os
from typing import Any

from platforms_connectors.base import (
    ConnectorError,
    dry_result,
    env,
    media_url,
    request_json,
    text,
)

BACKEND = "Buffer API (GraphQL)"
ENDPOINT = "https://api.buffer.com"


def _registry_target(cfg: dict[str, Any]) -> dict[str, Any]:
    from .router import channel_for

    platform = str(cfg.get("platform") or cfg.get("service") or "").strip().lower()
    if not platform:
        raise ConnectorError("Buffer requires buffer.platform or buffer.service")
    try:
        registered = channel_for(platform, cfg.get("account"))
    except KeyError as exc:
        raise ConnectorError(str(exc)) from exc
    return {**registered, **cfg}


def _targets(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("buffer_targets")
    if isinstance(raw, list):
        if not raw:
            raise ConnectorError("buffer_targets must not be empty")
        return [_registry_target(x) if isinstance(x, dict) else {} for x in raw]
    cfg = payload.get("buffer") if isinstance(payload.get("buffer"), dict) else {}
    if cfg.get("channel_id"):
        return [dict(cfg)]
    if cfg.get("platform") or cfg.get("service") or cfg.get("account"):
        return [_registry_target(cfg)]
    from .router import all_channels

    return all_channels()


def _input(payload: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    channel_id = str(target.get("channel_id") or target.get("id") or "").strip()
    service = str(target.get("service") or target.get("platform") or "").lower().strip()
    if not channel_id or not service:
        raise ConnectorError("Buffer target requires channel_id and service/platform")
    value: dict[str, Any] = {
        "channelId": channel_id,
        "schedulingType": str(target.get("scheduling_type") or "automatic"),
        "mode": str(target.get("mode") or "addToQueue"),
        "text": text(payload),
    }
    due_at = (
        target.get("due_at")
        or payload.get("due_at")
        or payload.get("scheduled_at")
        or os.getenv("BUFFER_DUE_AT")
    )
    if due_at:
        value["dueAt"] = str(due_at)
    asset = media_url(payload)
    media_type = str(
        target.get("media_type") or payload.get("media_type") or ""
    ).lower()
    if service in {"youtube", "tiktok"} and not media_type:
        media_type = "video"
    if asset:
        value["assets"] = [
            {"video" if media_type == "video" else "image": {"url": asset}}
        ]
    metadata: dict[str, Any] = {}
    if service == "instagram":
        if not asset:
            raise ConnectorError("Buffer Instagram posts require media_url")
        metadata["instagram"] = {
            "type": str(target.get("instagram_type") or "post"),
            "shouldShareToFeed": bool(target.get("should_share_to_feed", True)),
        }
    elif service == "facebook":
        metadata["facebook"] = {"type": str(target.get("facebook_type") or "post")}
    elif service == "pinterest":
        configured_board = str(target.get("board_service_id") or "").strip()
        if configured_board.upper().startswith(("PENDING_", "TODO_", "PLACEHOLDER_")):
            configured_board = ""
        board = configured_board or os.getenv("BUFFER_BOARD_SERVICE_ID", "").strip()
        if board.upper().startswith(("PENDING_", "TODO_", "PLACEHOLDER_")):
            board = ""
        if not board:
            raise ConnectorError(
                "Buffer Pinterest requires a verified buffer.board_service_id from channel metadata"
            )
        metadata["pinterest"] = {
            "boardServiceId": board,
            "title": str(target.get("title") or payload.get("title") or ""),
        }
    elif service == "youtube":
        if not asset or media_type != "video":
            raise ConnectorError("Buffer YouTube posts require a video media_url")
        metadata["youtube"] = {
            "title": str(target.get("title") or payload.get("title") or ""),
            "categoryId": str(target.get("category_id") or "22"),
            "privacy": str(target.get("privacy") or "private"),
        }
    if metadata:
        value["metadata"] = metadata
    return value


def _key_for(target: dict[str, Any]) -> str:
    account = str(target.get("account") or "").strip()
    if account and account.isdigit():
        return os.getenv(f"BUFFER_API_KEY_ACCOUNT_{account}", "").strip() or env(
            "BUFFER_API_KEY"
        )
    return env("BUFFER_API_KEY")


def _create(value: dict[str, Any], key: str) -> dict[str, Any]:
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
    return result.get("post") or {}


def get_post(post_id: str, *, account: str | int | None = None) -> dict[str, Any]:
    """Fetch the current Buffer lifecycle state for one persisted post ID."""
    identifier = str(post_id or "").strip()
    if not identifier:
        raise ConnectorError("Buffer post reconciliation requires post_id")
    query = """
    query GetPost($input: PostInput!) {
      post(input: $input) { id status dueAt }
    }
    """
    response = request_json(
        ENDPOINT,
        headers={"Authorization": f"Bearer {_key_for({'account': account})}"},
        data={"query": query, "variables": {"input": {"id": identifier}}},
    )
    if response.get("errors"):
        raise ConnectorError("Buffer GraphQL post lookup returned an error")
    post = response.get("data", {}).get("post")
    if not isinstance(post, dict) or str(post.get("id") or "") != identifier:
        raise ConnectorError("Buffer GraphQL post lookup returned no matching post")
    return post


def _target_metadata(
    target: dict[str, Any], post: dict[str, Any] | None = None
) -> dict[str, Any]:
    value = {
        "account": target.get("account"),
        "platform": str(target.get("platform") or target.get("service") or "").lower(),
        "channel_id": str(target.get("channel_id") or target.get("id") or ""),
    }
    if target.get("organization_id"):
        value["organization_id"] = str(target["organization_id"])
    if post is not None:
        if post.get("id"):
            value["buffer_post_id"] = str(post["id"])
        if post.get("status"):
            value["status"] = str(post["status"]).lower()
    return value


def publish(
    payload: dict[str, Any],
    *,
    dry_run: bool = True,
    idempotency_key: str | None = None,
    provider: str = "buffer",
) -> dict[str, Any]:
    targets = _targets(payload)
    values = [_input(payload, target) for target in targets]
    if dry_run:
        return {
            **dry_result("buffer", BACKEND, endpoint=ENDPOINT, payload=payload),
            "targets": values,
            "target_metadata": [_target_metadata(target) for target in targets],
            "provider": provider,
            "idempotency_key": idempotency_key,
        }
    posts = [_create(value, _key_for(target)) for value, target in zip(values, targets)]
    external_ids = [str(post.get("id")) for post in posts if post.get("id")]
    target_metadata = [
        _target_metadata(target, post) for target, post in zip(targets, posts)
    ]
    result = {
        "platform": "buffer",
        "backend": BACKEND,
        "mode": "LIVE",
        "published": True,
        "validated": True,
        "external_ids": external_ids,
        "posts": posts,
        "target_metadata": target_metadata,
        "provider": provider,
        "idempotency_key": idempotency_key,
    }
    if len(external_ids) == 1:
        result["external_id"] = external_ids[0]
    return result
