# Externe Blocker (Stand 2026-08-12)

Die Code-, Dry-Run- und Browser-Vorbereitung ist abgeschlossen. Der Instagram-Account
`systemfehler_nach_din` wurde im SIN-Chrome-`bot` erfolgreich in ein öffentliches
Creator-/Professional-Konto der Kategorie `Kunst` umgestellt.

Für echte OAuth-/Live-Konfiguration fehlen noch externe Account-Anmeldungen oder
Freigaben:

- Meta/Facebook: Meta-Developer-Login fehlt; dadurch sind Instagram-Graph-, Facebook-Page- und Threads-App/OAuth-Einrichtung blockiert.
- X: Developer-Portal leitet auf X-Login um; Developer-Schreibzugang kann kostenpflichtig sein.
- Reddit: `/prefs/apps` war durch Network Security blockiert.
- LinkedIn, Pinterest, Mastodon, Telegram und Discord: jeweilige Developer-Portale fordern eine nicht vorhandene Anmeldung.
- Bluesky: Im Bot-Profil war nur der öffentliche Feed sichtbar; Account/App-Passwort nicht bestätigt.
- YouTube: Google Cloud-Projekt `Hermes Private` und YouTube Data API v3 sind vorhanden/aktiviert; ein OAuth-Client ist noch nicht eingerichtet. Secret-Download aus dem Browser wurde nicht vorgenommen.
- Postiz: lokaler Endpoint `localhost:4007` ist nicht erreichbar; offizieller Compose-Stack und Runtime-Secrets fehlen.

Bis die Konten, App-Freigaben und Tokens autorisiert und über Infisical injiziert sind,
bleiben alle Live-Gates geschlossen. Es wurden keine Plattform-Tokens, Cookies oder
Passwörter extrahiert, keine Credentials geändert und keine Posts versendet.
Siehe `ACCOUNT_SETUP_RUNBOOK.md` für die verifizierten URLs, Reihenfolge und Recovery-Hinweise.
