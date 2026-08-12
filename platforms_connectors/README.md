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

## Buffer-first Adaptergrenzen

Für die neun verbundenen Systemfehler-Kanäle ist Buffer der primäre Publishing-/Scheduling-Weg. Direkte Adapter bleiben als offizielle Fallbacks/Account-Setup-Werkzeuge erhalten.

## Adaptergrenzen

| Plattform | Backend/Wrapper | Credential-Quelle |
|---|---|---|
| TikTok | SIN-Browser-Use CLI 3.0 / TikTok Studio UI | SIN-Chrome `bot` |
| YouTube | Buffer Account 3 / Channel `6a7cf0c4b2d9d57743679762` | Buffer account key from Infisical |
| Instagram | Buffer Account 1 | `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID` |
| Facebook | Buffer Account 2 | `FACEBOOK_PAGE_ACCESS_TOKEN`, `FACEBOOK_PAGE_ID` |
| X | offizielle X API v2 | `X_ACCESS_TOKEN` |
| Reddit | offizielle Reddit OAuth API | `REDDIT_ACCESS_TOKEN` |
| LinkedIn | offizielle LinkedIn Posts API | `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_AUTHOR_URN` |
| Threads | offizielle Threads API | `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID` |
| Pinterest | offizielle Pinterest API v5 | `PINTEREST_ACCESS_TOKEN`, `PINTEREST_BOARD_ID` |
| Bluesky | offizielles AT Protocol | App-Passwort |
| Mastodon | offizielle Mastodon REST API | Access Token |
| Telegram | offizielle Telegram Bot API | Bot Token |
| Discord | offizieller Incoming Webhook | Webhook URL |
| Postiz | optionaler self-hosted API-Layer | Runtime-Token |


### TikTok Social

Die kanonische TikTok-Integration liegt unter `TikTok/`. Organische Uploads,
Kommentare, Analytics und Trend-Recherche laufen über TikTok Studio bzw.
tiktok.com im authentifizierten SIN-Chrome-`bot`; für mehrschrittige Aktionen
ist SIN-Browser-Use CLI 3.0 der Standard. TikTok Shop und Ads bleiben getrennt
in `sin-tiktok-shop` und `sin-tiktok-ads`. Es gibt keinen öffentlichen Upload-
API-Pfad für reguläre TikTok-Konten. Live-Publishing bleibt außerhalb der
allgemeinen Bridge fail-closed und benötigt einen explizit geprüften UI-Lauf.

### Buffer YouTube route

Der verbundene Kanal `Systemfehler_nach_DIN` wird über Buffer Account 3 geplant
und veröffentlicht (`Buffer channel 6a7cf0c4b2d9d57743679762`, YouTube-ID
`UCBWRl7VXRdy0kcsoV7or7Uw`). Die direkten YouTube-API-/OAuth-Dateien bleiben
als manuelle Fallbacks für Kontoverifikation, Kommentare und nicht von Buffer
abgedeckte Studio-Funktionen. Für Buffer-Videos sind eine stabile öffentliche
HTTPS-Video-URL sowie `metadata.youtube.title`, `categoryId` und `privacy` nötig.

### Buffer account routing

`platforms_connectors/Buffer/accounts.json` ist die nicht-geheime Registry.
`buffer_targets` kann mehrere Targets mit `account`, `platform`, `channel_id`
und `media_type` enthalten. Der Adapter wählt `BUFFER_API_KEY_ACCOUNT_1..3`
(runtime aus Infisical) anhand des Accounts; `BUFFER_API_KEY` bleibt als
kompatibler Einzelaccount-Fallback.

## Tests

```bash
cd platforms_connectors
python3 -m unittest -v test_bridge.py
python3 -m pytest -q YouTube
```

Die Tests sind offline und prüfen alle offiziellen Connectoren, gemockte Live-Pfade, Pflichtfeldvalidierung, unbekannte Plattformen und den Default-Deny für LIVE. Instagram Private API (`instagrapi`), Twikit, Playwright und Cookie-/Passwort-Backends sind keine Bridge-Fallbacks.
