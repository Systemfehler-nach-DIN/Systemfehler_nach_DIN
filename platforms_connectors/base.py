"""Shared offline-safe primitives for official social API connectors."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ConnectorError(RuntimeError):
    """A platform operation cannot safely continue."""


def env(name: str, *, required: bool = True) -> str:
    value = os.getenv(name, "").strip()
    if required and not value:
        raise ConnectorError(f"missing required runtime secret/config: {name}")
    return value


def text(payload: dict[str, Any]) -> str:
    value = payload.get("body") or payload.get("excerpt") or payload.get("title")
    value = str(value or "").strip()
    if not value:
        raise ConnectorError("payload requires title, excerpt, or body")
    return value


def media_url(payload: dict[str, Any]) -> str:
    return str(payload.get("media_url") or "").strip()


def dry_result(
    platform: str, backend: str, *, endpoint: str, payload: dict[str, Any]
) -> dict[str, Any]:
    return {
        "platform": platform,
        "backend": backend,
        "mode": "DRY_RUN",
        "published": False,
        "validated": True,
        "endpoint": endpoint,
        "media": bool(media_url(payload)),
    }


def request_json(
    url: str,
    *,
    method: str = "POST",
    headers: dict[str, str] | None = None,
    data: dict[str, Any] | None = None,
    form: dict[str, Any] | None = None,
    timeout: float = 30,
) -> dict[str, Any]:
    body: bytes | None = None
    request_headers = {"Accept": "application/json", **(headers or {})}
    if form is not None:
        body = urlencode({k: v for k, v in form.items() if v is not None}).encode()
        request_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    elif data is not None:
        body = json.dumps(data, ensure_ascii=False).encode()
        request_headers.setdefault("Content-Type", "application/json")
    request = Request(url, data=body, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            value = json.loads(raw) if raw else {}
            if isinstance(value, dict):
                value.setdefault(
                    "_response_headers",
                    {k.lower(): v for k, v in response.headers.items()},
                )
            return value
    except (HTTPError, URLError, TimeoutError) as error:
        detail = getattr(error, "reason", str(error))
        raise ConnectorError(f"official API request failed: {detail}") from error
    except json.JSONDecodeError as error:
        raise ConnectorError("official API returned invalid JSON") from error


def published(
    platform: str,
    backend: str,
    response: dict[str, Any],
    *,
    external_id: str | None = None,
) -> dict[str, Any]:
    identifier = external_id or response.get("id") or response.get("data", {}).get("id")
    if not identifier:
        raise ConnectorError("official API response did not contain an external id")
    return {
        "platform": platform,
        "backend": backend,
        "mode": "LIVE",
        "published": True,
        "validated": True,
        "external_id": str(identifier),
    }
