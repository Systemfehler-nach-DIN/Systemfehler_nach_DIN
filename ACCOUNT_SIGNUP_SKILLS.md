# Social-Account-Signup-Skills

Stand: 2026-08-12

## Zweck

Neue Plattform-Accounts sollen nicht erneut durch unstrukturierte Browser-Discovery eingerichtet werden. Die kanonischen Signup-Skills liegen im `wow-my-zsh`-Repository unter `shared/skills/`:

- Zentraler Vertrag: `sin-social-account-setup`
- Plattform-Wrapper: `sin-<plattform>-signup` für Instagram, Facebook, X, Reddit, LinkedIn, Threads, Pinterest, Bluesky, Mastodon, Telegram, Discord, YouTube, TikTok und Postiz
- Connector-Skills bleiben für Publishing zuständig (`sin-<plattform>`); Signup und Publishing sind absichtlich getrennt.

## Verbindlicher Datenfluss

1. Signup-Skill laden und dieses Runbook sowie `EXTERNAL-BLOCKERS.md` öffnen.
2. Offizielles Portal im SIN-Chrome-`bot`-Profil prüfen.
3. Account, externe ID, Owner, App, Permissions, Review-Status und Recovery erfassen.
4. Nicht-geheime Werte/Schlüssel-Namen über Infisical dokumentieren; Secret-Werte nie in Chat, Repo oder Logs.
5. `setup-manifest.jsonl`-Eintrag aktualisieren.
6. Identity-Check und DRY_RUN durchführen.
7. Live-Gates erst nach externer Freigabe und expliziter Autorisierung öffnen.

## Meta-Fortsetzung

- ZoE GmbH ist gelöscht.
- `Systemfehler Nach Din` Professional Mode ist kein Pages-API-Asset und wird im Business-Suite-Dialog nicht als Seite gefunden.
- OpenSIN ist im App-Inventar vorhanden.
- App-ID `2283580245716951` liefert beim direkten Violations-/Appeals-Link „Seite nicht gefunden“; `required-actions` meldet keine offenen Maßnahmen.
- Instagram-Tester-OAuth stoppt aktuell mit `Entwickler-Rolle nicht ausreichend`; keine Credentials wurden verarbeitet.

Jede neue Erkenntnis wird direkt hier, im Haupt-Runbook und in der Blocker-Datei ergänzt.
