# Buffer-Integration

Stand: 2026-08-14. Buffer ist die einzige Scheduling-Grenze für die neun
inventarisierten Buffer-Kanäle. Die drei Account-Keys bleiben in Infisical und
werden als `BUFFER_API_KEY_ACCOUNT_1..3` ausschließlich zur Laufzeit injiziert.
`PUBLISH_MODE=DRY_RUN` und `ALLOW_REAL_POSTS=false` bleiben die Defaults.

## Abdeckung

| Buffer-Account | Organisation | Kanäle |
|---|---|---|
| 1 | `6a7cdff6ba121c15135353f4` | Instagram, Threads, LinkedIn |
| 2 | `6a7ce320460832fbfcda7d98` | Facebook, Bluesky, Mastodon |
| 3 | `6a7ce8391c7f43f54a9c0b59` | Pinterest, X/Twitter, YouTube (`6a7cf0c4b2d9d57743679762`, `UCBWRl7VXRdy0kcsoV7or7Uw`) |

Alle neun Channels wurden am 2026-08-14 read-only über die jeweilige
Infisical-injizierte Buffer-Credential erneut gelesen und meldeten
`isDisconnected=false`. Der Pinterest-Kanal ist verbunden, liefert aber aktuell
`boards: []`; daher existiert noch kein verifizierbarer `board_service_id`.

## Grenzen

- Buffer API unterstützt laut aktueller Doku: Instagram, Threads, LinkedIn,
  X, Facebook, Mastodon, YouTube, Pinterest und Bluesky. Der YouTube-Kanal
  `Systemfehler_nach_DIN` ist nun in Account 3 verbunden und als
  `isDisconnected=false` verifiziert.
- TikTok ist im Buffer-Produkt gelistet, aber nicht in der aktuellen API-Liste
  und nicht im Channel-Inventar. TikTok bleibt beim SIN-Adapter.
- Für Medien erwartet Buffer eine stabile, öffentliche HTTPS-URL. Private oder
  ablaufende Storage-Links sind für geplante Posts ungeeignet.
- Alle Mutationen bleiben bis zum expliziten Live-Gate `DRY_RUN`; der kanonische
  `/lifecycle`-HTTP-Pfad akzeptiert nur `platforms: ["buffer"]`. Kestra hat
  zusätzlich einen eigenen Buffer-only-Validator.
- Pinterest wird fail-closed behandelt: Platzhalter wie
  `PENDING_EXTERNAL_BUFFER_BOARD_ID` werden nicht als Board-ID akzeptiert.
  Solange Buffer keine Board-Metadaten liefert, bleibt nur dieser eine Zielpfad
  extern blockiert; es wird keine ID geraten oder erfunden.
- X/Twitter wird in der lokalen Registry kanonisch als `x` geführt; der Router
  normalisiert `x` und Buffer-Service `twitter` symmetrisch.

## Reproduzierbare Lifecycle-Evidence

```bash
python3 scripts/verify_buffer_lifecycle.py
python3 -m unittest discover -s platforms_connectors -p 'test_*.py' -v
```

Der Fixture deckt TeraBox-Read-only-Vertrag, Supabase-Staging, echten
Projekt-Buffer-Adapter im DRY_RUN, persistierte Buffer-ID, Restart/Retry ohne
zweiten Provider-Create sowie Grace-Period-Cleanup ab. Die JSON-Evidence liegt
unter `.sin-goal/buffer-fleet-completion/evidence/`.

## Media lifecycle: TeraBox → Supabase → Buffer

TeraBox-SIN is the durable archive. Supabase Storage bucket `social-staging`
is temporary production storage for stable public HTTPS URLs consumed by Buffer.
The migration is `supabase/migrations/001_social_staging.sql`; it tracks media,
publish jobs, targets, hashes and cleanup timestamps. Media is not deleted when
Buffer accepts a scheduled post: only after a confirmed `sent`/published state
and a 48-hour grace period. Scheduled or errored media is retained. Die aktuelle Migration ergänzt eine eindeutige `(provider,idempotency_key)`-
Reservation und eindeutige Target-Identitäten, damit Retries nach Prozessneustart
keine zweite Buffer-Planung erzeugen. Der aktuelle Lifecycle verweigert LIVE,
wenn Supabase-Durability nicht verfügbar ist.

## OCI-Supabase deployment

Am 2026-08-13 wurde der live entdeckte OCI-Host `sin-supabase` über den
verifizierten OCI-Public-IP-Pfad `92.5.60.87` und Benutzer `ubuntu` erreicht.
Die bestehende Compose-Installation unter `/opt/sin-supabase` war aktiv und
healthy. Die Migration `supabase/migrations/001_social_staging.sql` wurde per
SSH-stdin mit `psql --single-transaction` in `supabase-db` angewendet. Danach
wurde PostgREST per `NOTIFY pgrst, 'reload schema'` aktualisiert.

Read-only verifiziert: `public.media_assets`, `public.publish_jobs` und
`public.publish_targets` existieren; Storage-Bucket `social-staging` ist
`public=true`; der authentifizierte REST-Read gegen
`https://supabase.delqhi.com/rest/v1/media_assets` liefert HTTP 200 mit leerem
Bestand. Keine Medien wurden bei dieser Read-only-Verifikation hochgeladen und keine
Live-Posts versendet. In der aktuellen Fresh-Chat-Welle konnte eine zusätzliche
Supabase-Mutationsprobe nicht ausgeführt werden, weil der lokale Connector den
POST/DELETE-Test vor Ausführung blockierte; deshalb wird dafür keine neue
Live-Evidence behauptet.

## Aktuelle externe Blocker

- **TeraBox:** `terabox-sin status` meldet `configured=false` und
  `authenticated=false`. Der neue `stage-terabox`-Pfad stoppt deshalb vor jedem
  Download. Mocked/read-only-contract Evidence ist vorhanden, echter TeraBox-E2E
  bleibt bis zur Authentifizierung offen.
- **Pinterest:** der verbundene Kanal liefert read-only `boards: []`; ohne echten
  Board-`serviceId` bleibt Pinterest fail-closed.
- **Kestra Flow-Revision:** der lokale Stack läuft, aber die CLI/API-Validierung
  der neu bearbeiteten Flow-Datei antwortete in dieser Session mit
  `Client 'remote-api': Unauthorized`. Die Datei und ihre hermetischen Contracts
  sind getestet; eine neue installierte Kestra-Revision wird nicht behauptet.
