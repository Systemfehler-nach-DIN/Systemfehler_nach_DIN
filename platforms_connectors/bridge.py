#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

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
            "credential_source": "env/session-path only",
        }


ADAPTERS: dict[str, Adapter] = {
    "tiktok": Adapter(
        "tiktok",
        "SIN-Browser-Use CLI 3.0 / TikTok Studio",
        ("TIKTOK_PARTNER_EMAIL",),
        ("TIKTOK_COOKIE_PATH", "SIN_CHROME_PROFILE"),
    ),
    "instagram": Adapter(
        "instagram",
        "subzeroid/instagrapi",
        ("INSTAGRAM_USERNAME", "INSTAGRAM_PASSWORD"),
        ("INSTAGRAM_SESSION_PATH",),
    ),
    "reddit": Adapter("reddit", "playwright-web", (), ("REDDIT_STORAGE_STATE",)),
    "x": Adapter(
        "x", "d60/twikit", ("X_USERNAME", "X_EMAIL", "X_PASSWORD"), ("X_COOKIE_PATH",)
    ),
    "youtube": Adapter(
        "youtube",
        "YouTube Data API v3 (OAuth 2.0)",
        ("YOUTUBE_OAUTH_TOKEN", "YOUTUBE_OAUTH_CLIENT_SECRETS"),
        ("YOUTUBE_VIDEO_PATH",),
    ),
    "mastodon": Adapter(
        "mastodon", "Mastodon.py/toot", ("MASTODON_ACCESS_TOKEN", "MASTODON_BASE_URL")
    ),
    "bluesky": Adapter(
        "bluesky", "MarshalX/atproto", ("BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD")
    ),
    "telegram": Adapter(
        "telegram",
        "Telethon",
        ("TELEGRAM_API_ID", "TELEGRAM_API_HASH"),
        ("TELEGRAM_SESSION_PATH",),
    ),
    "discord": Adapter("discord", "stdlib Incoming Webhook", ("DISCORD_WEBHOOK_URL",)),
    "forums": Adapter(
        "forums",
        "Discourse HTTP API / Playwright fallback",
        ("DISCOURSE_BASE_URL", "DISCOURSE_API_KEY", "DISCOURSE_API_USERNAME"),
        ("FORUM_STORAGE_STATE",),
    ),
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
    # YouTube-only options are kept out of the common platform schema unless supplied.
    if isinstance(payload.get("youtube"), dict):
        normalized["youtube"] = dict(payload["youtube"])
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


def publish(payload: Any, platforms: list[str] | None = None) -> dict[str, Any]:
    normalized = validate_payload(payload)
    selected = platforms or list(ADAPTERS)
    unknown = [name for name in selected if name not in ADAPTERS]
    if unknown:
        raise ValueError("unknown platforms: " + ", ".join(unknown))
    if live_allowed():
        # Only the reviewed, official YouTube API path may publish. All other
        # adapters remain fail-closed until they receive their own implementation.
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
        raise PermissionError(
            "LIVE publishing denied: adapter-specific live approval is not installed"
        )
    return {
        "ok": True,
        "mode": "DRY_RUN",
        "payload": normalized,
        "results": [ADAPTERS[name].draft(normalized) for name in selected],
    }


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
        if self.path != "/publish":
            self._json(404, {"ok": False, "error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            if isinstance(body, dict) and "payload" in body:
                payload = body["payload"]
                platforms = body.get("platforms")
            else:
                payload = body
                platforms = None
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
