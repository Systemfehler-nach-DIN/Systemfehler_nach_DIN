# Externe Blocker (Stand 2026-08-12)

Die Code-, Dry-Run- und Browser-Vorbereitung ist abgeschlossen. Der Instagram-Account
`systemfehler_nach_din` wurde im SIN-Chrome-`bot` erfolgreich in ein öffentliches
Creator-/Professional-Konto der Kategorie `Kunst` umgestellt.

Für echte OAuth-/Live-Konfiguration fehlen noch externe Account-Anmeldungen oder
Freigaben:

- Meta/Facebook: OpenSIN ist im Business-Portfolio Minime angelegt; Instagram API und Pages API sind konfiguriert und das professionelle Instagram-Konto ist verknüpft. Offen bleiben der offizielle Instagram-Tester-/OAuth-Lauf (Bot-Profil öffnet aktuell den Login-Dialog), die App-Review für erweiterte Berechtigungen und die Portfolio-Verknüpfung der Facebook-Seite ZoE GmbH. Kein Token wurde extrahiert.
- X: Account `@schu68231` ist im Bot-Profil angemeldet und das Developer-Onboarding ist erreichbar; das Absenden verlangt jedoch die Annahme des Developer Agreement/Policy und kann kostenpflichtigen Schreibzugang voraussetzen.
- Reddit: `/prefs/apps` war durch Network Security blockiert.
- LinkedIn, Pinterest, Mastodon, Telegram und Discord: jeweilige Developer-Portale fordern eine nicht vorhandene Anmeldung.
- Bluesky: Im Bot-Profil war nur der öffentliche Feed sichtbar; Account/App-Passwort nicht bestätigt.
- YouTube: Google Cloud-Projekt `Hermes Private` und YouTube Data API v3 sind vorhanden/aktiviert; ein OAuth-Client ist noch nicht eingerichtet. Secret-Download aus dem Browser wurde nicht vorgenommen.
- Postiz: lokaler Endpoint `localhost:4007` ist nicht erreichbar; offizieller Compose-Stack und Runtime-Secrets fehlen.

Bis die Konten, App-Freigaben und Tokens autorisiert und über Infisical injiziert sind,
bleiben alle Live-Gates geschlossen. Es wurden keine Plattform-Tokens, Cookies oder
Passwörter extrahiert, keine Credentials geändert und keine Posts versendet.
Siehe `ACCOUNT_SETUP_RUNBOOK.md` für die verifizierten URLs, Reihenfolge und Recovery-Hinweise.

- Die alte ZoE-GmbH-Facebook-Seite (ID `100085541960065`) wurde laut Nutzer gelöscht; der frühere Link zeigt nun den Meta-Hinweis, dass der Link nicht funktioniert oder die Seite entfernt wurde. Das professionelle Profil `Systemfehler.nach.DIN` (ID `100085502655496`) wird im Business-Suite-Dialog „Vorhandene Facebook-Seite hinzufügen“ nicht gefunden, weil Meta es dort nicht als Facebook-Seite behandelt.

- Meta App-ID `2283580245716951`: Der direkte `violations_and_appeals`-Link liefert „Seite nicht gefunden“; im App-Inventar ist nur OpenSIN sichtbar und `required-actions` meldet aktuell keine erforderlichen Maßnahmen. Es gibt deshalb derzeit keinen zugänglichen Appeal-Workflow für diese ID.

- Instagram OAuth-Testflow: Die sichtbare Session `systemfehler_nach_din` erreicht den offiziellen OAuth-Endpunkt, wird aber mit `Entwickler-Rolle nicht ausreichend` abgewiesen. Eine gültige Instagram-Tester-/App-Rollen-Zuordnung fehlt noch; keine Credentials oder OAuth-Codes wurden verarbeitet.

- Instagram-Tester-Zuordnung: OpenSIN → App-Rollen → Instagram-Tester → OpenSIN → `systemfehler_nach_din` wurde versucht; Meta blockiert mit „A Facebook Developer Account is required to be added to an app. Test users can't be added.“ OAuth endet zusätzlich mit „Entwickler-Rolle nicht ausreichend“.

- Meta Developer-Registrierung: Offizielle Dokumentation und `/async/registration` geprüft. OpenSIN-Dashboard-/App-Erstellungszugriff ist vorhanden; der Endpunkt leitet zurück ins Developer Center. Eine neue App wurde nicht erstellt. Der verbleibende Blocker ist die Instagram-Tester-Rollenpolicy, nicht der allgemeine Dashboard-Zugriff.

- Meta-Unternehmensverifizierung: Minime (`1786125979186446`) wurde für den Use Case „App verlangt Zugriff auf Berechtigungen für Meta for Developers“ eingereicht und steht auf **Wird überprüft**. Meta nennt normalerweise etwa 2 Werktage. Der Identitätsnachweis wurde durch den Kontoinhaber eingereicht; bis zur Entscheidung bleiben Instagram-Tester/OAuth und erweiterte Berechtigungen blockiert. Screenshot vom 12.08.2026, 22:50 liegt unter `/var/folders/4k/w1vg2tbj7718gc0mj308m95m0000gn/T/TemporaryItems/NSIRD_screencaptureui_mLYIkB/Bildschirmfoto 2026-08-12 um 22.50.16.png`.

- YouTube-OAuth: Desktop-Client in `Hermes Private` erstellt und OAuth technisch erfolgreich, aber Google/API liefert den falschen Kanal `ZOE Solar` (`UC8jo_fyVGSPKvRuS2ZWAvyA`). Ziel ist `Systemfehler_nach_DIN` (`UCBWRl7VXRdy0kcsoV7or7Uw`). Kein Upload; der lokale Token wird nicht verwendet. Erneute Autorisierung im korrekten Brand-/Google-Account erforderlich.
