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
| TikTok | `wkaisertexas/tiktok-uploader` | `TIKTOK_SESSIONID` / `TIKTOK_COOKIE_PATH` |
| Instagram | `subzeroid/instagrapi` | `INSTAGRAM_*` / `INSTAGRAM_SESSION_PATH` |
| Reddit | eigener Playwright-Webadapter | `REDDIT_STORAGE_STATE` |
| X | `d60/twikit` | `X_*` / `X_COOKIE_PATH` |
| YouTube | `adasq/youtube-studio` | `YOUTUBE_COOKIE_PATH` (lokal z. B. `~/.config/sin-youtube/cookies.json`) |
| Mastodon | `Mastodon.py` / `toot` | `MASTODON_*` |
| Bluesky | `MarshalX/atproto` | `BLUESKY_*` |
| Telegram | `Telethon` | `TELEGRAM_*` / `TELEGRAM_SESSION_PATH` |
| Discord | stdlib Incoming Webhook | `DISCORD_WEBHOOK_URL` |
| Foren | Discourse HTTP / Playwright fallback | `DISCOURSE_*` / `FORUM_STORAGE_STATE` |

Die Python-Bridge selbst benutzt nur die Standardbibliothek und laeuft damit auf macOS/ARM64 und Linux/OCI. Die eigentlichen Community-Clients bleiben optionale Adapter-Abhaengigkeiten und werden erst fuer einen explizit freigegebenen Live-Publisher installiert/aktiviert.

## Tests

```bash
cd platforms_connectors
python3 -m unittest -v test_bridge.py
```

Die Tests sind offline und pruefen alle zehn Plattformen, Pflichtfeldvalidierung, unbekannte Plattformen und den Default-Deny fuer LIVE.
