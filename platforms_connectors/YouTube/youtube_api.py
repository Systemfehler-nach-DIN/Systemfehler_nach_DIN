#!/usr/bin/env python3
"""Offizieller YouTube-Data-API-v3-Adapter.

Der Adapter verwendet OAuth 2.0 und resumable uploads. Er ist absichtlich
stdlib-only: kein Cookie-Browser, keine privaten Studio-Endpunkte und keine
Credentials in Logs. Standard-Sichtbarkeit ist PRIVATE.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from typing import Any, Callable

API_ROOT = "https://www.googleapis.com/youtube/v3"
UPLOAD_ROOT = "https://www.googleapis.com/upload/youtube/v3/videos"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = (
    "https://www.googleapis.com/auth/youtube.upload "
    "https://www.googleapis.com/auth/youtube.readonly "
    "https://www.googleapis.com/auth/youtube.force-ssl"
)
DEFAULT_CLIENT_SECRETS = "~/.config/google/sin-google-apps-oauth-client.json"
DEFAULT_TOKEN_PATH = "~/.config/sin-youtube/youtube-oauth-token.json"
CHUNK_SIZE = 8 * 1024 * 1024


class YouTubeApiError(RuntimeError):
    """Safe, non-secret API failure."""


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def _read_json(path: str | os.PathLike[str]) -> dict[str, Any]:
    try:
        with open(Path(path).expanduser(), encoding="utf-8") as fh:
            value = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise YouTubeApiError(
            f"JSON-Datei nicht lesbar: {Path(path).expanduser()}"
        ) from exc
    if not isinstance(value, dict):
        raise YouTubeApiError(f"JSON-Objekt erwartet: {Path(path).expanduser()}")
    return value


def _safe_error(body: bytes) -> str:
    try:
        value = json.loads(body.decode("utf-8", "replace"))
        errors = value.get("error", value)
        if isinstance(errors, dict):
            return str(errors.get("message") or errors.get("status") or "API-Fehler")[
                :300
            ]
        return str(errors)[:300]
    except Exception:
        return body.decode("utf-8", "replace")[:300] or "API-Fehler"


def _request(
    req: urllib.request.Request,
    timeout: int = 60,
    opener: Callable[..., Any] = urllib.request.urlopen,
):
    last = None
    for attempt in range(3):
        try:
            with opener(req, timeout=timeout) as response:
                return response.status, dict(response.headers), response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read()
            if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                last = exc
                time.sleep(2**attempt)
                continue
            raise YouTubeApiError(
                f"YouTube API HTTP {exc.code}: {_safe_error(body)}"
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt < 2:
                last = exc
                time.sleep(2**attempt)
                continue
            raise YouTubeApiError("YouTube API Netzwerkfehler") from exc
    raise YouTubeApiError("YouTube API Anfrage fehlgeschlagen") from last


def _client_config(path: str) -> dict[str, str]:
    data = _read_json(path)
    data = data.get("installed") or data.get("web") or data
    try:
        return {
            "client_id": data["client_id"],
            "client_secret": data["client_secret"],
            "auth_uri": data.get(
                "auth_uri", "https://accounts.google.com/o/oauth2/auth"
            ),
            "token_uri": data.get("token_uri", TOKEN_URL),
        }
    except KeyError as exc:
        raise YouTubeApiError(
            f"OAuth-Client-Datei unvollständig: {Path(path).expanduser()}"
        ) from exc


@dataclass
class OAuthToken:
    access_token: str
    refresh_token: str | None
    expires_at: float
    client_id: str
    client_secret: str
    token_uri: str = TOKEN_URL

    @classmethod
    def load(cls, token_path: str, client_path: str) -> "OAuthToken":
        raw = _read_json(token_path)
        client = _client_config(client_path)
        access = raw.get("access_token")
        if not access:
            raise YouTubeApiError("OAuth-Token enthält kein access_token")
        expires_at = float(raw.get("expires_at", 0))
        if not expires_at and raw.get("expires_in"):
            expires_at = time.time() + float(raw["expires_in"]) - 60
        return cls(
            access,
            raw.get("refresh_token"),
            expires_at,
            raw.get("client_id", client["client_id"]),
            raw.get("client_secret", client["client_secret"]),
            raw.get("token_uri", client["token_uri"]),
        )

    def refresh_if_needed(self, token_path: str) -> None:
        if self.expires_at > time.time() + 60:
            return
        if not self.refresh_token:
            raise YouTubeApiError(
                "OAuth-Token abgelaufen; erneute Autorisierung erforderlich"
            )
        form = urllib.parse.urlencode(
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode()
        req = urllib.request.Request(
            self.token_uri,
            data=form,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        status, _, body = _request(req, timeout=30)
        if status != 200:
            raise YouTubeApiError(f"OAuth-Token-Erneuerung fehlgeschlagen ({status})")
        value = json.loads(body.decode("utf-8"))
        self.access_token = value["access_token"]
        self.expires_at = time.time() + float(value.get("expires_in", 3600)) - 60
        saved = _read_json(token_path)
        saved.update({"access_token": self.access_token, "expires_at": self.expires_at})
        os.chmod(Path(token_path).expanduser(), 0o600)
        Path(token_path).expanduser().write_text(
            json.dumps(saved, indent=2) + "\n", encoding="utf-8"
        )


class YouTubeApi:
    def __init__(
        self, client_secrets: str | None = None, token_path: str | None = None
    ):
        self.client_path = os.path.expanduser(
            client_secrets
            or os.getenv("YOUTUBE_OAUTH_CLIENT_SECRETS", DEFAULT_CLIENT_SECRETS)
        )
        self.token_path = os.path.expanduser(
            token_path or os.getenv("YOUTUBE_OAUTH_TOKEN", DEFAULT_TOKEN_PATH)
        )
        self.token = OAuthToken.load(self.token_path, self.client_path)
        self.token.refresh_if_needed(self.token_path)

    def _headers(self, content_type: str = "application/json") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token.access_token}",
            "Content-Type": content_type,
            "User-Agent": "SIN-YouTube/1.0",
        }

    def request_json(
        self, method: str, url: str, body: Any = None, timeout: int = 60
    ) -> dict[str, Any]:
        req = urllib.request.Request(
            url,
            method=method,
            headers=self._headers(),
            data=None if body is None else _json_bytes(body),
        )
        status, _, raw = _request(req, timeout=timeout)
        if status < 200 or status >= 300:
            raise YouTubeApiError(f"YouTube API HTTP {status}: {_safe_error(raw)}")
        try:
            return json.loads(raw.decode("utf-8")) if raw else {}
        except json.JSONDecodeError as exc:
            raise YouTubeApiError("YouTube API lieferte ungültiges JSON") from exc

    def channel(self) -> dict[str, Any]:
        """Verifiziert das mit OAuth ausgewählte Konto und liefert den Kanal."""
        url = f"{API_ROOT}/channels?part=id,snippet&mine=true"
        data = self.request_json("GET", url)
        items = data.get("items", [])
        if not items:
            raise YouTubeApiError(
                "OAuth-Konto besitzt keinen erreichbaren YouTube-Kanal"
            )
        return items[0]

    def upload(
        self,
        video_path: str,
        title: str,
        description: str = "",
        privacy: str = "private",
        category_id: str = "22",
        publish_at: str | None = None,
        made_for_kids: bool = False,
    ) -> dict[str, Any]:
        path = Path(video_path).expanduser()
        if not path.is_file():
            raise YouTubeApiError(f"Videodatei nicht gefunden: {path}")
        if privacy not in {"private", "unlisted", "public"}:
            raise YouTubeApiError("privacy muss private, unlisted oder public sein")
        if publish_at and privacy != "private":
            raise YouTubeApiError("publish_at erfordert private Sichtbarkeit")
        size = path.stat().st_size
        mime = (
            "video/mp4" if path.suffix.lower() == ".mp4" else "application/octet-stream"
        )
        status_body: dict[str, Any] = {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": bool(made_for_kids),
        }
        if publish_at:
            status_body["publishAt"] = publish_at
        metadata = {
            "snippet": {
                "title": title,
                "description": description,
                "categoryId": str(category_id),
            },
            "status": status_body,
        }
        headers = self._headers()
        headers.update(
            {"X-Upload-Content-Length": str(size), "X-Upload-Content-Type": mime}
        )
        req = urllib.request.Request(
            f"{UPLOAD_ROOT}?part=snippet,status&uploadType=resumable",
            method="POST",
            headers=headers,
            data=_json_bytes(metadata),
        )
        _, response_headers, _ = _request(req, timeout=60)
        location = response_headers.get("Location") or response_headers.get("location")
        if not location:
            raise YouTubeApiError("YouTube API lieferte keine Resumable-Upload-URL")
        sent = 0
        with path.open("rb") as fh:
            while sent < size:
                chunk = fh.read(CHUNK_SIZE)
                put_headers = {
                    "Authorization": headers["Authorization"],
                    "Content-Length": str(len(chunk)),
                    "Content-Range": f"bytes {sent}-{sent + len(chunk) - 1}/{size}",
                    "Content-Type": mime,
                    "User-Agent": "SIN-YouTube/1.0",
                }
                put = urllib.request.Request(
                    location, method="PUT", headers=put_headers, data=chunk
                )
                code, response_headers, raw = _request(put, timeout=600)
                if code in (200, 201):
                    result = json.loads(raw.decode("utf-8"))
                    return result
                if code != 308:
                    raise YouTubeApiError(f"Upload fehlgeschlagen (HTTP {code})")
                range_header = response_headers.get("Range", "")
                if range_header.startswith("bytes="):
                    sent = int(range_header.rsplit("-", 1)[1]) + 1
                else:
                    sent += len(chunk)
        raise YouTubeApiError("Upload endete ohne Video-ID")

    def delete_video(self, video_id: str) -> dict[str, Any]:
        """Löscht ein eigenes Testvideo nach unabhängiger Verifikation."""
        return self.request_json(
            "DELETE", f"{API_ROOT}/videos?id={urllib.parse.quote(video_id)}"
        )

    def video(self, video_id: str) -> dict[str, Any]:
        """Liest Metadaten und Sichtbarkeit eines Videos zur unabhängigen Prüfung."""
        data = self.request_json(
            "GET",
            f"{API_ROOT}/videos?part=snippet,status&id={urllib.parse.quote(video_id)}",
        )
        items = data.get("items", [])
        if not items:
            raise YouTubeApiError("Video-ID nicht gefunden oder nicht zugreifbar")
        return items[0]

    def search(
        self,
        query: str,
        *,
        resource_type: str = "video",
        channel_id: str | None = None,
        max_results: int = 25,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """Sucht Videos, Kanäle oder Playlists über die offizielle API."""
        if resource_type not in {"video", "channel", "playlist"}:
            raise YouTubeApiError("resource_type muss video, channel oder playlist sein")
        params: dict[str, Any] = {
            "part": "snippet",
            "q": query,
            "type": resource_type,
            "maxResults": min(max(1, max_results), 50),
        }
        if channel_id:
            params["channelId"] = channel_id
        if page_token:
            params["pageToken"] = page_token
        return self.request_json("GET", f"{API_ROOT}/search?{urllib.parse.urlencode(params)}")

    def list_playlists(
        self, *, mine: bool = True, channel_id: str | None = None,
        max_results: int = 50, page_token: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "part": "snippet,status,contentDetails",
            "maxResults": min(max(1, max_results), 50),
        }
        if mine:
            params["mine"] = "true"
        elif channel_id:
            params["channelId"] = channel_id
        else:
            raise YouTubeApiError("list_playlists benötigt mine oder channel_id")
        if page_token:
            params["pageToken"] = page_token
        return self.request_json("GET", f"{API_ROOT}/playlists?{urllib.parse.urlencode(params)}")

    def create_playlist(
        self, title: str, description: str = "", privacy: str = "private"
    ) -> dict[str, Any]:
        if privacy not in {"private", "unlisted", "public"}:
            raise YouTubeApiError("privacy muss private, unlisted oder public sein")
        body = {
            "snippet": {"title": title, "description": description},
            "status": {"privacyStatus": privacy},
        }
        return self.request_json("POST", f"{API_ROOT}/playlists?part=snippet,status", body)

    def update_playlist(
        self, playlist_id: str, *, title: str | None = None,
        description: str | None = None, privacy: str | None = None
    ) -> dict[str, Any]:
        current = self.request_json(
            "GET", f"{API_ROOT}/playlists?part=snippet,status&id={urllib.parse.quote(playlist_id)}"
        )
        items = current.get("items", [])
        if not items:
            raise YouTubeApiError("Playlist-ID nicht gefunden oder nicht zugreifbar")
        item = items[0]
        snippet = dict(item.get("snippet", {}))
        snippet = {key: snippet.get(key, "") for key in ("title", "description")}
        status = {"privacyStatus": item.get("status", {}).get("privacyStatus", "private")}
        if title is not None:
            snippet["title"] = title
        if description is not None:
            snippet["description"] = description
        if privacy is not None:
            if privacy not in {"private", "unlisted", "public"}:
                raise YouTubeApiError("privacy muss private, unlisted oder public sein")
            status["privacyStatus"] = privacy
        return self.request_json(
            "PUT", f"{API_ROOT}/playlists?part=snippet,status",
            {"id": playlist_id, "snippet": snippet, "status": status},
        )

    def delete_playlist(self, playlist_id: str) -> dict[str, Any]:
        return self.request_json(
            "DELETE", f"{API_ROOT}/playlists?id={urllib.parse.quote(playlist_id)}"
        )

    def list_comment_threads(
        self, video_id: str, max_results: int = 100, page_token: str | None = None
    ) -> dict[str, Any]:
        params = {
            "part": "snippet,replies",
            "videoId": video_id,
            "maxResults": min(max(1, max_results), 100),
            "textFormat": "plainText",
        }
        if page_token:
            params["pageToken"] = page_token
        return self.request_json(
            "GET", f"{API_ROOT}/commentThreads?{urllib.parse.urlencode(params)}"
        )

    def list_replies(
        self, parent_id: str, max_results: int = 100, page_token: str | None = None
    ) -> dict[str, Any]:
        params = {
            "part": "snippet",
            "parentId": parent_id,
            "maxResults": min(max(1, max_results), 100),
            "textFormat": "plainText",
        }
        if page_token:
            params["pageToken"] = page_token
        return self.request_json(
            "GET", f"{API_ROOT}/comments?{urllib.parse.urlencode(params)}"
        )

    def comment(self, video_id: str, text: str) -> dict[str, Any]:
        """Kompatibilitätsalias für einen neuen Top-Level-Kommentar."""
        body = {
            "snippet": {
                "videoId": video_id,
                "topLevelComment": {"snippet": {"textOriginal": text}},
            }
        }
        return self.request_json(
            "POST", f"{API_ROOT}/commentThreads?part=snippet", body
        )

    def reply(self, parent_id: str, text: str) -> dict[str, Any]:
        body = {"snippet": {"parentId": parent_id, "textOriginal": text}}
        return self.request_json("POST", f"{API_ROOT}/comments?part=snippet", body)

    def update_comment(self, comment_id: str, text: str) -> dict[str, Any]:
        body = {"id": comment_id, "snippet": {"textOriginal": text}}
        return self.request_json("PUT", f"{API_ROOT}/comments?part=snippet", body)

    def delete_comment(self, comment_id: str) -> dict[str, Any]:
        return self.request_json(
            "DELETE", f"{API_ROOT}/comments?id={urllib.parse.quote(comment_id)}"
        )

    def moderate_comment(
        self, comment_id: str, status: str, ban_author: bool = False
    ) -> dict[str, Any]:
        allowed = {"heldForReview", "published", "rejected", "likelySpam"}
        if status not in allowed:
            raise YouTubeApiError(f"Ungültiger Moderationsstatus: {status}")
        params = {"id": comment_id, "moderationStatus": status}
        if ban_author:
            params["banAuthor"] = "true"
        return self.request_json(
            "POST",
            f"{API_ROOT}/comments/setModerationStatus?{urllib.parse.urlencode(params)}",
        )

    def update_video(
        self,
        video_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        privacy: str | None = None,
        tags: list[str] | None = None,
        category_id: str | None = None,
        publish_at: str | None = None,
    ) -> dict[str, Any]:
        current = self.video(video_id)
        current_snippet = current.get("snippet", {})
        current_status = current.get("status", {})
        snippet = {
            "title": current_snippet.get("title", ""),
            "description": current_snippet.get("description", ""),
            "categoryId": str(current_snippet.get("categoryId", "22")),
        }
        if current_snippet.get("tags") is not None:
            snippet["tags"] = current_snippet["tags"]
        status = {
            "privacyStatus": current_status.get("privacyStatus", "private"),
            "selfDeclaredMadeForKids": bool(
                current_status.get("selfDeclaredMadeForKids", False)
            ),
        }
        if title is not None:
            snippet["title"] = title
        if description is not None:
            snippet["description"] = description
        if tags is not None:
            snippet["tags"] = tags
        if category_id is not None:
            snippet["categoryId"] = str(category_id)
        if privacy is not None:
            if privacy not in {"private", "unlisted", "public"}:
                raise YouTubeApiError("privacy muss private, unlisted oder public sein")
            status["privacyStatus"] = privacy
        if publish_at is not None:
            status["publishAt"] = publish_at
            status["privacyStatus"] = "private"
        return self.request_json(
            "PUT",
            f"{API_ROOT}/videos?part=snippet,status",
            {"id": video_id, "snippet": snippet, "status": status},
        )

    def set_thumbnail(self, video_id: str, image_path: str) -> dict[str, Any]:
        path = Path(image_path).expanduser()
        if not path.is_file():
            raise YouTubeApiError(f"Thumbnail nicht gefunden: {path}")
        mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(
            path.suffix.lower()
        )
        if not mime:
            raise YouTubeApiError("Thumbnail muss JPG oder PNG sein")
        data = path.read_bytes()
        if len(data) > 2 * 1024 * 1024:
            raise YouTubeApiError("Thumbnail überschreitet 2 MiB")
        req = urllib.request.Request(
            f"{API_ROOT}/thumbnails/set?videoId={urllib.parse.quote(video_id)}",
            method="POST",
            headers={**self._headers(mime), "Content-Length": str(len(data))},
            data=data,
        )
        status, _, raw = _request(req, timeout=120)
        if status < 200 or status >= 300:
            raise YouTubeApiError(f"Thumbnail-Upload HTTP {status}: {_safe_error(raw)}")
        return json.loads(raw.decode("utf-8")) if raw else {}

    def playlist_items(
        self, playlist_id: str, max_results: int = 50, page_token: str | None = None
    ) -> dict[str, Any]:
        params = {
            "part": "snippet,contentDetails",
            "playlistId": playlist_id,
            "maxResults": min(max(1, max_results), 50),
        }
        if page_token:
            params["pageToken"] = page_token
        return self.request_json(
            "GET", f"{API_ROOT}/playlistItems?{urllib.parse.urlencode(params)}"
        )

    def add_to_playlist(self, playlist_id: str, video_id: str) -> dict[str, Any]:
        body = {
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id},
            }
        }
        return self.request_json("POST", f"{API_ROOT}/playlistItems?part=snippet", body)

    def remove_from_playlist(self, playlist_item_id: str) -> dict[str, Any]:
        return self.request_json(
            "DELETE",
            f"{API_ROOT}/playlistItems?id={urllib.parse.quote(playlist_item_id)}",
        )


def authorize(client_secrets: str, token_path: str, port: int = 0) -> None:
    """Einmalige lokale OAuth-Autorisierung mit localhost-Callback."""
    client = _client_config(client_secrets)
    state = os.urandom(16).hex()
    result: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            values = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if values.get("state", [""])[0] != state:
                self.send_error(400, "invalid state")
                return
            result["code"] = values.get("code", [""])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK - Fenster kann geschlossen werden.")

        def log_message(self, *_):
            return

    server = HTTPServer(("localhost", port), Handler)
    actual_port = server.server_port
    redirect = os.getenv(
        "YOUTUBE_OAUTH_REDIRECT_URI", f"http://localhost:{actual_port}/callback"
    )
    query = urllib.parse.urlencode(
        {
            "client_id": client["client_id"],
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )
    Thread(target=server.handle_request, daemon=True).start()
    url = f"{client['auth_uri']}?{query}"
    print("OAuth-URL (keine Secrets):", url)
    webbrowser.open(url)
    deadline = time.time() + 300
    while time.time() < deadline and "code" not in result:
        time.sleep(0.2)
    server.server_close()
    if not result.get("code"):
        raise YouTubeApiError("OAuth-Autorisierung abgebrochen oder Timeout")
    form = urllib.parse.urlencode(
        {
            "code": result["code"],
            "client_id": client["client_id"],
            "client_secret": client["client_secret"],
            "redirect_uri": redirect,
            "grant_type": "authorization_code",
        }
    ).encode()
    req = urllib.request.Request(
        client["token_uri"],
        data=form,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    _, _, raw = _request(req, timeout=30)
    token = json.loads(raw.decode("utf-8"))
    token.update(
        {
            "client_id": client["client_id"],
            "client_secret": client["client_secret"],
            "expires_at": time.time() + float(token.get("expires_in", 3600)) - 60,
        }
    )
    target = Path(token_path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(token, indent=2) + "\n", encoding="utf-8")
    os.chmod(target, 0o600)
    print(f"OAuth-Token gespeichert: {target}")


def main() -> int:
    parser = argparse.ArgumentParser(description="SIN-YouTube über YouTube Data API v3")
    parser.add_argument("--authorize", action="store_true")
    parser.add_argument(
        "--client-secrets",
        default=os.getenv("YOUTUBE_OAUTH_CLIENT_SECRETS", DEFAULT_CLIENT_SECRETS),
    )
    parser.add_argument(
        "--token", default=os.getenv("YOUTUBE_OAUTH_TOKEN", DEFAULT_TOKEN_PATH)
    )
    parser.add_argument("--channel", action="store_true")
    parser.add_argument(
        "--inspect", metavar="VIDEO_ID", help="Video prüfen, ohne zu ändern"
    )
    parser.add_argument("--delete-video", metavar="VIDEO_ID")
    parser.add_argument("--video")
    parser.add_argument("--search", metavar="QUERY")
    parser.add_argument("--search-type", choices=["video", "channel", "playlist"], default="video")
    parser.add_argument("--search-channel")
    parser.add_argument("--max-results", type=int, default=25)
    parser.add_argument("--title")
    parser.add_argument("--description")
    parser.add_argument("--list-comments", metavar="VIDEO_ID")
    parser.add_argument("--list-replies", metavar="COMMENT_ID")
    parser.add_argument("--comment-video", metavar="VIDEO_ID")
    parser.add_argument("--reply-to", metavar="COMMENT_ID")
    parser.add_argument("--comment-text")
    parser.add_argument("--update-comment", metavar="COMMENT_ID")
    parser.add_argument("--delete-comment", metavar="COMMENT_ID")
    parser.add_argument("--moderate-comment", metavar="COMMENT_ID")
    parser.add_argument(
        "--moderation-status",
        choices=["heldForReview", "published", "rejected", "likelySpam"],
    )
    parser.add_argument("--ban-author", action="store_true")
    parser.add_argument("--update-video", metavar="VIDEO_ID")
    parser.add_argument("--tags", help="Kommagetrennte Tags für --update-video")
    parser.add_argument("--category-id")
    parser.add_argument("--thumbnail-video", metavar="VIDEO_ID")
    parser.add_argument("--thumbnail")
    parser.add_argument("--playlist-id", metavar="PLAYLIST_ID")
    parser.add_argument("--playlists", action="store_true", help="eigene Playlists auflisten")
    parser.add_argument("--playlist-list", metavar="PLAYLIST_ID")
    parser.add_argument("--playlist-create", action="store_true")
    parser.add_argument("--playlist-update", metavar="PLAYLIST_ID")
    parser.add_argument("--playlist-delete", metavar="PLAYLIST_ID")
    parser.add_argument("--playlist-description", default="")
    parser.add_argument("--playlist-add-video", metavar="VIDEO_ID")
    parser.add_argument("--playlist-remove-item", metavar="PLAYLIST_ITEM_ID")
    parser.add_argument(
        "--privacy", choices=["private", "unlisted", "public"], default=None
    )
    parser.add_argument("--publish-at")
    parser.add_argument(
        "--dry-run", action="store_true", help="Kanal/Datei prüfen, nicht hochladen"
    )
    args = parser.parse_args()
    if args.authorize:
        authorize(args.client_secrets, args.token)
        return 0
    try:
        api = YouTubeApi(args.client_secrets, args.token)
        if args.delete_video:
            print(json.dumps(api.delete_video(args.delete_video), ensure_ascii=False))
            return 0
        if args.inspect:
            item = api.video(args.inspect)
            print(
                json.dumps(
                    {
                        "id": item["id"],
                        "title": item["snippet"]["title"],
                        "privacy": item["status"]["privacyStatus"],
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        if args.channel:
            channel = api.channel()
            print(
                json.dumps(
                    {"id": channel["id"], "title": channel["snippet"]["title"]},
                    ensure_ascii=False,
                )
            )
            return 0
        if args.search:
            print(json.dumps(api.search(args.search, resource_type=args.search_type,
                channel_id=args.search_channel, max_results=args.max_results), ensure_ascii=False))
            return 0
        if args.playlists:
            print(json.dumps(api.list_playlists(max_results=args.max_results), ensure_ascii=False))
            return 0
        if args.playlist_create:
            if not args.title:
                parser.error("--playlist-create benötigt --title")
            print(json.dumps(api.create_playlist(args.title, args.playlist_description,
                args.privacy or "private"), ensure_ascii=False))
            return 0
        if args.playlist_update:
            print(json.dumps(api.update_playlist(args.playlist_update, title=args.title,
                description=args.playlist_description if args.playlist_description else None,
                privacy=args.privacy), ensure_ascii=False))
            return 0
        if args.playlist_delete:
            print(json.dumps(api.delete_playlist(args.playlist_delete), ensure_ascii=False))
            return 0
        if args.list_comments:
            print(
                json.dumps(
                    api.list_comment_threads(args.list_comments), ensure_ascii=False
                )
            )
            return 0
        if args.list_replies:
            print(json.dumps(api.list_replies(args.list_replies), ensure_ascii=False))
            return 0
        if args.comment_video:
            if not args.comment_text:
                parser.error("--comment-video benötigt --comment-text")
            print(
                json.dumps(
                    api.comment(args.comment_video, args.comment_text),
                    ensure_ascii=False,
                )
            )
            return 0
        if args.reply_to:
            if not args.comment_text:
                parser.error("--reply-to benötigt --comment-text")
            print(
                json.dumps(
                    api.reply(args.reply_to, args.comment_text), ensure_ascii=False
                )
            )
            return 0
        if args.update_comment:
            if not args.comment_text:
                parser.error("--update-comment benötigt --comment-text")
            print(
                json.dumps(
                    api.update_comment(args.update_comment, args.comment_text),
                    ensure_ascii=False,
                )
            )
            return 0
        if args.delete_comment:
            print(
                json.dumps(api.delete_comment(args.delete_comment), ensure_ascii=False)
            )
            return 0
        if args.moderate_comment:
            if not args.moderation_status:
                parser.error("--moderate-comment benötigt --moderation-status")
            print(
                json.dumps(
                    api.moderate_comment(
                        args.moderate_comment, args.moderation_status, args.ban_author
                    ),
                    ensure_ascii=False,
                )
            )
            return 0
        if args.update_video:
            tags = (
                [x.strip() for x in args.tags.split(",") if x.strip()]
                if args.tags
                else None
            )
            print(
                json.dumps(
                    api.update_video(
                        args.update_video,
                        title=args.title,
                        description=args.description,
                        privacy=args.privacy,
                        tags=tags,
                        category_id=args.category_id,
                        publish_at=args.publish_at,
                    ),
                    ensure_ascii=False,
                )
            )
            return 0
        if args.thumbnail_video:
            if not args.thumbnail:
                parser.error("--thumbnail-video benötigt --thumbnail")
            print(
                json.dumps(
                    api.set_thumbnail(args.thumbnail_video, args.thumbnail),
                    ensure_ascii=False,
                )
            )
            return 0
        if args.playlist_list:
            print(
                json.dumps(api.playlist_items(args.playlist_list), ensure_ascii=False)
            )
            return 0
        if args.playlist_add_video:
            if not args.playlist_id:
                parser.error("--playlist-add-video benötigt --playlist-id")
            print(
                json.dumps(
                    api.add_to_playlist(args.playlist_id, args.playlist_add_video),
                    ensure_ascii=False,
                )
            )
            return 0
        if args.playlist_remove_item:
            print(
                json.dumps(
                    api.remove_from_playlist(args.playlist_remove_item),
                    ensure_ascii=False,
                )
            )
            return 0
        if args.dry_run:
            channel = api.channel()
            video_ok = not args.video or Path(args.video).expanduser().is_file()
            if not video_ok:
                raise YouTubeApiError(
                    f"Videodatei nicht gefunden: {Path(args.video).expanduser()}"
                )
            print(
                json.dumps(
                    {
                        "ok": True,
                        "dry_run": True,
                        "channel_id": channel["id"],
                        "channel_title": channel["snippet"]["title"],
                        "video_checked": bool(args.video),
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        if not args.video or not args.title:
            parser.error("--video und --title erforderlich")
        result = api.upload(
            args.video,
            args.title,
            args.description or "",
            args.privacy or "private",
            publish_at=args.publish_at,
        )
        print(
            f"Upload OK: videoId={result.get('id')} privacy={args.privacy or 'private'}"
        )
        return 0
    except YouTubeApiError as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
