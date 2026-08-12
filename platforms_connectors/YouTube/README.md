# YouTube-Connectoren

Alle YouTube-spezifischen Adapter und Offline-Tests liegen in diesem Verzeichnis.

- `youtube_api.py` — offizieller YouTube Data API v3-Adapter (OAuth, Uploads,
  Metadaten, Suche, Kommentare, Moderation, Thumbnails und vollständige
  Playlist-Verwaltung).
- `youtube_community.py` — Community-/Studio-Fallback über SIN-Browser-Use CLI
  3.0 im authentifizierten SIN-Chrome-`bot`; Playwright nur explizit als Legacy-
  Backend.
- `youtube_upload.py` — Upload-Hilfsadapter.
- `youtube_api.py --delete-video` — nach Verifikation Testvideos entfernen.
- `test_*.py` — netzwerkfreie Tests.

Die gemeinsame Bridge (`../bridge.py`) hält die API als Primärpfad. Live-Aktionen
bleiben fail-closed und erfordern die jeweiligen `PUBLISH_MODE`,
`ALLOW_REAL_POSTS` sowie YouTube-spezifischen Freigaben.

```bash
cd platforms_connectors
python3 YouTube/youtube_api.py --channel \
  --token ~/.config/sin-youtube/youtube-oauth-token.json
python3 -m pytest -q YouTube
```
