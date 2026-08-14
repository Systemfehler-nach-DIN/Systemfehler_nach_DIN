# Supabase media staging

TeraBox-SIN remains the durable archive. Supabase Storage is a temporary
staging layer that provides stable public HTTPS URLs to Buffer until a post has
been confirmed as sent. The service-role key is runtime-only from Infisical.

```bash
scripts/media-staging stage --path /path/video.mp4 --content-id content-123
scripts/media-staging stage-terabox \
  --remote-path /archive/video.mp4 --fs-id 123456 --content-id content-123
scripts/media-staging mark-published --content-id content-123 --grace-hours 48
scripts/media-staging cleanup
```

`stage-terabox` is read-only toward TeraBox. It first runs `terabox-sin status`
and requires both `configured=true` and `authenticated=true`; otherwise it
stops before requesting a download. The source is addressed by numeric `fs_id`,
the short-lived download URL is consumed internally, and no TeraBox delete or
mutation method exists in this path. Source path/fs_id, SHA-256 and Supabase
object metadata are retained as provenance.

Cleanup only deletes rows marked `published` whose grace period has elapsed.
Scheduled and failed media are retained. No public anonymous database policies
are created by the migration.


## Reconciliation commands

After Buffer accepts a schedule, persist the job and target IDs:

```bash
scripts/media-staging record-scheduled --content-id item-123 \
  --idempotency-key '<deterministic-lifecycle-key>' \
  --scheduled-at 2026-08-13T12:00:00Z \
  --targets-json '[{"account":3,"platform":"youtube","channel_id":"6a7cf0c4b2d9d57743679762","buffer_post_id":"post-id"}]'
scripts/media-staging record-target-status --buffer-post-id post-id --status sent
scripts/media-staging mark-published --content-id item-123 --grace-hours 48
scripts/media-staging cleanup
```

`record-scheduled` atomically reserves/upserts by `(provider,idempotency_key)`
and reconciles target rows by `(job_id,account,platform,channel_id)`. Persisted
`buffer_post_id` values survive process restarts and are the authority for later
Buffer status reconciliation. `cleanup` checks for any non-terminal job before
deleting an asset. It reports `deleted` and `skipped` counts and never deletes
TeraBox originals.
