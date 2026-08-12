# Social Publishing Decisions — T-0001

Stand: 2026-08-11. Research only: keine Credentials erzeugt, keine echten Posts versendet.

## YouTube-Identität und Chrome-Profil

Für YouTube-Browserarbeit wird standardmäßig das eingeloggte SIN-Chrome-
Profil `bot` mit der Identity-Lock-Identität
`zukunftsorientierte.energie@gmail.com` / `Systemfehler_nach_DIN`
wiederverwendet. Dadurch bleibt die Google-Anmeldung erhalten. Agenten öffnen
für ihre Arbeit ein neues Fenster oder neue Tabs **innerhalb dieses Profils**;
bestehende Operator-Tabs werden nicht geschlossen oder verändert. Ein anderes
Chrome-Profil ist nur nach ausdrücklichem Benutzerbefehl zulässig.

## Architekturentscheidung

Die spaetere `social_bridge_url` wird als lokaler Python-HTTP-Service mit einheitlicher Payload (`title`, `excerpt`, `body`, `media_url`, `url`, `cta`) gebaut. Standard ist immer `DRY_RUN`/`DRAFT`. Secrets und Session-Dateien kommen ausschliesslich ueber Environment bzw. externe Secret-Injection; niemals in Git, YAML, Markdown oder Logs.

Fuer geschlossene Plattformen gilt: **offizielle API zuerst; fuer Browser-Luecken SIN-Browser-Use (Browser Use CLI 3.0) im authentifizierten SIN-Chrome-Bot als schneller Session-Weg; Playwright nur als expliziter Legacy-Fallback.** Fuer offene Protokolle oder explizit fuer Automation gedachte Webhooks/Bot-Schnittstellen wird der native offene Weg bevorzugt, weil Browser-Imitation dort keinen Vorteil bringt.

## Entscheidungsmatrix

| Plattform | Primaerwahl | Alternative 2 | Lizenz(en) | Auth | Medien | Risiko / Aufwand |
|---|---|---|---|---|---|---|
| TikTok | `wkaisertexas/tiktok-uploader` | `haziq-exe/TikTokAutoUploader` bzw. eigener Playwright-Adapter | MIT / MIT; Playwright Apache-2.0 | Cookies / `sessionid` | Video | hoch / mittel |
| Instagram | `subzeroid/instagrapi` | eigener Playwright-Webadapter | MIT / Apache-2.0 | Private-API-Session bzw. Browser-Session | Bild, Video, Reel, Album | hoch / mittel |
| Reddit | eigener Playwright-Webadapter | `public-clis/rdt-cli` als Cookie-/Webauth-Referenz | Apache-2.0 / Apache-2.0 | Browser-Cookies | Text, Link, Bild/Video via UI | mittel-hoch / mittel |
| X | `d60/twikit` | eigener Playwright-Webadapter | MIT / Apache-2.0 | Cookies / Web-Session | Text, Bild, Video | hoch / mittel |
| YouTube | `adasq/youtube-studio` | eigener Playwright-YouTube-Studio-Adapter | MIT / Apache-2.0 | Google/YouTube-Cookies + Session | Video | mittel-hoch / mittel |
| Mastodon | `Mastodon.py` | `ihabunek/toot` | MIT / GPL-3.0 | OAuth/User-Token | Text, Bild, Video | niedrig / niedrig |
| Bluesky | `MarshalX/atproto` | `bluesky-social/@atproto/api` | MIT / MIT oder Apache-2.0 | ATProto Session/App-Password | Text, Bild, Video | niedrig / niedrig |
| Telegram | `LonamiWebs/Telethon` | Telegram Bot API | MIT / Plattformprotokoll | MTProto Session bzw. Bot-Token | Text, Bild, Video, Datei | niedrig-mittel / niedrig |
| Discord | Incoming Webhook via stdlib HTTP | `Rapptz/discord.py` | kein SDK / MIT | Webhook-Secret bzw. Bot-Token | Text, Embeds, Dateien | niedrig / niedrig |
| Foren | Discourse HTTP API, falls Discourse | eigener Playwright-Adapter fuer sonstige Foren | Discourse GPL-2.0-or-later / Playwright Apache-2.0 | forumabhaengig | forumabhaengig | mittel / forumabhaengig |

## TikTok

**Primaer: `wkaisertexas/tiktok-uploader`** — https://github.com/wkaisertexas/tiktok-uploader

- MIT, 2026 aktiv gepflegt.
- Python + Playwright; macOS und Linux.
- Nutzt Browser-Cookies/`sessionid` und kann Videos samt Caption/Hashtags/Scheduling hochladen.
- Vorteil: direkte Passung zum vorhandenen Session-first Zielbild.
- Risiko: TikTok kann Automation, Session-/IP-Wechsel oder zu viele Uploads blockieren. Kein Massenuploading, kein unbegrenztes Retry.

**Alternative: `haziq-exe/TikTokAutoUploader`** — https://github.com/haziq-exe/TikTokAutoUploader

- MIT (GitHub license metadata verifiziert), 2026 aktiv.
- Session-basierter Uploader mit Phantomwright/Playwright-orientierter Anti-Detection.
- Mehr bewegliche Abhaengigkeiten und explizite Stealth-Schicht; dadurch groesseres Betriebs-/Account-Risiko.

**Offizieller Fallback:** TikTok Content Posting API.

**T-0003:** Wrapper um `tiktok-uploader`; Draft-only bis explizit freigeschaltet.

## Instagram

**Primaer: `subzeroid/instagrapi`** — https://github.com/subzeroid/instagrapi

- MIT, grosse und 2026 aktive Community.
- Instagram Private API mit persistierbarer Session.
- Unterstuetzt Fotos, Videos, Alben, Stories und Clips/Reels je aktuellem Library-Support.
- Python und portabel fuer macOS ARM64/Linux.
- Risiko: Challenge/2FA/Checkpoint und interne API-Aenderungen.

**Alternative: eigener Playwright-Webadapter** — https://github.com/microsoft/playwright

- Apache-2.0.
- Persistentes Browserprofil/Storage-State; Upload ueber echten Web-Composer.
- Vorteil: folgt dem Webclient; Nachteil: DOM-/Bot-Detection-Fragilitaet.

**Offizieller Fallback:** Instagram Graph API fuer unterstuetzte Business-/Creator-Faelle.

**T-0003:** `instagrapi` primaer, Playwright austauschbarer Fallback.

## Reddit

**Primaer: eigener Playwright-Webadapter** — https://github.com/microsoft/playwright

- Apache-2.0.
- Verwendet bestehende Browser-Session statt App-Key.
- New-Reddit-Composer kann Text/Link/Medien abbilden.
- Risiko: UI-Aenderungen, Rate-Limits und Subreddit-spezifische Regeln.

**Alternative/Referenz: `public-clis/rdt-cli`** — https://github.com/public-clis/rdt-cli

- Apache-2.0, 2026 aktiv.
- Extrahiert Browser-Cookies und implementiert Reddit-Webinteraktionen ueber die eingeloggte Session.
- Aktuell kein gleichwertig vollstaendig dokumentierter Create-Post/Media-Uploader; deshalb Auth-/Cookie-Referenz statt Primaer-Publisher.

**Offizieller Fallback:** Reddit API/PRAW.

**T-0003:** Playwright-Postingadapter; `rdt-cli` nicht vendoren.

## X

**Primaer: `d60/twikit`** — https://github.com/d60/twikit

- MIT; Releases 2.3.x im Februar 2026, aktuelle Login-/Create-Tweet-Fixes.
- Python Web-Client/GraphQL mit Cookie-Persistenz statt kostenpflichtiger API.
- Tweet-Erstellung und Medienfunktionen vorhanden.
- Risiko hoch: interne Endpunkte, Transaction IDs und Login-Flows koennen wechseln.

**Alternative: eigener Playwright-Webadapter** — Apache-2.0.

- Persistente X-Websession, Composer fuer Text/Bild/Video.
- Weniger Abhaengigkeit von GraphQL-Operation-IDs, dafuer UI-fragiler.

Gepruefte, aber verworfene Zusatzalternative: `Owen3H/twittxr` (MIT) ist cookie/Puppeteer-faehig, fokussiert aber Syndication/Lesen statt vollwertigem Publishing.

**Offizieller Fallback:** X API / `xurl`.

**T-0003:** `twikit` primaer, Playwright-Fallback.

## YouTube

**Primaer: offizielle YouTube Data API v3** — OAuth 2.0 und resumable upload.

- Stabiler, dokumentierter Upload für Video, Metadaten, Sichtbarkeit, Planung, Kommentare, Moderation, Thumbnails und Playlist-Operationen.
- OAuth-Token statt langlebiger Browser-Cookies; Kanal wird vor Live-Upload verifiziert.
- `YouTube/youtube_api.py` ist stdlib-only und bleibt damit auf macOS und Linux/OCI portabel.
- Standard `PRIVATE`; Live ist zusätzlich über `YOUTUBE_API_LIVE_APPROVED=true` fail-closed geschützt.

**Browser-Fallback:** `YouTube/youtube_community.py` bleibt ausschließlich für Funktionen, die die Data API nicht anbietet (insbesondere Community-Posts und bestimmte Studio-Aktionen). Sein Standard-Backend ist SIN-Browser-Use CLI 3.0 im SIN-Chrome-Bot; Playwright ist nur ein expliziter Legacy-Fallback. Er ist nicht der Upload- oder Kommentar-Primärpfad.

**T-0003:** API-Adapter als primärer YouTube-Publisher integrieren; OAuth-Client- und Token-Dateien nur über lokale Pfade konsumieren, nie Inhalte loggen. Keine automatische Google-Cloud-Projekt- oder Credential-Erstellung.


## Mastodon

**Primaer: `Mastodon.py`** — https://github.com/halcy/Mastodon.py — MIT.

**Alternative: `ihabunek/toot`** — https://github.com/ihabunek/toot — GPL-3.0.

Beide nutzen die offene, vorgesehene Mastodon-API mit User-Token und Medienupload. Browser-Imitation waere hier technisch schlechter. Anti-Bot-Risiko bei normaler, rate-limit-konformer Nutzung niedrig.

**T-0003:** optionaler Python-Adapter ueber Mastodon.py bzw. minimalen HTTP-Client.

## Bluesky

**Primaer: `MarshalX/atproto`** — https://github.com/MarshalX/atproto

- MIT, 2026 aktiv.
- Python SDK fuer das offene AT Protocol; Text/Bilder/Video.

**Alternative: `bluesky-social/atproto` / `@atproto/api`** — https://github.com/bluesky-social/atproto

- Referenzimplementierung, MIT oder Apache-2.0, sehr aktiv.
- Technisch stark, aber Node/TypeScript waere ein zusaetzlicher Runtime-Stack.

**T-0003:** Python `atproto`.

## Telegram

**Primaer: `LonamiWebs/Telethon`** — https://github.com/LonamiWebs/Telethon

- MIT; Releases bis 2026.
- MTProto User-/Bot-Session, Text/Bild/Video/Dateien.
- Session-Datei ist Secret und bleibt ausserhalb Git.

**Alternative: Telegram Bot API.** Stabiler und einfacher, wenn Bot-Identitaet im Zielkanal akzeptiert ist.

**T-0003:** optional Telethon; Bot API bevorzugen, wenn ein Bot ausreichend ist.

## Discord

**Primaer: Incoming Webhook via Python-stdlib HTTP.** Kein SDK noetig; Webhook-URL nur per Environment. Webhooks sind explizit fuer Automation gedacht und koennen Content/Embeds/Dateien senden.

**Alternative: `Rapptz/discord.py`** — https://github.com/Rapptz/discord.py — MIT, aktiv, mit Rate-Limit-Handling und Bot-/Webhook-Support.

**T-0003:** stdlib Webhook-Adapter; `discord.py` nur fuer spaetere Bot-/Interaktionsfunktionen.

## Foren

**Primaer fuer Discourse:** Discourse HTTP API — https://github.com/discourse/discourse — Server GPL-2.0-or-later. Die HTTP-API ist der robuste Weg fuer Topics/Posts/Uploads.

**Alternative fuer unbekannte Foren:** Playwright (Apache-2.0) mit persistenter Browser-Session. Stark forumspezifisch; Captcha, Moderation und ToS variieren.

**T-0003:** nur generisches Forum-Draft-Interface. Echte Implementierung erst nach Benennung eines konkreten Forums.

## Gemeinsame Regeln fuer T-0003

1. `DRY_RUN=true` als sicherer Default; echter Publish nur nach separater Freigabe.
2. Keine Credentials/Session-Inhalte in Git, YAML, Markdown oder Logs.
3. Cookie-/Session-Dateien nur ueber Pfade aus Environment.
4. Challenge/Captcha/2FA/Checkpoint => abbrechen statt automatisiert umgehen.
5. Kein unbegrenztes Retry; pro Account sequentiell und rate-limit-konform.
6. Draft-Validierung muss komplett offline testbar sein.
7. Browser-Code bleibt Chromium/Playwright-portabel fuer macOS ARM64 und Linux/OCI.
8. Offizielle APIs fuer TikTok/Instagram/Reddit/X/YouTube bleiben austauschbare Fallbacks.

## Gepruefte Quellen

- https://github.com/wkaisertexas/tiktok-uploader
- https://github.com/haziq-exe/TikTokAutoUploader
- https://github.com/subzeroid/instagrapi
- https://github.com/public-clis/rdt-cli
- https://github.com/d60/twikit
- https://github.com/Owen3H/twittxr
- https://github.com/adasq/youtube-studio
- https://github.com/porjo/youtubeuploader
- https://github.com/microsoft/playwright
- https://github.com/halcy/Mastodon.py
- https://github.com/ihabunek/toot
- https://github.com/MarshalX/atproto
- https://github.com/bluesky-social/atproto
- https://github.com/LonamiWebs/Telethon
- https://github.com/Rapptz/discord.py
- https://github.com/discourse/discourse

## Endentscheidung

T-0003 kann ohne weitere Architekturentscheidung beginnen: geschlossene Plattformen verwenden Session/private-client + Playwright-Fallback; offene Netze und Webhooks verwenden ihre nativen offenen Schnittstellen. Die Bridge bleibt standardmaessig Draft-only und benoetigt fuer diesen Research-Task keinerlei echte Plattform-Credentials.
