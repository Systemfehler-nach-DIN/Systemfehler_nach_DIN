"""Official LinkedIn Posts API connector."""

from __future__ import annotations
from typing import Any
from platforms_connectors.base import dry_result, env, published, request_json, text

BACKEND = "LinkedIn Posts API"


def publish(payload: dict[str, Any], *, dry_run: bool = True) -> dict[str, Any]:
    endpoint = "https://api.linkedin.com/rest/posts"
    if dry_run:
        return dry_result("linkedin", BACKEND, endpoint=endpoint, payload=payload)
    token = env("LINKEDIN_ACCESS_TOKEN")
    author = env("LINKEDIN_AUTHOR_URN")
    body = {
        "author": author,
        "commentary": text(payload),
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    response = request_json(
        endpoint,
        headers={
            "Authorization": f"Bearer {token}",
            "LinkedIn-Version": __import__("os").getenv("LINKEDIN_VERSION", "202501"),
            "X-Restli-Protocol-Version": "2.0.0",
        },
        data=body,
    )
    return published(
        "linkedin",
        BACKEND,
        response,
        external_id=response.get("id")
        or response.get("x-restli-id")
        or response.get("_response_headers", {}).get("x-restli-id"),
    )
