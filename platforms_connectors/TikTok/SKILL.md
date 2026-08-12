---
name: sin-tiktok
description: >
  TikTok (Social) integration for the OpenSIN fleet: organic content
  publishing via TikTok Studio (tiktok.com), video upload workflow, comment
  and community management, account analytics and trend research. All browser
  work runs exclusively through SIN-Chrome (bot profile) with agentcookie
  sessions — no external browser, no Orca browser. There is no public
  content-publishing API for regular TikTok accounts; uploads happen in TikTok
  Studio UI. Fail-closed by default. Triggers: "SIN-TikTok", "TikTok upload",
  "TikTok Studio", "TikTok Videos", "TikTok Kommentare", "TikTok Social",
  "tiktok.com", "TikTok hochladen".
license: MIT
compatibility:
  - claude-code
  - codex
  - opencode
  - worker
  - jcode
  - cline
  - orca
metadata:
  author: OpenSIN-Code
  category: social-publishing
  lifecycle: bundled
  version: "1.0.0"
---

# SIN-TikTok

TikTok Social ist der organische Content-Kanal der OpenSIN-Fleet (ShopSIN
Storefront, https://shopsin.delqhi.com, TikTok-Shop-Kanal und kommende
TikTok-Ads-Kampagnen). Diese Skill deckt den Social-Lebenszyklus ab:
Content-Planung, Upload über TikTok Studio, Community-Management
(Kommentare), Performance-Auswertung und Trend-Recherche.

Browser-UI-Arbeit läuft standardmäßig über SIN-Browser-Use (Browser Use CLI
3.0) am isolierten SIN-Chrome-`bot`-Profil mit agentcookie-Session. SIN-Chrome
bleibt Profil-/Identity-Owner und typed Fallback. Orca-Browser ist für TikTok
kein Ziel; wenn Orca-Profile doch verwendet werden, gilt diese Skill nicht.

## Abgrenzung zu anderen TikTok-Skills

| Skill | Zuständigkeit |
|---|---|
| `sin-tiktok` (diese) | Organischer Content: tiktok.com, TikTok Studio, Kommentare, Analytics |
| `sin-tiktok-shop` | Marketplace: Partner Center, Shop-API, Produkte, Orders, Returns |
| `sin-tiktok-ads` | Werbung: Ads Manager (ads.tiktok.com), Kampagnen, Zielgruppen, Pixel |

Nicht verwenden für Produkt-/Shop-Themen (→ `sin-tiktok-shop`) oder
Werbung/Ads-Kampagnen (→ `sin-tiktok-ads`).

## Aktivierungsgrenze

Verwende diese Skill bei:

- „SIN-TikTok", „TikTok hochladen", „TikTok Upload", „TikTok Studio"
- Video-Publishing, Content-Plan, Hashtag-/Trend-Recherche
- Kommentar-Moderation, Community-Management auf tiktok.com
- Performance-Auswertung (Aufrufe, Likes, Shares) für organische Posts
- Browser-Fehlerdiagnose auf tiktok.com (Login, Studio, Upload)

## Architekturentscheidung

| Aufgabe | Primärer Weg | Fallback |
|---|---|---|
| Video-Upload | TikTok Studio UI (SIN-Browser-Use am SIN-Chrome-Bot) — keine öffentliche Upload-API für normale Accounts | manueller Upload |
| Login/Session | SIN-Chrome bot-Profil, agentcookie | Keychain `sin-chrome:bot:www.tiktok.com:*` |
| Kommentare | tiktok.com/Studio UI | — |
| Analytics | TikTok Studio → Analytics (UI) | — |
| Trend-Recherche | tiktok.com ForYou / Suche | Google Trends (extern) |

Die TikTok **Social**-API bietet keinen öffentlichen Content-Publishing-Zugang
für reguläre Nutzerkonten. Der ShopSIN-Backend-Flow (`/api/tiktok/*`) gehört
zur **Shop**-API (siehe `sin-tiktok-shop`) und ist hier nicht zuständig.

## Wichtige Credentials (wo sie liegen)

| Secret | Ort |
|---|---|
| `TIKTOK_PARTNER_EMAIL` (Account: `zukunftsorientierte.energie@gmail.com`) | Infisical + `~/.config/sin-infisical/credentials.env` |
| `TIKTOK_PARTNER_PASSWORD` | Infisical + `~/.config/sin-infisical/credentials.env` |
| Browser-Session | SIN-Chrome `bot`-Profil (agentcookie, persistent) |

Niemals Passwörter, Cookies oder Session-IDs in Git, Logs, Reports, Screenshots
oder Chat ausgeben. Werte nur über `sin-infisical`-CLI (`get.sh --mask`).

## Browser-Routing (SIN-Browser-Use als Standard)

- Browser: SIN-Browser-Use / Browser Use CLI 3.0 über SIN-Chrome `bot` (headed,
  persistent, agentcookie); `sin-chrome` bleibt Start-, Identity- und Fallback-Gate.
- Login: über SIN-Chrome Keychain/agentcookie; bei frischer Session manuell im
  sichtbaren Fenster oder `sin-chrome-control login`
- Aktionen: Browser-Use-CLI-Skripte mit stabilen `targetId`s; `sin-chrome-control`
  für Status, Identity-Gates und typed Fallback.
- Wichtige URLs:

| Ziel | URL |
|---|---|
| TikTok Start/ForYou | `https://www.tiktok.com` |
| Login (Email) | `https://www.tiktok.com/login/phone-or-email/email` |
| TikTok Studio | `https://www.tiktok.com/tiktokstudio` |
| Upload | `https://www.tiktok.com/upload` (leitet eingeloggte User auf Studio-Upload) |
| Profil | `https://www.tiktok.com/@systemfehler_nach_din` |
| Partner Center | `https://partner.tiktokshop.com` (Shop, nicht Social) |

## Bekannte Browser-Verhaltensweisen (CDP)

TikTok ist eine schwere SPA; die CDP-Verbindung von sin-chrome-control bricht
bei tiktok.com regelmäßig ab (Snapshots timeout). Bewährtes Muster:

1. `sin-chrome-control navigate <url> --tab <n>` → Antwort „ok" genügt; die
   URL wird über `sin-chrome-control status` des Tabs verifiziert (Snapshot
   auf TikTok-Seiten oft unnötig).
2. Bei Timeout/Verbindungsverlust: `sin-chrome start` (idempotent) → `status`
   → weiter.
3. Login-Check über Umleitung: `/upload` leitet eingeloggte User auf
   `tiktokstudio/upload` weiter, nicht eingeloggte auf `/login/*`.

## Video-Upload (TikTok Studio)

1. `sin-chrome start` → Tab auf `https://www.tiktok.com/tiktokstudio/upload`
2. Video hochladen (Datei-Dialog über `sin-chrome-control` UI-Aktionen oder
   manuell im sichtbaren Fenster)
3. Titel, Hashtags, Cover, Zielgruppe pflegen
4. Veröffentlichen oder als Entwurf speichern
5. Erst nach abgesprochener Content-Freigabe publizieren — keine
   automatisierten Fake-Countdowns oder künstliche Verknappung
   (AGENTS.md-Regel 11 gilt für alle Kanäle)

## Community & Analytics

- Kommentare: TikTok Studio → „Kommentare" (Moderation, Antworten)
- Analytics: TikTok Studio → „Analyse" (Aufrufe, Likes, Shares, Follower)
- Kennzahlen nur aus der UI übernehmen; keine erfundenen Conversion-Zahlen

## Fehlerdiagnose (bekannte Muster)

| Symptom | Ursache | Fix |
|---|---|---|
| CDP-Timeout bei Snapshot | schwere SPA | `sin-chrome start` → `status`, per `navigate`+`status` arbeiten |
| `/upload` zeigt Login-Seite | Session weg (Cookie-Laufzeit) | erneut einloggen (Keychain/Infisical), agentcookie-Sync prüfen |
| „Höchstanzahl an Versuchen erreicht" | TikTok-Login-Rate-Limit | Stunden warten, Login via Keychain nicht wiederholen |
| Studio lädt nicht | Ad-Blocker/Erweiterungen | bot-Profil ist isoliert — keine Erweiterungen hinzufügen |

## Abschluss-Checkliste

- [ ] Login auf tiktok.com funktioniert (bot-Profil)
- [ ] TikTok Studio erreichbar, Upload-Prozess verstanden
- [ ] Session-Status vor/nach Arbeit dokumentiert
- [ ] Keine Secrets in Git, Logs, Reports, Screenshots
