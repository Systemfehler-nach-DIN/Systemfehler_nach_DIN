# Buffer-Integration

Stand: 2026-08-12. Buffer ist der bevorzugte Publishing-Layer für neun
verifizierte Buffer-Kanäle. API-Keys bleiben in Infisical; zur Laufzeit wird
der gewünschte Account-Key als `BUFFER_API_KEY` injiziert.

## Abdeckung

| Buffer-Account | Organisation | Kanäle |
|---|---|---|
| 1 | `6a7cdff6ba121c15135353f4` | Instagram, Threads, LinkedIn |
| 2 | `6a7ce320460832fbfcda7d98` | Facebook, Bluesky, Mastodon |
| 3 | `6a7ce8391c7f43f54a9c0b59` | Pinterest, X/Twitter, YouTube (`6a7cf0c4b2d9d57743679762`, `UCBWRl7VXRdy0kcsoV7or7Uw`) |

Alle inventarisierten Channels meldeten `isDisconnected=false`.

## Grenzen

- Buffer API unterstützt laut aktueller Doku: Instagram, Threads, LinkedIn,
  X, Facebook, Mastodon, YouTube, Pinterest und Bluesky. Der YouTube-Kanal
  `Systemfehler_nach_DIN` ist nun in Account 3 verbunden und als
  `isDisconnected=false` verifiziert.
- TikTok ist im Buffer-Produkt gelistet, aber nicht in der aktuellen API-Liste
  und nicht im Channel-Inventar. TikTok bleibt beim SIN-Adapter.
- Für Medien erwartet Buffer eine stabile, öffentliche HTTPS-URL. Private oder
  ablaufende Storage-Links sind für geplante Posts ungeeignet.
- Free ist nicht unbegrenzt: bis zu drei Channels pro Account, 10 geplante
  Posts je Channel (auffüllbar), 100 Ideen und 3.000 API-Anfragen/Monat je
  API-Key laut Pricing-Seite.
- Alle Mutationen bleiben bis zum expliziten Live-Gate `DRY_RUN`; vor jeder
  Mutation muss `buffer ... --dry-run` erfolgreich sein.

## Offene Implementierung

Der Projekt-Bridge-Adapter für Buffer ist implementiert und getestet (inklusive
account/channel routing, Multi-Target-Dry-Run und YouTube-Metadaten). Postiz ist
aktuell nicht erreichbar; sein offizieller Multi-Container-Stack und der direkte
Postiz→Buffer→YouTube/TikTok-Orchestrierungsweg sind noch nicht verifiziert und
bleiben offen.

## Media lifecycle: TeraBox → Supabase → Buffer

TeraBox-SIN is the durable archive. Supabase Storage bucket `social-staging`
is temporary production storage for stable public HTTPS URLs consumed by Buffer.
The migration is `supabase/migrations/001_social_staging.sql`; it tracks media,
publish jobs, targets, hashes and cleanup timestamps. Media is not deleted when
Buffer accepts a scheduled post: only after a confirmed `sent`/published state
and a 48-hour grace period. Scheduled or errored media is retained. No Supabase
runtime endpoint was guessed or mutated; OCI health/auth discovery remains an
external infrastructure step.

## Deployment-Gate

Der lokale Staging-Adapter und die Migration sind implementiert, aber noch nicht
auf der OCI-Supabase-Instanz angewendet. Ein authentifizierter REST-Read gegen
`https://supabase.delqhi.com` bestätigte HTTP 404/PGRST205 für `media_assets`;
damit ist die Tabelle aktuell nicht vorhanden. Vor der ersten echten Planung müssen
Endpoint, Bucket, Service-Role-Zugriff, öffentliche Objekt-URLs und RLS auf der
VM read-only verifiziert werden. Tailscale-SSH war bei der Discovery durch einen
zusätzlichen Authentifizierungs-Gate blockiert; deshalb wurde nichts remote
mutiert.

## OCI-Supabase deployment completed

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
Bestand. Keine Medien wurden hochgeladen und keine Live-Posts versendet.
