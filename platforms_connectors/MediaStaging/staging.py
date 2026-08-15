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
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import urlopen

import httpx


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
    request_headers = {
        "Authorization": f"Bearer {key}",
        "apikey": key,
        "Content-Type": content_type,
        "Accept": "application/json",
        "User-Agent": "Systemfehler-nach-DIN-MediaStaging/1.0",
        **(headers or {}),
    }
    try:
        response = httpx.request(
            method,
            url,
            headers=request_headers,
            content=body,
            timeout=60.0,
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.json() if response.content else {}
    except httpx.HTTPStatusError as exc:
        raise StagingError(
            f"Supabase request failed: {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise StagingError(
            f"Supabase request failed: {type(exc).__name__}"
        ) from exc


def stage_file(
    path: str,
    *,
    content_id: str,
    media_id: str | None = None,
    mime_type: str | None = None,
    cleanup_after: str | None = None,
    source_provider: str | None = None,
    source_reference: str | None = None,
    source_fs_id: int | None = None,
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
    if source_provider:
        row["source_provider"] = source_provider
    if source_reference:
        row["source_reference"] = source_reference
    if source_fs_id is not None:
        row["source_fs_id"] = int(source_fs_id)
    try:
        _request(
            f"{base}/rest/v1/media_assets",
            key=key,
            method="POST",
            body=json.dumps(row).encode(),
            content_type="application/json",
            headers={"Prefer": "resolution=merge-duplicates,return=representation"},
        )
    except Exception as exc:
        # Storage is temporary; compensate only the object just uploaded.
        try:
            _request(upload_url, key=key, method="DELETE")
        except Exception as compensation:  # preserve both failures without secrets
            raise StagingError(
                "metadata write failed and storage compensation failed"
            ) from compensation
        raise StagingError(
            "metadata write failed; uploaded object compensated"
        ) from exc
    return row


def stage_terabox_reference(
    remote_path: str,
    *,
    content_id: str,
    fs_id: int,
    output_dir: str | None = None,
    terabox_command: str = "terabox-sin",
) -> dict[str, Any]:
    """Read one TeraBox file by ``fs_id`` and stage its bytes in Supabase.

    TeraBox-SIN's ``download`` method returns a short-lived download descriptor,
    not file bytes.  The descriptor is consumed immediately and never returned
    or logged.  This function calls no TeraBox mutation method, so the archive
    remains untouched.
    """
    import tempfile

    if not remote_path.strip() or int(fs_id) <= 0:
        raise StagingError("TeraBox reference requires remote_path and positive fs_id")
    destination_root = (
        Path(output_dir).expanduser()
        if output_dir
        else Path(tempfile.mkdtemp(prefix="sin-terabox-"))
    )
    destination_root.mkdir(parents=True, exist_ok=True)
    suffix = Path(remote_path).suffix.lower() or ".bin"
    destination = destination_root / f"{int(fs_id)}{suffix}"
    status_command = [terabox_command, "status"]
    command = [terabox_command, "call", "download", json.dumps([[int(fs_id)]])]
    try:
        status_result = subprocess.run(
            status_command, check=True, capture_output=True, text=True, timeout=30
        )
        status_value = json.loads(status_result.stdout)
        if not (
            isinstance(status_value, dict)
            and status_value.get("configured") is True
            and status_value.get("authenticated") is True
        ):
            raise StagingError("TeraBox-SIN is not configured and authenticated")
        result = subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=300
        )
        descriptor = json.loads(result.stdout)
        dlink = _find_download_link(descriptor)
        if not dlink:
            raise StagingError("TeraBox download returned no download link")
        with urlopen(dlink, timeout=300) as response, destination.open("wb") as handle:
            while chunk := response.read(1024 * 1024):
                handle.write(chunk)
    except StagingError:
        raise
    except (
        OSError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        raise StagingError("TeraBox download failed") from exc
    if not destination.is_file() or destination.stat().st_size == 0:
        raise StagingError("TeraBox download produced no local file")
    staged = stage_file(
        str(destination),
        content_id=content_id,
        source_provider="terabox",
        source_reference=remote_path,
        source_fs_id=int(fs_id),
    )
    staged.update(
        {
            "source_provider": "terabox",
            "source_reference": remote_path,
            "source_fs_id": int(fs_id),
        }
    )
    return staged


def _find_download_link(value: Any) -> str | None:
    """Extract only an HTTPS download URL from a TeraBox descriptor."""
    if isinstance(value, dict):
        for key, item in value.items():
            if (
                key.lower() in {"dlink", "download_url", "downloadurl"}
                and isinstance(item, str)
                and item.startswith("https://")
            ):
                return item
            found = _find_download_link(item)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_download_link(item)
            if found:
                return found
    return None


def mark_published(
    *,
    content_id: str,
    idempotency_key: str | None = None,
    grace_hours: int = 48,
) -> dict[str, Any]:
    """Mark staged media published and arm, but never bypass, the grace period."""
    base, key, _ = _config()
    cleanup_epoch = int(time.time()) + grace_hours * 3600
    media_query = urlencode(
        {"content_id": f"eq.{content_id}", "status": "neq.published"}
    )
    body = json.dumps(
        {"status": "published", "cleanup_after_epoch": cleanup_epoch}
    ).encode()
    _request(
        f"{base}/rest/v1/media_assets?{media_query}",
        key=key,
        method="PATCH",
        body=body,
        headers={"Prefer": "return=representation"},
    )
    filters = {"provider": "eq.buffer", "content_id": f"eq.{content_id}"}
    if idempotency_key:
        filters["idempotency_key"] = f"eq.{idempotency_key}"
    _request(
        f"{base}/rest/v1/publish_jobs?{urlencode(filters)}",
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


def find_scheduled(*, idempotency_key: str) -> dict[str, Any] | None:
    """Return one durable Buffer job plus its persisted target/post IDs."""
    base, key, _ = _config()
    query = urlencode(
        {
            "provider": "eq.buffer",
            "idempotency_key": f"eq.{idempotency_key}",
            "select": "*",
            "limit": 1,
        }
    )
    rows = _request(f"{base}/rest/v1/publish_jobs?{query}", key=key, method="GET")
    if not isinstance(rows, list) or not rows:
        return None
    job = dict(rows[0])
    job_id = str(job.get("job_id") or "")
    targets: list[dict[str, Any]] = []
    if job_id:
        target_query = urlencode(
            {
                "job_id": f"eq.{job_id}",
                "select": "account,platform,channel_id,buffer_post_id,status,last_error",
                "order": "created_at.asc",
            }
        )
        value = _request(
            f"{base}/rest/v1/publish_targets?{target_query}", key=key, method="GET"
        )
        if isinstance(value, list):
            targets = [dict(item) for item in value if isinstance(item, dict)]
    job["targets"] = targets
    job["durable"] = True
    return job


def record_scheduled(
    *,
    content_id: str,
    scheduled_at: str | None,
    targets: list[dict[str, Any]],
    idempotency_key: str | None = None,
    status: str = "scheduled",
    provider_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Atomically reserve/upsert one Buffer job and reconcile its target IDs."""
    base, key, _ = _config()
    idempotency_key = idempotency_key or hashlib.sha256(
        f"buffer:{content_id}".encode()
    ).hexdigest()
    normalized_status = str(status or "scheduled").lower()
    job = {
        "content_id": content_id,
        "provider": "buffer",
        "idempotency_key": idempotency_key,
        "status": normalized_status,
        "scheduled_at": scheduled_at,
    }
    job_url = (
        f"{base}/rest/v1/publish_jobs?"
        + urlencode({"on_conflict": "provider,idempotency_key"})
    )
    reserve_only = normalized_status == "draft"
    created = _request(
        job_url,
        key=key,
        method="POST",
        body=json.dumps(job).encode(),
        headers={
            "Prefer": (
                "resolution=ignore-duplicates,return=representation"
                if reserve_only
                else "resolution=merge-duplicates,return=representation"
            )
        },
    )
    job_row = created[0] if isinstance(created, list) and created else created
    existing = reserve_only and not (
        isinstance(job_row, dict) and str(job_row.get("job_id") or "")
    )
    if existing:
        prior = find_scheduled(idempotency_key=idempotency_key)
        if not prior:
            raise StagingError("Supabase reservation conflict returned no existing job")
        prior["existing"] = True
        return prior
    job_id = str(job_row.get("job_id", "")) if isinstance(job_row, dict) else ""
    if not job_id:
        raise StagingError("Supabase did not return publish_jobs.job_id")

    target_rows = []
    for target in targets:
        account = target.get("account")
        platform = str(target.get("platform") or target.get("service") or "").strip()
        channel_id = str(target.get("channel_id") or target.get("id") or "").strip()
        if account in (None, "") or not platform or not channel_id:
            raise StagingError("Buffer target persistence requires account/platform/channel_id")
        target_rows.append(
            {
                "job_id": job_id,
                "account": int(account),
                "platform": platform,
                "channel_id": channel_id,
                "buffer_post_id": target.get("buffer_post_id"),
                "status": str(target.get("status") or "scheduled").lower(),
            }
        )
    if target_rows:
        target_url = (
            f"{base}/rest/v1/publish_targets?"
            + urlencode({"on_conflict": "job_id,account,platform,channel_id"})
        )
        _request(
            target_url,
            key=key,
            method="POST",
            body=json.dumps(target_rows).encode(),
            headers={"Prefer": "resolution=merge-duplicates,return=representation"},
        )
    return {
        "job_id": job_id,
        "content_id": content_id,
        "idempotency_key": idempotency_key,
        "target_count": len(target_rows),
        "targets": target_rows,
        "status": normalized_status,
        "existing": False,
    }


def record_job_status(
    *, idempotency_key: str, status: str, error: str | None = None
) -> dict[str, Any]:
    """Persist the aggregate Buffer job state by deterministic key."""
    base, key, _ = _config()
    body: dict[str, Any] = {"status": str(status).lower()}
    if error:
        body["last_error"] = error[:1000]
    query = urlencode(
        {"provider": "eq.buffer", "idempotency_key": f"eq.{idempotency_key}"}
    )
    _request(
        f"{base}/rest/v1/publish_jobs?{query}",
        key=key,
        method="PATCH",
        body=json.dumps(body).encode(),
        headers={"Prefer": "return=representation"},
    )
    return {"idempotency_key": idempotency_key, "status": body["status"]}


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


def cleanup_due(
    *,
    now_epoch: int | None = None,
    limit: int = 100,
    content_id: str | None = None,
) -> dict[str, int]:
    base, key, bucket = _config()
    now_epoch = now_epoch or int(time.time())
    filters: dict[str, Any] = {
        "status": "eq.published",
        "cleanup_after_epoch": f"lte.{now_epoch}",
        "select": "media_id,object_path,content_id",
        "limit": limit,
    }
    if content_id is not None:
        filters["content_id"] = f"eq.{content_id}"
    params = urlencode(filters)
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
    terabox = sub.add_parser("stage-terabox")
    terabox.add_argument("--remote-path", required=True)
    terabox.add_argument("--fs-id", required=True, type=int)
    terabox.add_argument("--content-id", required=True)
    terabox.add_argument("--output-dir")
    published = sub.add_parser("mark-published")
    published.add_argument("--content-id", required=True)
    published.add_argument("--grace-hours", type=int, default=48)
    scheduled = sub.add_parser("record-scheduled")
    scheduled.add_argument("--content-id", required=True)
    scheduled.add_argument("--scheduled-at")
    scheduled.add_argument("--targets-json", required=True)
    scheduled.add_argument("--idempotency-key")
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
    elif args.command == "stage-terabox":
        result = stage_terabox_reference(
            args.remote_path,
            content_id=args.content_id,
            fs_id=args.fs_id,
            output_dir=args.output_dir,
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
            idempotency_key=args.idempotency_key,
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
