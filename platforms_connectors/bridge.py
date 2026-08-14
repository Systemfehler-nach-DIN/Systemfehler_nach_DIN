#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

_LIFECYCLE_STORE: dict[str, dict[str, Any]] = {}
_LIFECYCLE_LOCK = threading.RLock()

REQUIRED_FIELDS = ("title", "excerpt", "body", "media_url", "url", "cta")


@dataclass(frozen=True)
class Adapter:
    platform: str
    backend: str
    auth_env: tuple[str, ...] = ()
    session_env: tuple[str, ...] = ()

    def draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "backend": self.backend,
            "mode": "DRAFT",
            "validated": True,
            "media": bool(payload.get("media_url")),
            "credential_source": "runtime environment/session path"
            if self.session_env
            else "runtime environment only",
        }


ADAPTERS: dict[str, Adapter] = {
    "tiktok": Adapter(
        "tiktok",
        "SIN-Browser-Use CLI 3.0 / TikTok Studio",
        ("TIKTOK_PARTNER_EMAIL",),
        ("SIN_CHROME_PROFILE",),
    ),
    "youtube": Adapter(
        "youtube",
        "YouTube Data API v3 (OAuth 2.0)",
        ("YOUTUBE_OAUTH_TOKEN", "YOUTUBE_OAUTH_CLIENT_SECRETS"),
        ("YOUTUBE_VIDEO_PATH",),
    ),
    "instagram": Adapter(
        "instagram",
        "Instagram Graph API",
        ("INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_USER_ID"),
    ),
    "facebook": Adapter(
        "facebook",
        "Meta Graph API / Pages",
        ("FACEBOOK_PAGE_ACCESS_TOKEN", "FACEBOOK_PAGE_ID"),
    ),
    "threads": Adapter(
        "threads", "Threads API", ("THREADS_ACCESS_TOKEN", "THREADS_USER_ID")
    ),
    "x": Adapter("x", "X API v2", ("X_ACCESS_TOKEN",)),
    "reddit": Adapter(
        "reddit", "Reddit OAuth API", ("REDDIT_ACCESS_TOKEN", "REDDIT_USER_AGENT")
    ),
    "linkedin": Adapter(
        "linkedin",
        "LinkedIn Posts API",
        ("LINKEDIN_ACCESS_TOKEN", "LINKEDIN_AUTHOR_URN"),
    ),
    "pinterest": Adapter(
        "pinterest",
        "Pinterest API v5",
        ("PINTEREST_ACCESS_TOKEN", "PINTEREST_BOARD_ID"),
    ),
    "bluesky": Adapter(
        "bluesky", "Bluesky AT Protocol", ("BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD")
    ),
    "mastodon": Adapter("mastodon", "Mastodon REST API", ("MASTODON_ACCESS_TOKEN",)),
    "telegram": Adapter(
        "telegram", "Telegram Bot API", ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
    ),
    "discord": Adapter("discord", "Discord Incoming Webhook", ("DISCORD_WEBHOOK_URL",)),
    "postiz": Adapter(
        "postiz",
        "Postiz self-hosted API (optional)",
        ("POSTIZ_API_TOKEN",),
    ),
    "buffer": Adapter(
        "buffer",
        "Buffer API (GraphQL; account-routed)",
        (),
    ),
    # Legacy forum draft remains visible but has no live adapter in this wave.
    "forums": Adapter(
        "forums",
        "Discourse HTTP API (draft-only until separately reviewed)",
        ("DISCOURSE_BASE_URL", "DISCOURSE_API_KEY", "DISCOURSE_API_USERNAME"),
    ),
}

# Only these modules may ever receive a live request. There is deliberately no
# private-API, browser-session, cookie, or password fallback in this registry.
OFFICIAL_MODULES = {
    name: f"platforms_connectors.{name.title()}.publish"
    for name in (
        "instagram",
        "facebook",
        "threads",
        "x",
        "reddit",
        "linkedin",
        "pinterest",
        "bluesky",
        "mastodon",
        "telegram",
        "discord",
        "postiz",
        "buffer",
    )
}


def live_allowed() -> bool:
    return (
        os.getenv("PUBLISH_MODE", "DRY_RUN").upper() == "LIVE"
        and os.getenv("ALLOW_REAL_POSTS", "false").lower() == "true"
    )


def validate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    normalized = {field: payload.get(field, "") for field in REQUIRED_FIELDS}
    if isinstance(payload.get("buffer_targets"), list):
        normalized["buffer_targets"] = payload["buffer_targets"]
    elif isinstance(payload.get("buffer"), dict):
        normalized["buffer"] = payload["buffer"]
    # Platform-specific routing metadata is preserved for Buffer and YouTube.
    # Buffer channel/account selection is non-secret and must survive bridge
    # normalization; credentials remain runtime-only environment values.
    for key in ("buffer", "buffer_targets", "youtube", "tiktok"):
        if isinstance(payload.get(key), (dict, list)):
            normalized[key] = payload[key]
    missing = [
        field for field in ("title", "excerpt") if not str(normalized[field]).strip()
    ]
    if missing:
        raise ValueError("missing required fields: " + ", ".join(missing))
    return normalized


def _publish_youtube_api(payload: dict[str, Any]) -> dict[str, Any]:
    """Live-Upload über die offizielle API; Browser bleibt nur Fallback.

    Diese Funktion wird ausschließlich mit YOUTUBE_API_LIVE_APPROVED=true
    aktiviert. Der Zielkanal wird vor dem Upload verifiziert.
    """
    try:
        from platforms_connectors.YouTube.youtube_api import YouTubeApi, YouTubeApiError
    except ModuleNotFoundError:  # direct execution from platforms_connectors/
        from YouTube.youtube_api import YouTubeApi, YouTubeApiError

    options = payload.get("youtube") if isinstance(payload.get("youtube"), dict) else {}
    video_path = (
        options.get("video_path")
        or os.getenv("YOUTUBE_VIDEO_PATH")
        or payload.get("media_url")
    )
    if not video_path or str(video_path).startswith(("http://", "https://")):
        raise ValueError(
            "YouTube API benötigt eine lokale Videodatei (youtube.video_path oder YOUTUBE_VIDEO_PATH)"
        )
    privacy = str(
        options.get("privacy") or os.getenv("YOUTUBE_PRIVACY", "private")
    ).lower()
    try:
        api = YouTubeApi()
        channel = api.channel()
        expected = os.getenv("YOUTUBE_CHANNEL_ID", "").strip()
        if expected and channel.get("id") != expected:
            raise YouTubeApiError(
                "OAuth-Konto ist nicht für den konfigurierten Zielkanal autorisiert"
            )
        result = api.upload(
            str(video_path),
            str(payload["title"]),
            str(payload.get("body") or payload.get("excerpt") or ""),
            privacy=privacy,
            category_id=str(options.get("category_id", "22")),
            publish_at=options.get("publish_at"),
            made_for_kids=bool(options.get("made_for_kids", False)),
        )
    except YouTubeApiError as exc:
        raise RuntimeError(str(exc)) from exc
    return {
        "platform": "youtube",
        "backend": "YouTube Data API v3",
        "mode": "LIVE",
        "validated": True,
        "video_id": result.get("id"),
        "privacy": privacy,
    }


def _publish_tiktok_browser(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        from platforms_connectors.TikTok.tiktok_social import TikTokError, publish_video
    except ModuleNotFoundError:  # direct execution from platforms_connectors/
        from TikTok.tiktok_social import TikTokError, publish_video
    options = payload.get("tiktok") if isinstance(payload.get("tiktok"), dict) else {}
    video_path = options.get("video_path") or payload.get("media_url")
    if not video_path or str(video_path).startswith(("http://", "https://")):
        raise ValueError(
            "TikTok benötigt eine lokale Videodatei (tiktok.video_path oder media_url)"
        )
    try:
        result = publish_video(
            str(video_path),
            str(
                options.get("description")
                or payload.get("body")
                or payload.get("excerpt")
                or payload["title"]
            ),
            dry_run=False,
        )
    except TikTokError as exc:
        raise RuntimeError(str(exc)) from exc
    return {
        "platform": "tiktok",
        "backend": "SIN-Browser-Use CLI 3.0 / TikTok Studio",
        **result,
    }


def _publish_official(platform: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Dispatch only to an explicitly implemented official API module."""
    import importlib

    module_path = OFFICIAL_MODULES.get(platform)
    if not module_path:
        raise PermissionError(
            f"LIVE publishing denied: no official adapter for {platform}"
        )
    if os.getenv(f"{platform.upper()}_API_LIVE_APPROVED", "false").lower() != "true":
        raise PermissionError(
            f"LIVE publishing denied: set {platform.upper()}_API_LIVE_APPROVED=true after external approval"
        )
    module = importlib.import_module(module_path)
    return module.publish(payload, dry_run=False)


def publish(payload: Any, platforms: list[str] | None = None) -> dict[str, Any]:
    normalized = validate_payload(payload)
    selected = platforms or list(ADAPTERS)
    unknown = [name for name in selected if name not in ADAPTERS]
    if unknown:
        raise ValueError("unknown platforms: " + ", ".join(unknown))
    if live_allowed():
        if (
            selected == ["tiktok"]
            and os.getenv("TIKTOK_BROWSER_LIVE_APPROVED", "false").lower() == "true"
        ):
            return {
                "ok": True,
                "mode": "LIVE",
                "payload": normalized,
                "results": [_publish_tiktok_browser(normalized)],
            }
        if (
            selected == ["youtube"]
            and os.getenv("YOUTUBE_API_LIVE_APPROVED", "false").lower() == "true"
        ):
            return {
                "ok": True,
                "mode": "LIVE",
                "payload": normalized,
                "results": [_publish_youtube_api(normalized)],
            }
        # Multi-platform live publishing is fail-closed before *any* network
        # request: approvals, runtime configuration and payload validation for
        # every target are checked first, preventing partial fan-out.
        if all(name in OFFICIAL_MODULES for name in selected):
            import importlib

            missing_approvals = [
                name
                for name in selected
                if os.getenv(f"{name.upper()}_API_LIVE_APPROVED", "false").lower()
                != "true"
            ]
            if missing_approvals:
                raise PermissionError(
                    "LIVE publishing denied: missing explicit approval for "
                    + ", ".join(missing_approvals)
                )
            modules = {
                name: importlib.import_module(OFFICIAL_MODULES[name])
                for name in selected
            }
            for name, adapter in ((name, ADAPTERS[name]) for name in selected):
                missing_config = [
                    key for key in adapter.auth_env if not os.getenv(key, "").strip()
                ]
                if (
                    name == "buffer"
                    and not any(
                        os.getenv(f"BUFFER_API_KEY_ACCOUNT_{account}", "").strip()
                        for account in ("1", "2", "3")
                    )
                    and not os.getenv("BUFFER_API_KEY", "").strip()
                ):
                    missing_config = ["BUFFER_API_KEY_ACCOUNT_1..3 or BUFFER_API_KEY"]
                if missing_config:
                    raise PermissionError(
                        f"LIVE publishing denied: missing runtime configuration for {name}: "
                        + ", ".join(missing_config)
                    )
                modules[name].publish(normalized, dry_run=True)
            return {
                "ok": True,
                "mode": "LIVE",
                "payload": normalized,
                "results": [
                    modules[name].publish(normalized, dry_run=False)
                    for name in selected
                ],
            }
        raise PermissionError(
            "LIVE publishing denied: adapter-specific live approval is not installed"
        )
    results = []
    for name in selected:
        if name == "buffer" and platforms is not None:
            # Exercise the real account/channel routing and payload validation
            # when Buffer is explicitly selected; this must never perform network I/O.
            from platforms_connectors.Buffer.publish import publish as buffer_publish

            results.append(buffer_publish(normalized, dry_run=True))
        else:
            results.append(ADAPTERS[name].draft(normalized))
    return {
        "ok": True,
        "mode": "DRY_RUN",
        "payload": normalized,
        "results": results,
    }


def _buffer_job_status(statuses: list[str]) -> tuple[bool, str]:
    """Normalize Buffer terminal states into the durable job state machine."""
    terminal_sent = {"sent", "published"}
    terminal_error = {"error", "failed", "failure"}
    all_sent = bool(statuses) and all(status in terminal_sent for status in statuses)
    if all_sent:
        return True, "sent"
    if any(status in terminal_error for status in statuses):
        return False, "error"
    return False, "scheduled"


def lifecycle(payload: dict[str, Any], *, dry_run: bool = True) -> dict[str, Any]:
    """Execute the durable Buffer lifecycle; never schedules direct platforms."""
    from platforms_connectors.lifecycle import idempotency_key, run_buffer_lifecycle
    from platforms_connectors.Buffer.publish import get_post, publish as buffer_publish
    from platforms_connectors.Buffer.router import all_channels

    durable_enabled = all(
        os.getenv(name, "").strip()
        for name in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
    )
    if not dry_run and not durable_enabled:
        raise PermissionError(
            "LIVE Buffer lifecycle requires Supabase durability; refusing in-memory scheduling"
        )

    def lookup(**kwargs: Any) -> dict[str, Any] | None:
        key = kwargs["idempotency_key"]
        if durable_enabled:
            from platforms_connectors.MediaStaging.staging import find_scheduled

            durable = find_scheduled(idempotency_key=key)
            if durable:
                with _LIFECYCLE_LOCK:
                    _LIFECYCLE_STORE[key] = dict(durable)
                return durable
        with _LIFECYCLE_LOCK:
            current = _LIFECYCLE_STORE.get(key)
            return dict(current) if current else None

    def persist(**kwargs: Any) -> dict[str, Any]:
        key = kwargs["idempotency_key"]
        row = {
            "content_id": kwargs["content_id"],
            "idempotency_key": key,
            "status": str(kwargs["status"]).lower(),
            "targets": kwargs.get("targets", []),
            "durable": False,
        }
        if kwargs.get("provider_result") is not None:
            row["provider_result"] = kwargs["provider_result"]

        if durable_enabled:
            from platforms_connectors.MediaStaging.staging import record_scheduled

            durable = record_scheduled(
                content_id=kwargs["content_id"],
                scheduled_at=payload.get("scheduled_at"),
                targets=kwargs.get("targets", []),
                idempotency_key=key,
                status=kwargs["status"],
                provider_result=kwargs.get("provider_result"),
            )
            row.update(durable, durable=True)
            with _LIFECYCLE_LOCK:
                _LIFECYCLE_STORE[key] = dict(row)
            return row

        with _LIFECYCLE_LOCK:
            current = _LIFECYCLE_STORE.get(key)
            if row["status"] == "draft" and current:
                existing = dict(current)
                existing["existing"] = True
                return existing
            if current:
                current.update(row)
                current["existing"] = False
                return dict(current)
            row["existing"] = False
            _LIFECYCLE_STORE[key] = dict(row)
            return row

    def provider(provider_payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        result = buffer_publish(provider_payload, **kwargs)
        result.setdefault(
            "target_metadata",
            provider_payload.get("buffer_targets")
            if isinstance(provider_payload.get("buffer_targets"), list)
            else all_channels(),
        )
        return result

    def reconcile(**kwargs: Any) -> dict[str, Any]:
        targets = [
            dict(target)
            for target in kwargs.get("targets", [])
            if isinstance(target, dict)
        ]
        if dry_run:
            return {
                "all_sent": False,
                "checked": len(targets),
                "status": "pending",
                "job_status": "scheduled",
                "targets": targets,
            }

        from platforms_connectors.MediaStaging.staging import (
            record_job_status,
            record_target_status,
        )

        attempts = max(1, int(os.getenv("BUFFER_RECONCILE_MAX_ATTEMPTS", "3")))
        delay = max(0.0, float(os.getenv("BUFFER_RECONCILE_RETRY_SECONDS", "0.25")))
        statuses: list[str] = []
        for target in targets:
            post_id = str(target.get("buffer_post_id") or "").strip()
            if not post_id:
                target["status"] = str(target.get("status") or "scheduled").lower()
                target["last_error"] = "missing persisted Buffer post id"
                statuses.append(target["status"])
                continue
            last_error: Exception | None = None
            for attempt in range(attempts):
                try:
                    state = get_post(post_id, account=target.get("account"))
                    target["status"] = str(state.get("status") or "scheduled").lower()
                    target.pop("last_error", None)
                    last_error = None
                    break
                except Exception as exc:  # provider failures are retried, then persisted
                    last_error = exc
                    if attempt + 1 < attempts and delay:
                        time.sleep(delay)
            if last_error is not None:
                target["status"] = str(target.get("status") or "scheduled").lower()
                target["last_error"] = type(last_error).__name__
            statuses.append(target["status"])
            if durable_enabled:
                record_target_status(
                    buffer_post_id=post_id,
                    status=target["status"],
                    error=target.get("last_error"),
                )

        all_sent, job_status = _buffer_job_status(statuses)
        if durable_enabled:
            record_job_status(
                idempotency_key=kwargs["idempotency_key"], status=job_status
            )
        return {
            "all_sent": all_sent,
            "checked": len(targets),
            "status": "complete" if all_sent else "pending",
            "job_status": job_status,
            "targets": targets,
        }

    def cleanup(**kwargs: Any) -> dict[str, int]:
        if not durable_enabled:
            return {"deleted": 0, "skipped": 1}
        from platforms_connectors.MediaStaging.staging import cleanup_due, mark_published

        if kwargs.get("first_sent"):
            mark_published(
                content_id=kwargs["content_id"],
                idempotency_key=kwargs["idempotency_key"],
                grace_hours=max(1, int(os.getenv("SOCIAL_STAGING_GRACE_HOURS", "48"))),
            )
        return cleanup_due(content_id=kwargs["content_id"])

    working_payload = dict(payload)
    staged_media: dict[str, Any] | None = None
    source = (
        working_payload.get("terabox_source")
        if isinstance(working_payload.get("terabox_source"), dict)
        else None
    )
    if source and not str(working_payload.get("media_url") or "").strip():
        if not durable_enabled:
            raise ValueError(
                "TeraBox media staging requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY"
            )
        key = idempotency_key(working_payload)
        if lookup(idempotency_key=key) is None:
            remote_path = str(source.get("remote_path") or "").strip()
            try:
                fs_id = int(source.get("fs_id"))
            except (TypeError, ValueError) as exc:
                raise ValueError("terabox_source.fs_id must be a positive integer") from exc
            from platforms_connectors.MediaStaging.staging import stage_terabox_reference

            staged_media = stage_terabox_reference(
                remote_path,
                content_id=str(working_payload.get("content_id") or key),
                fs_id=fs_id,
            )
            working_payload["media_url"] = staged_media["public_url"]

    result = run_buffer_lifecycle(
        working_payload,
        publish=provider,
        persist=persist,
        reconcile=reconcile,
        cleanup=cleanup,
        lookup=lookup,
        dry_run=dry_run,
    )
    if staged_media is not None:
        result["staging"] = {
            key: staged_media[key]
            for key in (
                "media_id",
                "public_url",
                "sha256",
                "source_provider",
                "source_reference",
                "source_fs_id",
            )
            if key in staged_media
        }
    return result


def _request_envelope(body: Any) -> tuple[dict[str, Any], list[str] | None]:
    """Normalize the HTTP envelope without dropping Buffer routing metadata."""
    if isinstance(body, dict) and "payload" in body:
        raw_payload = body["payload"]
        if not isinstance(raw_payload, dict):
            raise ValueError("payload must be a JSON object")
        payload = dict(raw_payload)
        if "buffer_targets" in body:
            if not isinstance(body["buffer_targets"], list):
                raise ValueError("buffer_targets must be a JSON array")
            payload["buffer_targets"] = body["buffer_targets"]
        raw_platforms = body.get("platforms")
        if raw_platforms is not None and not isinstance(raw_platforms, list):
            raise ValueError("platforms must be a JSON array")
        return payload, list(raw_platforms) if raw_platforms is not None else None
    if not isinstance(body, dict):
        raise ValueError("payload must be a JSON object")
    return dict(body), None


class Handler(BaseHTTPRequestHandler):
    server_version = "SystemfehlerSocialBridge/1.0"

    def _json(self, status: int, data: dict[str, Any]) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json(
                200,
                {
                    "ok": True,
                    "mode": "DRY_RUN" if not live_allowed() else "LIVE_LOCKED",
                    "platforms": list(ADAPTERS),
                },
            )
        else:
            self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        if self.path not in {"/publish", "/lifecycle"}:
            self._json(404, {"ok": False, "error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            payload, platforms = _request_envelope(body)
            # This endpoint is the canonical Buffer-only scheduler boundary.
            # Direct platform fan-out is intentionally rejected here.
            if platforms is not None and any(
                str(item).lower() != "buffer" for item in platforms
            ):
                raise PermissionError(
                    "social bridge is Buffer-only; direct platform scheduling is disabled"
                )
            if self.path == "/lifecycle":
                self._json(200, lifecycle(payload, dry_run=not live_allowed()))
            else:
                result = publish(payload, platforms)
                self._json(200, result)
        except PermissionError as exc:
            self._json(403, {"ok": False, "error": str(exc)})
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"ok": False, "error": str(exc)})

    def log_message(self, fmt: str, *args: Any) -> None:
        # Never log request bodies, auth headers, session data, or credential values.
        print("bridge", self.address_string(), fmt % args)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SYSTEMFEHLER_nach_DIN social publishing bridge"
    )
    parser.add_argument("--host", default=os.getenv("SOCIAL_BRIDGE_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port", type=int, default=int(os.getenv("SOCIAL_BRIDGE_PORT", "18765"))
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate a sample payload from stdin and exit",
    )
    args = parser.parse_args()
    if args.dry_run:
        print(
            json.dumps(
                publish(json.load(__import__("sys").stdin)),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"social bridge listening on {args.host}:{args.port} mode=DRY_RUN")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
