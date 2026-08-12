# TikTok (Social) Connector

Production connector for the organic TikTok channel of the OpenSIN fleet
(ShopSIN, https://shopsin.delqhi.com). Wires TikTok Social into the fleet:
browser access via SIN-Browser-Use CLI 3.0 through SIN-Chrome, content publishing via TikTok Studio, comment
management and analytics. The TikTok Shop marketplace flows live in the
`tiktok-shop` connector; ads in `tiktok-ads`.

## Scope

| Area | Mechanism |
|---|---|
| Content-Upload / TikTok Studio | SIN-Browser-Use CLI 3.0 via SIN-Chrome bot profile (no public upload API for regular accounts) |
| Login/Session | SIN-Chrome bot profile (agentcookie) + Infisical credentials |
| Community (Kommentare) | TikTok Studio UI |
| Analytics | TikTok Studio UI |
| Trend-Recherche | tiktok.com ForYou/Suche |

## Credential layout

| Secret | Storage | Used by |
|---|---|---|
| `TIKTOK_PARTNER_EMAIL` (zukunftsorientierte.energie@gmail.com) | Infisical + `~/.config/sin-infisical/credentials.env` | Browser login (tiktok.com / Studio) |
| `TIKTOK_PARTNER_PASSWORD` | Infisical + `~/.config/sin-infisical/credentials.env` | Browser login (tiktok.com / Studio) |
| Browser session | SIN-Chrome `bot` profile (agentcookie) | All UI work |

Never commit passwords, cookies, or session IDs. Browser sessions live only in
the SIN-Chrome `bot` profile.

## Verify

```bash
sin-chrome start
sin-chrome-control status
# Erwartet: bot-Profil aktiv; TikTok-Tab vorhanden

# Login-Check: /upload leitet eingeloggte User auf tiktokstudio/upload weiter
sin-chrome-control navigate "https://www.tiktok.com/upload" --tab <n>
sin-chrome-control status   # Tab-URL prüfen
```

Expected: `tiktokstudio/upload` (eingeloggt) statt `login`-Weiterleitung.

## Manual triggers

```bash
sin-browser-use <<'PY'
target = new_tab("https://www.tiktok.com/tiktokstudio/upload")
wait_for_load()
print(page_info())
# Datei-Upload bleibt ein sichtbarer, bestätigter UI-Schritt.
PY
# Upload im sichtbaren Fenster (Datei, Titel, Hashtags) — erst nach Freigabe publizieren
```

## Deploy wiring

No backend runtime involved for TikTok Social: publishing happens in TikTok
Studio via SIN-Chrome. ShopSIN backend endpoints (`/api/tiktok/*`, cron
`tiktok-*`) belong to the Shop API and are wired via the `tiktok-shop`
connector.

For ordinary multi-step actions use `sin-browser-use`; use `sin-chrome-control`
for identity/status gates and typed fallback.

See the skill
[`shared/skills/sin-tiktok/SKILL.md`](../../shared/skills/sin-tiktok/SKILL.md)
for the full runbook and CDP troubleshooting.

## Status (August 2026)

- Login tiktok.com funktioniert im SIN-Chrome bot profile (Session aktiv,
  `/upload` → `tiktokstudio/upload`).
- TikTok Studio erreichbar, Upload-Seite lädt.
- Account-Handle: `@systemfehler_nach_din`.
