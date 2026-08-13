# Social-Connector-Architektur

## Ziel

Alle Social-Connectoren verwenden einen gemeinsamen, fail-closed Vertrag. Buffer ist für verbundene Systemfehler-Kanäle der verbindliche und einzige Publishing-/Scheduling-Transport. Direkte Plattform-APIs werden nicht als parallele Fallback-Publishingwege betrieben.
YouTube ist über Buffer verbunden. TikTok bleibt bewusst ein separater Studio-Adapter; weitere Plattformen werden nicht automatisch aktiviert.

## Plattformen

| Connector | Verbindlicher Weg | Status |
|---|---|---|
| Instagram | Buffer Account 1 | verbunden |
| Threads | Buffer Account 1 | verbunden |
| LinkedIn | Buffer Account 1 | verbunden |
| Facebook | Buffer Account 2 | verbunden |
| Bluesky | Buffer Account 2 | verbunden |
| Mastodon | Buffer Account 2 | verbunden |
| Pinterest | Buffer Account 3 | verbunden |
| X | Buffer Account 3 | verbunden |
| YouTube | Buffer Account 3 | verbunden |
| TikTok | SIN-TikTok-Studio-Adapter außerhalb Buffer | separat, kein Buffer-Kanal |
| Reddit/Telegram/Discord/Foren | kein aktiver Publishingpfad | nicht verbunden |


## Gemeinsame Gates

1. Payload validieren und Plattformregeln prüfen.
2. Standardmäßig Dry-Run ausführen.
3. Live nur mit explizitem `ALLOW_REAL_POSTS=1` und plattformspezifischer Freigabe.
4. Keine Secrets im Prozessoutput oder Repository.
5. External-ID und Antwort unabhängig verifizieren.
6. Idempotency-Key/Audit-Eintrag schreiben.
7. Fehler fail-closed melden; keine stillen Browser-Fallbacks.

## Postiz

Postiz wird nicht als Scheduler betrieben. Es bleibt ausschließlich als historische/optionale Integrationsnotiz dokumentiert und darf Buffer weder ersetzen noch parallel schedulen.
Die kanonischen Connectoren bleiben maßgeblich für Payload-Validierung, Secret-Authority,
Live-Gates und Verifikation. Postiz darf keine Credentials aus Infisical ersetzen oder
ungeprüfte Live-Aktionen auslösen. Deployment-Ziel ist Docker/OrbStack-kompatibel und
später OCI-portabel; Secrets werden ausschließlich über die bestehende Laufzeitumgebung
injiziert.

## Aktueller Stand

Die Buffer-Flotte ist implementiert. Offen sind ausschließlich Staging, Kestra-Lifecycle, OCI-Runtime, E2E-Dry-Run und Readiness-Audit; keine neue Plattform-Adapterwelle.

## Buffer registry

Account 1 (`6a7cdff6ba121c15135353f4`): Instagram, Threads, LinkedIn. Account 2
(`6a7ce320460832fbfcda7d98`): Facebook, Bluesky, Mastodon. Account 3
(`6a7ce8391c7f43f54a9c0b59`): Pinterest, X/Twitter, YouTube. YouTube uses
Buffer channel `6a7cf0c4b2d9d57743679762` for channel
`UCBWRl7VXRdy0kcsoV7or7Uw`.

## Scheduler contract

Buffer ist der Scheduler für die neun verbundenen Kanäle. `dueAt` wird als
ISO-8601-Wert in `buffer_targets[].due_at` weitergereicht. Postiz ist nicht aktiviert und darf Buffer weder ersetzen noch parallel schedulen.
