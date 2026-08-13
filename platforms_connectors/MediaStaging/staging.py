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
from urllib.parse import quote, urlencode
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
    headers: dict[str, str] | None = None,
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
            **(headers or {}),
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
    safe_content = quote(str(content_id), safe="-_.~")
    safe_media = quote(str(media_id), safe="-_.~")
    object_path = f"{safe_content}/{safe_media}{suffix}"
    mime = (
        mime_type or mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    )
    upload_url = f"{base}/storage/v1/object/{bucket}/{object_path}"
    _request(
        upload_url,
        key=key,
        method="PUT",
        body=data,
        content_type=mime,
        headers={"x-upsert": "true"},
    )
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
        headers={"Prefer": "resolution=merge-duplicates,return=representation"},
    )
    return row


def mark_published(*, content_id: str, grace_hours: int = 48) -> dict[str, Any]:
    base, key, _ = _config()
    cleanup_epoch = int(time.time()) + grace_hours * 3600
    url = f"{base}/rest/v1/media_assets?content_id=eq.{quote(str(content_id), safe='-_.~')}"
    body = json.dumps(
        {"status": "published", "cleanup_after_epoch": cleanup_epoch}
    ).encode()
    _request(
        url,
        key=key,
        method="PATCH",
        body=body,
        headers={"Prefer": "return=representation"},
    )
    job_url = (
        f"{base}/rest/v1/publish_jobs?content_id={quote(str(content_id), safe='-_.~')}"
    )
    _request(
        job_url,
        key=key,
        method="PATCH",
        body=json.dumps(
            {
                "status": "sent",
                "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        ).encode(),
        headers={"Prefer": "return=representation"},
    )
    return {
        "content_id": content_id,
        "status": "published",
        "cleanup_after_epoch": cleanup_epoch,
    }


def record_scheduled(
    *,
    content_id: str,
    scheduled_at: str | None,
    targets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Persist Buffer scheduling IDs without storing credentials."""
    base, key, _ = _config()
    job = {
        "content_id": content_id,
        "provider": "buffer",
        "status": "scheduled",
        "scheduled_at": scheduled_at,
    }
    created = _request(
        f"{base}/rest/v1/publish_jobs",
        key=key,
        method="POST",
        body=json.dumps(job).encode(),
        headers={"Prefer": "return=representation"},
    )
    job_row = created[0] if isinstance(created, list) and created else created
    job_id = str(job_row.get("job_id", "")) if isinstance(job_row, dict) else ""
    if not job_id:
        raise StagingError("Supabase did not return publish_jobs.job_id")
    rows = []
    for target in targets:
        rows.append(
            {
                "job_id": job_id,
                "account": int(target["account"]),
                "platform": str(target["platform"]),
                "channel_id": str(target["channel_id"]),
                "buffer_post_id": target.get("buffer_post_id"),
                "status": "scheduled",
            }
        )
    if rows:
        _request(
            f"{base}/rest/v1/publish_targets",
            key=key,
            method="POST",
            body=json.dumps(rows).encode(),
            headers={"Prefer": "return=representation"},
        )
    return {
        "job_id": job_id,
        "content_id": content_id,
        "target_count": len(rows),
        "status": "scheduled",
    }


def record_target_status(
    *, buffer_post_id: str, status: str, error: str | None = None
) -> dict[str, Any]:
    """Record a reconciled Buffer target state; no deletion occurs here."""
    base, key, _ = _config()
    post_id = quote(str(buffer_post_id), safe="-_.~")
    body = {"status": status}
    if error:
        body["last_error"] = error[:1000]
    _request(
        f"{base}/rest/v1/publish_targets?buffer_post_id=eq.{post_id}",
        key=key,
        method="PATCH",
        body=json.dumps(body).encode(),
        headers={"Prefer": "return=representation"},
    )
    return {"buffer_post_id": buffer_post_id, "status": status}


def cleanup_due(*, now_epoch: int | None = None, limit: int = 100) -> dict[str, int]:
    base, key, bucket = _config()
    now_epoch = now_epoch or int(time.time())
    params = urlencode(
        {
            "status": "eq.published",
            "cleanup_after_epoch": f"lte.{now_epoch}",
            "select": "media_id,object_path,content_id",
            "limit": limit,
        }
    )
    rows = _request(f"{base}/rest/v1/media_assets?{params}", key=key, method="GET")
    deleted = 0
    skipped = 0
    for row in rows if isinstance(rows, list) else []:
        content_id = quote(str(row.get("content_id", "")), safe="-_.~")
        pending = _request(
            f"{base}/rest/v1/publish_jobs?content_id=eq.{content_id}&status=not.eq.sent&select=job_id&limit=1",
            key=key,
            method="GET",
        )
        if pending:
            skipped += 1
            continue
        path = str(row.get("object_path", ""))
        media_id = quote(str(row.get("media_id", "")), safe="-_.~")
        if not path or not media_id:
            skipped += 1
            continue
        _request(
            f"{base}/storage/v1/object/{bucket}/{quote(path, safe='/.-_~')}",
            key=key,
            method="DELETE",
        )
        _request(
            f"{base}/rest/v1/media_assets?media_id=eq.{media_id}",
            key=key,
            method="DELETE",
        )
        deleted += 1
    return {"deleted": deleted, "skipped": skipped}


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
    scheduled = sub.add_parser("record-scheduled")
    scheduled.add_argument("--content-id", required=True)
    scheduled.add_argument("--scheduled-at")
    scheduled.add_argument("--targets-json", required=True)
    target = sub.add_parser("record-target-status")
    target.add_argument("--buffer-post-id", required=True)
    target.add_argument("--status", required=True)
    target.add_argument("--error")
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
    elif args.command == "record-scheduled":
        result = record_scheduled(
            content_id=args.content_id,
            scheduled_at=args.scheduled_at,
            targets=json.loads(args.targets_json),
        )
    elif args.command == "record-target-status":
        result = record_target_status(
            buffer_post_id=args.buffer_post_id, status=args.status, error=args.error
        )
    else:
        result = cleanup_due()
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
