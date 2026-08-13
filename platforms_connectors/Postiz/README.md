# Postiz-Integration

Postiz ist **nicht aktiviert** und kein Scheduler des SYSTEMFEHLER_nach_DIN-Kanals. Buffer bleibt der verbindliche und einzige Publishing-/Scheduling-Layer. Die kanonische Bridge behält Payload-Validierung, Live-Gates, Secret-Authority und externe Verifikation.

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
- Postiz darf Buffer nicht ersetzen, spiegeln oder parallel schedulen.
- Direkte Plattform-APIs und Browser-Automation sind kein stiller Fallback.
