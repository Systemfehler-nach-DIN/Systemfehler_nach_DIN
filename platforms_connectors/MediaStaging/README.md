# Supabase media staging

TeraBox-SIN remains the durable archive. Supabase Storage is a temporary
staging layer that provides stable public HTTPS URLs to Buffer until a post has
been confirmed as sent. The service-role key is runtime-only from Infisical.

```bash
scripts/media-staging stage --path /path/video.mp4 --content-id content-123
scripts/media-staging mark-published --content-id content-123 --grace-hours 48
scripts/media-staging cleanup
```

Cleanup only deletes rows marked `published` whose grace period has elapsed.
Scheduled and failed media are retained. No public anonymous database policies
are created by the migration.
