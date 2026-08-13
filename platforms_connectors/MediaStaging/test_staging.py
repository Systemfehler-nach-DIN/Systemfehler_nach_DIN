import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from platforms_connectors.MediaStaging.staging import (
    cleanup_due,
    mark_published,
    record_scheduled,
    record_target_status,
    stage_file,
)


class StagingTests(unittest.TestCase):
    @patch("platforms_connectors.MediaStaging.staging._request")
    @patch(
        "platforms_connectors.MediaStaging.staging._config",
        return_value=("https://supabase.example", "service-key", "social-staging"),
    )
    def test_stage_file_uses_public_stable_url_and_hash(self, config, request):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clip.mp4"
            path.write_bytes(b"media")
            row = stage_file(str(path), content_id="item-1")
        self.assertTrue(
            row["public_url"].endswith(
                "/social-staging/item-1/" + row["media_id"] + ".mp4"
            )
        )
        self.assertEqual(row["status"], "staged")
        self.assertEqual(request.call_count, 2)

    @patch("platforms_connectors.MediaStaging.staging._request")
    @patch(
        "platforms_connectors.MediaStaging.staging._config",
        return_value=("https://supabase.example", "service-key", "social-staging"),
    )
    def test_mark_published_sets_grace_period_without_deleting(self, config, request):
        result = mark_published(content_id="item-1", grace_hours=48)
        self.assertEqual(result["status"], "published")
        self.assertEqual(request.call_count, 2)
        self.assertEqual(request.call_args_list[0].kwargs["method"], "PATCH")

    @patch("platforms_connectors.MediaStaging.staging._request")
    @patch(
        "platforms_connectors.MediaStaging.staging._config",
        return_value=("https://supabase.example", "service-key", "social-staging"),
    )
    def test_schedule_and_reconcile_never_store_credentials(self, config, request):
        request.side_effect = [[{"job_id": "job-1"}], [{}], [{}]]
        result = record_scheduled(
            content_id="item-1",
            scheduled_at="2026-08-13T12:00:00Z",
            targets=[
                {
                    "account": 3,
                    "platform": "youtube",
                    "channel_id": "yt",
                    "buffer_post_id": "post-1",
                }
            ],
        )
        self.assertEqual(result["job_id"], "job-1")
        self.assertEqual(request.call_count, 2)
        state = record_target_status(buffer_post_id="post-1", status="sent")
        self.assertEqual(state["status"], "sent")
        for call in request.call_args_list:
            self.assertNotIn("service-key", call.kwargs.get("body", b"").decode())

    @patch(
        "platforms_connectors.MediaStaging.staging._request",
        side_effect=[
            [{"media_id": "m1", "object_path": "item/m1.mp4", "content_id": "item"}],
            [],
            {},
            {},
        ],
    )
    @patch(
        "platforms_connectors.MediaStaging.staging._config",
        return_value=("https://supabase.example", "service-key", "social-staging"),
    )
    def test_cleanup_deletes_only_due_published_assets(self, config, request):
        result = cleanup_due(now_epoch=100)
        self.assertEqual(result, {"deleted": 1, "skipped": 0})
        self.assertEqual(request.call_count, 4)


if __name__ == "__main__":
    unittest.main()
