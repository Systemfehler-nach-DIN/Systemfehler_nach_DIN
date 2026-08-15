# Infisical – Systemfehler_nach_DIN

Das Repository ist fest an das eigene Infisical-Projekt gebunden. Secret-Werte werden niemals in Git gespeichert.

- Projekt: `Systemfehler_nach_DIN`
- Projekt-ID: `c5bc692a-11ee-4949-ae40-c01f5d80034b`
- Standardumgebung: `dev`
- Repo-Bindung: `/.infisical.json`
- Authentifizierung für Agenten: SIN-Infisical Machine Identity / Agent-Sink
- Runtime-Injection: `website/kestra/run-with-infisical.sh` via `exec-with-secret.py`

## Verifizierte Runtime-Secrets

Vorhanden und names-only verifiziert sind insbesondere:

- `BUFFER_API_KEY_ACCOUNT_1`
- `BUFFER_API_KEY_ACCOUNT_2`
- `BUFFER_API_KEY_ACCOUNT_3`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_MEDIA_BUCKET`
- `KESTRA_ADMIN_USERNAME`
- `KESTRA_ADMIN_PASSWORD`
- `KESTRA_DB_PASSWORD`
- `SYSTEMFEHLER_PUBLISH_WEBHOOK_KEY`
- `SYSTEMFEHLER_PUBLISH_WEBHOOK_KEY_BASE64`
- TikTok Partner-Credentials
- YouTube OAuth Client-Credentials und Status-Metadaten
- relevante Buffer-, Meta-, Instagram-, Supabase- und Systemfehler-Metadaten

Insgesamt wurden 80 projektbezogene Secrets/Metadaten aus dem bisherigen zentralen Vault in das Projekt migriert. Der Import wurde ausschließlich über einen temporären `0600`-Dateipfad durchgeführt; die Datei wurde direkt danach gelöscht.

## Bewusst nicht vorhanden

Direkte Plattform-Tokens wie `X_ACCESS_TOKEN`, `REDDIT_ACCESS_TOKEN`, `LINKEDIN_ACCESS_TOKEN`, `PINTEREST_ACCESS_TOKEN` oder `DISCORD_WEBHOOK_URL` existierten auch im bisherigen Vault nicht. Sie sind für den kanonischen Buffer-first-Publishing-Pfad nicht erforderlich. Werden sie später über offizielle OAuth-/Developer-Flows beschafft, gehören sie in dieses Projekt.

`BUFFER_BOARD_SERVICE_ID`/Pinterest-Board-Metadaten und eine aktive TeraBox-Session bleiben externe Laufzeit-Gates und dürfen nicht durch Platzhalter oder erfundene Werte ersetzt werden.
