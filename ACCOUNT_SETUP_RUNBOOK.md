# Social-Platform Account Setup Runbook

Stand: 2026-08-12. Dieses Dokument enthält verifizierte UI-/Account-Erkenntnisse aus
SIN-Chrome `bot`. Es enthält keine Tokens, Passwörter, Cookies oder OAuth-Codes.

## Wiederverwendbare Signup-Skills

Für jeden weiteren oder neu anzulegenden Account zuerst den zentralen Skill
`sin-social-account-setup` und anschließend `sin-<plattform>-signup` verwenden.
Die Plattform-Wrapper existieren für Instagram, Facebook, X, Reddit, LinkedIn,
Threads, Pinterest, Bluesky, Mastodon, Telegram, Discord, YouTube, TikTok und
Postiz. Übersicht und verbindlicher Datenfluss: `ACCOUNT_SIGNUP_SKILLS.md`.
Publishing-Skills (`sin-<plattform>`) und Signup-Skills sind getrennt.

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

### Meta/Facebook/Instagram (verifiziert 2026-08-12)

- Meta-App **OpenSIN** im Business-Portfolio **Minime**: App-ID `996299283432639`, Business-ID `1786125979186446`.
- Use Case **Instagram API** ist aktiviert; Instagram-App `OpenSIN-IG`, Instagram-App-ID `1603001711211651`.
- Die erforderlichen Instagram-Berechtigungen wurden in der App-Konfiguration angelegt: `instagram_business_basic`, `instagram_business_manage_comments`, `instagram_business_manage_messages`. Für Live-Zugriff ist weiterhin App Review erforderlich.
- Instagram-Konto `@systemfehler_nach_din` wurde dem Business-Portfolio hinzugefügt. Sichtbar verifizierte Konto-ID: `17841440701410225`; Eigentümer: Minime.
- Use Case **Seiten verwalten (Pages API)** wurde in OpenSIN aktiviert.
- Das im Facebook-Konto verwaltete Profil **ZoE GmbH** (Seiten-ID `100085541960065`) wurde laut Nutzer am 2026-08-12 gelöscht. Der zuvor verwendete Facebook-Link liefert nun „Entweder funktioniert der von dir angeklickte Link nicht oder die Seite wurde entfernt“; dies ist als Löschbestätigung dokumentiert, nicht als neuer Login-Blocker.
- Das professionelle Facebook-Profil **Systemfehler Nach Din** ist sichtbar verifiziert unter `https://www.facebook.com/Systemfehler.nach.DIN/`; sichtbare Profil-ID `100085502655496`, Kategorie/Status: Professional Mode / Digital Creator.
- Der Business-Suite-Dialog „Vorhandene Facebook-Seite hinzufügen“ findet die Professional-Mode-Profil-ID `100085502655496` nicht („Keine Facebook-Seiten gefunden“). Daraus folgt: Meta behandelt dieses Profil in diesem Dialog nicht als Facebook-Seite. Es darf nicht als Seite-ID eingetragen oder durch eine falsche ZoE-ID ersetzt werden.
- Instagram-Tester-/Token-Flow öffnet den offiziellen Instagram-Login. Kein Token, OAuth-Code oder Passwort wurde ausgelesen.

### Meta Violations-&-Appeals-Prüfung (2026-08-12)

- Der vom Nutzer genannte Pfad `https://developers.facebook.com/apps/2283580245716951/violations_and_appeals/` wurde im authentifizierten SIN-Chrome geöffnet. Meta zeigt „Seite nicht gefunden“ und fordert zur Suche nach der App-ID auf. Die App ist im aktuellen App-Inventar nicht vorhanden; dort ist nur OpenSIN (`996299283432639`) sichtbar.
- `https://developers.facebook.com/required-actions/` wurde anschließend geöffnet und zeigt aktuell **„Aktuell gibt es keine erforderlichen Maßnahmen.“**
- Ergebnis: Keine zugängliche Violation/Appeal-Aufgabe für OpenSIN und kein bearbeitbarer Appeal für App-ID `2283580245716951` gefunden. Die genannte ID und dieser Prüfstatus wurden als nicht-geheime Metadaten in Infisical gespeichert.

### Infisical-Metadaten

Folgende nicht-geheime IDs/Bezeichner wurden über den bestehenden `sin-infisical`-Workflow in `My-OpenSIN-Secrets` / `dev` gespeichert: `META_APP_ID`, `META_APP_NAME`, `META_BUSINESS_ID`, `META_BUSINESS_PORTFOLIO_ID`, `META_BUSINESS_PORTFOLIO_NAME`, `INSTAGRAM_API_APP_ID`, `INSTAGRAM_ACCOUNT_USERNAME`, `INSTAGRAM_BUSINESS_ACCOUNT_ID`, `INSTAGRAM_USER_ID`, `FACEBOOK_PAGE_ID`, `FACEBOOK_PAGE_NAME`. Token-Schlüssel werden erst nach autorisiertem OAuth-Lauf injiziert; ihre Werte erscheinen weder im Chat noch in diesem Repository.

### Nutzerentscheidung für die nächste Meta-Welle (2026-08-12)

- Der Nutzer verlangt, dass jeder neue Account-Setup-Schritt, jede sichtbare ID, jede UI-Abweichung, jeder externe Blocker und jeder Recovery-Schritt sofort in diesem Runbook und `EXTERNAL-BLOCKERS.md` festgehalten wird, damit spätere Accounts ohne erneute Discovery eingerichtet werden können.
- Der Nutzer autorisiert die Entfernung/Löschung der **konkreten alten ZoE-GmbH-Facebook-Seite**, nicht eines persönlichen Facebook-Profils. Vor jeder destruktiven Aktion muss die Zielseite anhand Name und sichtbarer URL/ID nochmals eindeutig bestätigt werden.
- Ziel für Meta Business Suite ist das professionelle Facebook-Profil bzw. die Facebook-Präsenz `Systemfehler.nach.DIN`; Meta kann professionelle Profile technisch anders behandeln als Facebook-Seiten. Es darf keine persönliche Identität oder ein falsches Business-Asset gelöscht werden.

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

## Recovery checkpoint: aktuelle Meta-Welle

1. **ZoE GmbH löschen:** Im SIN-Chrome-Tab `https://www.facebook.com/deactivate_delete_account/` ist für die verifizierte Seite `ZoE GmbH` (ID `100085541960065`) bereits „Seite löschen“ ausgewählt. Meta zeigt die finale Seite „Bestätige, dass dies deine Seite ist“ und wartet auf das Seitenpasswort. Nach manueller Eingabe durch den Kontoinhaber: `Weiter` bestätigen und anschließend live prüfen, dass die ZoE-Seite nicht mehr erreichbar ist und nicht mehr im Business-Portfolio auftaucht.
2. **SYSTEMFEHLER Professional Mode:** Profil-ID `100085502655496` und URL `https://www.facebook.com/Systemfehler.nach.DIN/` sind die kanonischen Werte. Der „Vorhandene Facebook-Seite hinzufügen“-Dialog findet sie nicht; nicht wiederholt suchen und niemals ZoE-ID als Ersatz verwenden. Professional Mode bleibt über das Facebook Professional Dashboard verwaltbar, ist aber kein Pages-API-Asset im Business-Portfolio.
3. **Instagram-Tester:** In OpenSIN → Instagram API → API-Einrichtung mit Instagram-Login → `Konto hinzufügen` → `Weiter` fortsetzen. Der offizielle Instagram-Login öffnet einen Login-Tab. Die bestehende Instagram-Session `systemfehler_nach_din` ist sichtbar, aber der OAuth-Aufruf endet aktuell fail-closed mit `Entwickler-Rolle nicht ausreichend`. Der Login-/Tester-Flow benötigt daher noch eine gültige Instagram-Tester-/App-Rollen-Zuordnung; kein Passwort, Code oder Token wurde eingegeben/ausgelesen. Danach Konto `systemfehler_nach_din` und ID `17841440701410225` prüfen. Access Token nicht anzeigen/loggen; ausschließlich als `INSTAGRAM_ACCESS_TOKEN` über `sin-infisical` schreiben.
4. **App Review:** Für Live-Zugriff die bereits konfigurierten Berechtigungen in OpenSIN einzeln mit Use-Case, Datenschutz-/Lösch-URL, Screenshots und Testanleitung einreichen. Erst nach Meta-Genehmigung und Identitätscheck Live-Gates öffnen.

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
