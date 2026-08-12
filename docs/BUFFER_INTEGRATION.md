# Buffer-Integration

Stand: 2026-08-12. Buffer ist der bevorzugte Publishing-Layer für die acht
verifizierten Buffer-Kanäle (9 Kanäle). API-Keys bleiben in Infisical; zur Laufzeit wird
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
