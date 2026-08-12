# Postiz-Integration

Postiz ist ein **optionaler** self-hosted Scheduling-/UI-Layer. Die kanonische Bridge
behält Payload-Validierung, Live-Gates, Secret-Authority und externe Verifikation.

## Betrieb

Der offizielle Compose-Stack enthält zusätzlich PostgreSQL, Redis und Temporal.
Wir pinnen keinen unvollständigen Eigenbau: verwende den offiziellen Stack und pinne
einen geprüften Commit vor dem produktiven Betrieb:

<https://github.com/gitroomhq/postiz-docker-compose>

`docker-compose.example.yml` ist nur ein sidecar-Vertragsbeispiel und startet
Postiz nicht allein. Secrets gehören in den bestehenden Secret-Workflow; niemals in
`.env`, Git oder Logs. `DRY_RUN` bleibt Standard.

## Grenzen

- Postiz darf keine Credentials parallel zur kanonischen Secret-Authority verwalten.
- Es darf keine ungeprüften Live-Aktionen auslösen.
- Bei Ausfall bleibt die direkte API-Bridge verfügbar.
- Browser-Automation ist kein stiller Fallback.
