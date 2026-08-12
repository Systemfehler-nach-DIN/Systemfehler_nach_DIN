"""Shared fail-closed contract for social platform adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ConnectorError(RuntimeError):
    """A connector cannot safely perform the requested operation."""


@dataclass(frozen=True)
class PublishResult:
    platform: str
    dry_run: bool
    published: bool
    external_id: str | None = None
    raw: dict[str, Any] | None = None


def require_live(*, dry_run: bool, allow_real_posts: bool) -> None:
    if dry_run:
        return
    if not allow_real_posts:
        raise ConnectorError("live publishing requires explicit allow_real_posts=True")
