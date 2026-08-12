# Externe Blocker (Stand 2026-08-12)

Die Code- und Dry-Run-Integration ist abgeschlossen. Folgende Schritte benötigen
Autorisierung/Accounts ausserhalb des Repositories und wurden absichtlich nicht
automatisch ausgeführt:

- Meta: Instagram Professional-/Facebook-Page-/Threads-App, OAuth-Berechtigungen und gültige Page-/User-Tokens.
- X: Developer-Projekt, aktivierte Schreibberechtigung und User-Context-Token.
- Reddit: registrierte OAuth-App, Subreddit-Berechtigung und User-Agent-Freigabe.
- LinkedIn: App-Produktfreigabe (`w_member_social`/`w_organization_social`) und Author-URN.
- Pinterest: App/OAuth-Freigabe und Board-ID.
- Bluesky, Mastodon, Telegram, Discord: zielkontospezifische App-Passwörter, Tokens oder Webhook-URLs.
- Postiz: geprüfter offizieller Docker-Compose-Stack, persistente Datenbank/Redis/Temporal-Volumes und Runtime-Secrets.

Bis diese externen Voraussetzungen autorisiert und über den bestehenden Secret-Workflow
injiziert sind, bleiben alle Live-Gates geschlossen. Es wurden keine Posts versendet,
keine Credentials erzeugt oder geändert und keine CAPTCHA-/2FA-/Plattform-Schutzmechanismen
umgangen.
