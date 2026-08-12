# SYSTEMFEHLER_nach_DIN Social Bridge

Lokaler Python-HTTP-Bridge fuer `publish_everywhere.yml`. Die Bridge normalisiert fuer alle Plattformen dieselbe Payload:

`title, excerpt, body, media_url, url, cta`

## Sicherheitsmodell

- Default: `PUBLISH_MODE=DRY_RUN`.
- Selbst `PUBLISH_MODE=LIVE` plus `ALLOW_REAL_POSTS=true` reicht absichtlich nicht fuer einen echten Post: die Bridge verweigert LIVE, solange kein separat gepruefter adapter-spezifischer Live-Publisher installiert ist.
- Keine Credentials, Cookie-Inhalte oder Session-Daten werden geloggt.
- Secrets kommen nur aus Environment, `.env` ausserhalb Git oder externen Secret Stores.
- Session-/Cookie-Dateien werden nur ueber Pfade referenziert.
- Challenge/Captcha/2FA/Checkpoint werden nicht umgangen.

## Start

```bash
python3 bridge.py --host 0.0.0.0 --port 18765
```

Health: `GET /health`

Publish/Dry-Run: `POST /publish` mit der Standard-Payload. Optional kann ein Wrapper-Objekt `{"payload": {...}, "platforms": ["x", "youtube"]}` gesendet werden.

## Adaptergrenzen

| Plattform | Backend/Wrapper | Credential-/Session-Quelle |
|---|---|---|
| TikTok | SIN-Browser-Use CLI 3.0 / TikTok Studio UI | `TIKTOK_PARTNER_EMAIL` / SIN-Chrome `bot` profile |
| Instagram | `subzeroid/instagrapi` | `INSTAGRAM_*` / `INSTAGRAM_SESSION_PATH` |
| Reddit | eigener Playwright-Webadapter | `REDDIT_STORAGE_STATE` |
| X | `d60/twikit` | `X_*` / `X_COOKIE_PATH` |
| YouTube | offizieller YouTube Data API v3-Adapter (OAuth 2.0, resumable upload) | `YOUTUBE_OAUTH_CLIENT_SECRETS`, `YOUTUBE_OAUTH_TOKEN`, `YOUTUBE_VIDEO_PATH` |
| Mastodon | `Mastodon.py` / `toot` | `MASTODON_*` |
| Bluesky | `MarshalX/atproto` | `BLUESKY_*` |
| Telegram | `Telethon` | `TELEGRAM_*` / `TELEGRAM_SESSION_PATH` |
| Discord | stdlib Incoming Webhook | `DISCORD_WEBHOOK_URL` |
| Foren | Discourse HTTP / Playwright fallback | `DISCOURSE_*` / `FORUM_STORAGE_STATE` |

### TikTok Social

Die kanonische TikTok-Integration liegt unter `TikTok/`. Organische Uploads,
Kommentare, Analytics und Trend-Recherche laufen über TikTok Studio bzw.
tiktok.com im authentifizierten SIN-Chrome-`bot`; für mehrschrittige Aktionen
ist SIN-Browser-Use CLI 3.0 der Standard. TikTok Shop und Ads bleiben getrennt
in `sin-tiktok-shop` und `sin-tiktok-ads`. Es gibt keinen öffentlichen Upload-
API-Pfad für reguläre TikTok-Konten. Live-Publishing bleibt außerhalb der
allgemeinen Bridge fail-closed und benötigt einen explizit geprüften UI-Lauf.

### YouTube API

Die Bridge nutzt für Uploads, Metadaten, Sichtbarkeit und Planung ausschließlich `YouTube/youtube_api.py` und die offizielle YouTube Data API v3. Browser/Cookies bleiben nur als Fallback für Community-Funktionen, die die API nicht anbietet. Standard ist `PRIVATE`; Live-Upload benötigt zusätzlich `PUBLISH_MODE=LIVE`, `ALLOW_REAL_POSTS=true` und die explizite Freigabe `YOUTUBE_API_LIVE_APPROVED=true`.

Einmalige Einrichtung mit einer Google-Cloud-OAuth-Clientdatei (Desktop-App):

```bash
python3 YouTube/youtube_api.py --authorize --client-secrets ~/.config/google/sin-google-apps-oauth-client.json
python3 YouTube/youtube_api.py --channel --token ~/.config/sin-youtube/youtube-oauth-token.json
```

Die erzeugte Token-Datei bleibt lokal und erhält Modus `0600`. Für Kommentare und Moderation muss der Token zusätzlich den Scope `youtube.force-ssl` besitzen; nach Scope-Änderungen erneut `--authorize` ausführen. Unterstützt werden Kommentare lesen/schreiben/antworten/bearbeiten/löschen, Moderationsstatus, Video-Metadaten, Thumbnails und Playlist-Items. Cloud-Projekt- oder Credential-Erstellung erfolgt nicht automatisch.

Community-Posts sind nicht Teil der öffentlichen Data API. `YouTube/youtube_community.py` nutzt standardmäßig SIN-Browser-Use (Browser Use CLI 3.0) über den eingeloggten SIN-Chrome-`bot`; der Legacy-Playwright-Weg bleibt mit `--backend playwright` explizit auswählbar. Live bleibt fail-closed und benötigt `PUBLISH_MODE=LIVE`, `ALLOW_REAL_POSTS=true` und `YOUTUBE_BROWSER_LIVE_APPROVED=true`; standardmäßig ist DRY_RUN.

Die Python-Bridge selbst benutzt nur die Standardbibliothek und laeuft damit auf macOS/ARM64 und Linux/OCI. Die eigentlichen Community-Clients bleiben optionale Adapter-Abhaengigkeiten und werden erst fuer einen explizit freigegebenen Live-Publisher installiert/aktiviert.

## Tests

```bash
cd platforms_connectors
python3 -m unittest -v test_bridge.py
python3 -m pytest -q YouTube
```

Die Tests sind offline und pruefen alle zehn Plattformen, Pflichtfeldvalidierung, unbekannte Plattformen und den Default-Deny fuer LIVE.
