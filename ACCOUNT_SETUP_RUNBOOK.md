# Social-Platform Account Setup Runbook

Stand: 2026-08-12. Dieses Dokument enthält verifizierte UI-/Account-Erkenntnisse aus
SIN-Chrome `bot`. Es enthält keine Tokens, Passwörter, Cookies oder OAuth-Codes.

## Sicherheitsregeln

- Browser Use verwendet ausschließlich das authentifizierte SIN-Chrome-`bot`-Profil.
- Keine Cookie-/Token-/Passwort-Extraktion; 2FA, CAPTCHA und Challenge-Flows werden nicht umgangen.
- Geheimnisse werden nach manueller/autorisierten OAuth-Erstellung ausschließlich über `sin-infisical` injiziert.
- Live-Gates bleiben bis zur Verifikation pro Plattform geschlossen.
- Für jede neue Plattform zuerst den Login-/Account-Status in einem neuen Agent-Tab prüfen; bestehende Operator-Tabs nicht schließen.

## Verifiziert eingerichtet

### Browser-Login-Fakten

- Facebook-Hauptseite war im SIN-Chrome-`bot`-Profil bereits authentifiziert; ein direkter Aufruf von `facebook.com/login` landete auf `facebook.com/home.php`.
- X war im Profil als `@schu68231` authentifiziert; `console.x.com/onboarding` ist erreichbar.
- Google Cloud war als `zukunftsorientierte.energie@gmail.com` authentifiziert.
- Diese Fakten wurden nur über sichtbare Seiten/URLs verifiziert; Passwörter und gespeicherte Secrets wurden nicht ausgelesen.

### Instagram

- Account: `systemfehler_nach_din` / Anzeigename `Systemfehler_nach_DIN`.
- Am 2026-08-12 erfolgreich von persönlichem Konto auf **Creator/Professional** umgestellt.
- Kategorie: **Kunst**.
- Nach der Umstellung zeigt das Profil Insights-/Werbeverwaltungs-Hinweis und `KI-Creator`.
- Die Meta-Umstellung stellt das Profil öffentlich; das war eine von Instagram verlangte Bestätigung.
- Nächster API-Schritt: Meta for Developers anmelden, App mit Instagram/Threads-Anwendungsfall erstellen, Instagram Login/API-Produkte und Berechtigungen beantragen.
- Meta for Developers leitet beim erstmaligen `Los geht’s` auf einen Registrierungsdialog um und verlangt eine Mobilnummer zur Kontobestätigung oder alternativ eine Kreditkarte. Dieser externe Verifizierungsschritt wurde nicht automatisiert.

Direkte Seiten:

- `https://www.instagram.com/accounts/account_type_and_tools/`
- `https://developers.facebook.com/apps/`
- `https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-instagram-login`

## Status und nächster Schritt je Plattform

| Plattform | Browser-Status | Nächster autorisierter Schritt | Blocker |
|---|---|---|---|
| Instagram | Creator-Konto eingerichtet; Facebook-Hauptlogin vorhanden | Meta-Developer-App/OAuth | Meta-Developer-Verifizierung per Mobilnummer/Kreditkarte fehlt |
| Facebook | Hauptseite authentifiziert; Developer-Registrierung offen | Page/App/OAuth einrichten | Meta-Developer-Verifizierung per Mobilnummer/Kreditkarte fehlt |
| Threads | Kein Developer-Zugriff geprüft | Meta-App mit Threads-Produkt | Meta-Login fehlt |
| X | `@schu68231` authentifiziert; Developer-Onboarding erreichbar | Developer-Projekt und User OAuth | Developer Agreement/Policy muss bestätigt werden; Schreibzugang kann kostenpflichtig sein |
| Reddit | `/prefs/apps` mit Network-Security-Block | OAuth-App anlegen | Reddit-Netzwerkblock/Login |
| LinkedIn | Developer-Portal fordert Login | App und `w_member_social`/`w_organization_social` | LinkedIn-Login fehlt |
| Pinterest | `account-setup` zeigt „Anmelden/Registrieren“ | Developer-Konto/App/OAuth | Pinterest-Login fehlt |
| Bluesky | Öffentlicher Feed sichtbar, kein eingeloggtes Profil bestätigt | Account/App-Passwort | Login/Account fehlt |
| Mastodon | `mastodon.social/auth/sign_in` | App registrieren/Token | Mastodon-Login fehlt |
| Telegram | `my.telegram.org/auth?to=apps` | API-ID/API-Hash erzeugen | Telegram-Login/Telefonbestätigung fehlt |
| Discord | Developer Portal zeigt „Create Account / Log In“ | Application/Webhook/Bot | Discord-Login fehlt |
| YouTube | Google Cloud-Projekt `Hermes Private`; YouTube Data API v3 **bereits aktiviert** | OAuth-Branding/Client/Consent und lokaler OAuth-Lauf | OAuth-Client fehlt; Secret darf nicht aus Browser extrahiert werden |
| Postiz | `localhost:4007` nicht erreichbar | Offiziellen Compose-Stack deployen | Stack läuft nicht; Runtime-Secrets/Volumes fehlen |

## Wiederholbarer OAuth-/Secret-Workflow

1. Plattform-App nur im offiziellen Developer-Portal anlegen.
2. Redirect-URI exakt nach Connector-Dokumentation eintragen; keine URL raten.
3. OAuth nur im autorisierten SIN-Chrome-Profil abschließen; 2FA/CAPTCHA manuell an den Operator.
4. Nach Rückkehr zur Anwendung keine Codes/Tokens in Chat, Dateien oder Logs schreiben.
5. Werte über `sin-infisical` in die kanonischen Namen schreiben, z. B. `INSTAGRAM_ACCESS_TOKEN`.
6. Den echten Connector zuerst mit Dry-Run und anschließend mit einem nicht-publizierenden Account-/Identity-Check testen.
7. Erst danach die plattformspezifische `*_API_LIVE_APPROVED=true`-Freigabe außerhalb des Repositories setzen.

## Häufige Probleme und Lösungen

- **Meta leitet zu `business.facebook.com/business/loginpage` um:** Facebook-Login im Bot-Profil fehlt; nicht mit Instagram-Cookies oder Session-IDs umgehen.
- **Reddit „blocked by network security“:** nicht wiederholt automatisieren; später über freigegebenes Netzwerk/Account-Login fortsetzen.
- **Pinterest „Anmelden/Registrieren“:** zuerst Pinterest-Hauptkonto registrieren/anmelden, danach Developer-Account aktivieren.
- **Google Cloud „keine OAuth-Clients“:** YouTube API kann bereits aktiviert sein, trotzdem muss Branding/Zielgruppe/Client separat konfiguriert werden. Client-Secret nicht per Browser auslesen.
- **Postiz localhost-Fehler:** Postiz ist noch nicht gestartet; den geprüften offiziellen `gitroomhq/postiz-docker-compose`-Stack verwenden, nicht den sidecar-Vertrag allein.
- **Unbekannte oder dynamische UI:** DOM-Text/URL verifizieren, nicht blind nach Tab-Index klicken.
