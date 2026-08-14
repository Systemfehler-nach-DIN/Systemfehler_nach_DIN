"""Non-secret Buffer channel routing registry for SYSTEMFEHLER_nach_DIN."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REGISTRY = json.loads(
    (Path(__file__).with_name("accounts.json")).read_text(encoding="utf-8")
)


def _canonical_platform(value: str) -> str:
    normalized = value.strip().lower()
    return "x" if normalized in {"x", "twitter"} else normalized


def channel_for(platform: str, account: str | int | None = None) -> dict[str, Any]:
    wanted = _canonical_platform(platform)
    account_value = str(account) if account is not None else None
    for owner in _REGISTRY["accounts"]:
        if account_value and owner["account"] != account_value:
            continue
        for channel in owner["channels"]:
            if _canonical_platform(channel["platform"]) == wanted:
                return {
                    **channel,
                    "account": owner["account"],
                    "organization_id": owner["organization_id"],
                    "infisical_key": owner["infisical_key"],
                }
    suffix = f" in account {account_value}" if account_value else ""
    raise KeyError(f"no Buffer channel registered for {platform}{suffix}")


def channels_for(
    platform: str, account: str | int | None = None
) -> list[dict[str, Any]]:
    """Return all matching channels; account-scoped registry currently has one each."""
    return [channel_for(platform, account)]


def all_channels() -> list[dict[str, Any]]:
    return [
        {
            **channel,
            "account": owner["account"],
            "organization_id": owner["organization_id"],
            "infisical_key": owner["infisical_key"],
        }
        for owner in _REGISTRY["accounts"]
        for channel in owner["channels"]
    ]


def supported_platforms() -> tuple[str, ...]:
    return tuple(c["platform"] for a in _REGISTRY["accounts"] for c in a["channels"])
