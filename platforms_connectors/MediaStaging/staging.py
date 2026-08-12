"""Supabase Storage staging with durable metadata and delayed cleanup.

TeraBox remains the durable source. Supabase is a temporary public-URL staging
layer for Buffer. Secrets are runtime-only environment values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class StagingError(RuntimeError):
    pass


def _env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise StagingError(f"missing runtime configuration: {name}")
    return value


def _config() -> tuple[str, str, str]:
    base = _env("SUPABASE_URL").rstrip("/")
    key = _env("SUPABASE_SERVICE_ROLE_KEY")
    bucket = (
        os.getenv("SUPABASE_MEDIA_BUCKET", "social-staging").strip() or "social-staging"
    )
    return base, key, bucket


def _request(
    url: str,
    *,
    key: str,
    method: str = "POST",
    body: bytes | None = None,
    content_type: str = "application/json",
) -> Any:
    req = Request(
        url,
        method=method,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "apikey": key,
            "Content-Type": content_type,
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=60) as response:
            raw = response.read()
            return json.loads(raw.decode()) if raw else {}
    except (HTTPError, URLError, TimeoutError) as exc:
        raise StagingError(
            f"Supabase request failed: {getattr(exc, 'code', type(exc).__name__)}"
        ) from exc


def stage_file(
    path: str,
    *,
    content_id: str,
    media_id: str | None = None,
    mime_type: str | None = None,
    cleanup_after: str | None = None,
) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise StagingError(f"media file not found: {source}")
    base, key, bucket = _config()
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    media_id = media_id or digest[:24]
    suffix = source.suffix.lower() or ".bin"
    object_path = f"{content_id}/{media_id}{suffix}"
    mime = (
        mime_type or mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    )
    upload_url = f"{base}/storage/v1/object/{bucket}/{object_path}"
    _request(upload_url, key=key, method="POST", body=data, content_type=mime)
    public_url = f"{base}/storage/v1/object/public/{bucket}/{object_path}"
    row = {
        "content_id": content_id,
        "media_id": media_id,
        "object_path": object_path,
        "public_url": public_url,
        "mime_type": mime,
        "size_bytes": len(data),
        "sha256": digest,
        "status": "staged",
        "cleanup_after": cleanup_after,
    }
    _request(
        f"{base}/rest/v1/media_assets",
        key=key,
        method="POST",
        body=json.dumps(row).encode(),
        content_type="application/json",
    )
    return row


def mark_published(*, content_id: str, grace_hours: int = 48) -> dict[str, Any]:
    base, key, _ = _config()
    cleanup_epoch = int(time.time()) + grace_hours * 3600
    # PostgREST filters are URL encoded only for fixed internal identifiers.
    url = f"{base}/rest/v1/media_assets?content_id=eq.{content_id}"
    body = json.dumps(
        {"status": "published", "cleanup_after_epoch": cleanup_epoch}
    ).encode()
    _request(url, key=key, method="PATCH", body=body)
    return {
        "content_id": content_id,
        "status": "published",
        "cleanup_after_epoch": cleanup_epoch,
    }


def cleanup_due(*, now_epoch: int | None = None, limit: int = 100) -> dict[str, int]:
    base, key, bucket = _config()
    now_epoch = now_epoch or int(time.time())
    rows = _request(
        f"{base}/rest/v1/media_assets?status=eq.published&cleanup_after_epoch=lte.{now_epoch}&select=media_id,object_path&limit={limit}",
        key=key,
        method="GET",
    )
    deleted = 0
    for row in rows if isinstance(rows, list) else []:
        path = str(row.get("object_path", ""))
        if not path:
            continue
        _request(f"{base}/storage/v1/object/{bucket}/{path}", key=key, method="DELETE")
        _request(
            f"{base}/rest/v1/media_assets?media_id=eq.{row.get('media_id')}",
            key=key,
            method="DELETE",
        )
        deleted += 1
    return {"deleted": deleted}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    stage = sub.add_parser("stage")
    stage.add_argument("--path", required=True)
    stage.add_argument("--content-id", required=True)
    stage.add_argument("--cleanup-after")
    published = sub.add_parser("mark-published")
    published.add_argument("--content-id", required=True)
    published.add_argument("--grace-hours", type=int, default=48)
    sub.add_parser("cleanup")
    args = parser.parse_args()
    if args.command == "stage":
        result = stage_file(
            args.path, content_id=args.content_id, cleanup_after=args.cleanup_after
        )
    elif args.command == "mark-published":
        result = mark_published(
            content_id=args.content_id, grace_hours=args.grace_hours
        )
    else:
        result = cleanup_due()
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
