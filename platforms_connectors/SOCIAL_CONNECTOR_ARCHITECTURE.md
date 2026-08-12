# Social-Connector-Architektur

## Ziel

Alle Social-Connectoren verwenden einen gemeinsamen, API-first und fail-closed Vertrag.
YouTube und TikTok bleiben kompatibel; neue Plattformen werden schrittweise aktiviert.

## Plattformen

| Connector | Primärweg | UI-Fallback | Skill |
|---|---|---|---|
| Facebook | Meta Graph API / Pages | keiner standardmäßig | SIN-Facebook |
| Instagram | Instagram Graph API | nur dokumentierte UI-Lücken | SIN-Instagram |
| X | X API v2 + Media Upload | keiner standardmäßig | SIN-X |
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
