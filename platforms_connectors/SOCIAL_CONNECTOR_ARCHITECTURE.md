# Social-Connector-Architektur

## Ziel

Alle Social-Connectoren verwenden einen gemeinsamen, fail-closed Vertrag. Buffer ist für verbundene Systemfehler-Kanäle der primäre Publishing-/Scheduling-Transport; direkte APIs bleiben offizielle Fallbacks.
YouTube und TikTok bleiben kompatibel; neue Plattformen werden schrittweise aktiviert.

## Plattformen

| Connector | Primärweg | UI-Fallback | Skill |
| Buffer Fleet | Buffer GraphQL/MCP mit account-scoped Infisical-Key | direkte Plattform-API | sin-buffer / Plattformskill |
|---|---|---|---|
| Facebook | Buffer (Account 2) | Meta Graph API / Pages | SIN-Facebook |
| Instagram | Buffer (Account 1) | Instagram Graph API | SIN-Instagram |
| X | Buffer (Account 3) | X API v2 + Media Upload | SIN-X |
| Reddit | OAuth API | keiner | SIN-Reddit |
| LinkedIn | Posts API | keiner | SIN-LinkedIn |
| Threads | Threads API | keiner | SIN-Threads |
| Pinterest | API v5 | keiner | SIN-Pinterest |
| Bluesky | AT Protocol | keiner | SIN-Bluesky |
| Mastodon | REST API | keiner | SIN-Mastodon |
| Telegram | Bot API | keiner | SIN-Telegram |
| Discord | Webhook/Bot API | keiner | SIN-Discord |

## Gemeinsame Gates

1. Payload validieren und Plattformregeln prüfen.
2. Standardmäßig Dry-Run ausführen.
3. Live nur mit explizitem `ALLOW_REAL_POSTS=1` und plattformspezifischer Freigabe.
4. Keine Secrets im Prozessoutput oder Repository.
5. External-ID und Antwort unabhängig verifizieren.
6. Idempotency-Key/Audit-Eintrag schreiben.
7. Fehler fail-closed melden; keine stillen Browser-Fallbacks.

## Postiz

Postiz wird optional als self-hosted Scheduling-/API-Layer betrieben (AGPL-3.0).
Die kanonischen Connectoren bleiben maßgeblich für Payload-Validierung, Secret-Authority,
Live-Gates und Verifikation. Postiz darf keine Credentials aus Infisical ersetzen oder
ungeprüfte Live-Aktionen auslösen. Deployment-Ziel ist Docker/OrbStack-kompatibel und
später OCI-portabel; Secrets werden ausschließlich über die bestehende Laufzeitumgebung
injiziert.

## Nächste Welle

Implementierung der offiziellen API-Adapter in Wellen: Instagram/X/Reddit/LinkedIn,
dann Threads/Pinterest/Bluesky/Mastodon, dann Telegram/Discord.

## Buffer registry

Account 1 (`6a7cdff6ba121c15135353f4`): Instagram, Threads, LinkedIn. Account 2
(`6a7ce320460832fbfcda7d98`): Facebook, Bluesky, Mastodon. Account 3
(`6a7ce8391c7f43f54a9c0b59`): Pinterest, X/Twitter, YouTube. YouTube uses
Buffer channel `6a7cf0c4b2d9d57743679762` for channel
`UCBWRl7VXRdy0kcsoV7or7Uw`.

## Scheduler contract

Buffer ist der Scheduler für die neun verbundenen Kanäle. `dueAt` wird als
ISO-8601-Wert in `buffer_targets[].due_at` weitergereicht. Postiz bleibt ein
optionaler Planungs-UI-Layer; sein offizieller Multi-Container-Stack ist lokal
nicht gestartet/verifiziert und darf Buffer nicht mit eigenen Credentials
überschreiben.
