"""Non-secret Buffer channel routing registry for SYSTEMFEHLER_nach_DIN."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

_REGISTRY = json.loads((Path(__file__).with_name("accounts.json")).read_text())


def channel_for(platform: str) -> dict[str, Any]:
    wanted = "twitter" if platform == "x" else platform
    for account in _REGISTRY["accounts"]:
        for channel in account["channels"]:
            if channel["platform"] == wanted:
                return {**channel, "account": account["account"], "organization_id": account["organization_id"], "infisical_key": account["infisical_key"]}
    raise KeyError(f"no Buffer channel registered for {platform}")


def supported_platforms() -> tuple[str, ...]:
    return tuple(c["platform"] for a in _REGISTRY["accounts"] for c in a["channels"])
