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


## Reconciliation commands

After Buffer accepts a schedule, persist the job and target IDs:

```bash
scripts/media-staging record-scheduled --content-id item-123 \
  --scheduled-at 2026-08-13T12:00:00Z \
  --targets-json '[{"account":3,"platform":"youtube","channel_id":"6a7cf0c4b2d9d57743679762","buffer_post_id":"post-id"}]'
scripts/media-staging record-target-status --buffer-post-id post-id --status sent
scripts/media-staging mark-published --content-id item-123 --grace-hours 48
scripts/media-staging cleanup
```

`cleanup` checks for any non-terminal job before deleting an asset. It reports
`deleted` and `skipped` counts and never deletes TeraBox originals.
