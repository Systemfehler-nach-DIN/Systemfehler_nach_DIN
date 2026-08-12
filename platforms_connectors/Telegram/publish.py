"""Official Telegram Bot API channel publisher."""

from __future__ import annotations
from typing import Any
from platforms_connectors.base import dry_result, env, published, request_json, text

BACKEND = "Telegram Bot API"


def publish(payload: dict[str, Any], *, dry_run: bool = True) -> dict[str, Any]:
    chat = env("TELEGRAM_CHAT_ID", required=not dry_run)
    token = env("TELEGRAM_BOT_TOKEN", required=not dry_run)
    endpoint = f"https://api.telegram.org/bot{token or '<BOT_TOKEN>'}/sendMessage"
    if dry_run:
        return dry_result("telegram", BACKEND, endpoint=endpoint, payload=payload)
    result = request_json(
        endpoint,
        form={
            "chat_id": chat,
            "text": text(payload),
            "disable_web_page_preview": "false",
        },
    )
    return published(
        "telegram",
        BACKEND,
        result,
        external_id=str(result.get("result", {}).get("message_id", "")) or None,
    )
