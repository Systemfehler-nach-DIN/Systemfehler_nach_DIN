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
