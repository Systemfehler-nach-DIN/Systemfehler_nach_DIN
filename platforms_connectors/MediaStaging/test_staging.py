import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from platforms_connectors.MediaStaging.staging import (
    StagingError,
    _request,
    cleanup_due,
    mark_published,
    record_scheduled,
    record_target_status,
    stage_file,
    stage_terabox_reference,
)


class StagingTests(unittest.TestCase):

    @patch("platforms_connectors.MediaStaging.staging.httpx.request")
    def test_request_uses_httpx_and_returns_json(self, request):
        response = Mock()
        response.content = b'{"ok":true}'
        response.json.return_value = {"ok": True}
        response.raise_for_status.return_value = None
        request.return_value = response
        result = _request(
            "https://supabase.example/rest/v1/publish_jobs",
            key="service-key",
            method="GET",
        )
        self.assertEqual(result, {"ok": True})
        self.assertEqual(request.call_args.args[:2], ("GET", "https://supabase.example/rest/v1/publish_jobs"))
        self.assertEqual(request.call_args.kwargs["headers"]["User-Agent"], "Systemfehler-nach-DIN-MediaStaging/1.0")
        self.assertEqual(request.call_args.kwargs["timeout"], 60.0)

    @patch("platforms_connectors.MediaStaging.staging.httpx.request")
    def test_request_masks_http_status_details(self, request):
        import httpx

        req = httpx.Request("GET", "https://supabase.example/rest/v1/publish_jobs")
        response = httpx.Response(403, request=req, text="sensitive upstream body")
        request.side_effect = httpx.HTTPStatusError("forbidden", request=req, response=response)
        with self.assertRaisesRegex(StagingError, r"Supabase request failed: 403") as raised:
            _request(
                "https://supabase.example/rest/v1/publish_jobs",
                key="service-key",
                method="GET",
            )
        self.assertNotIn("service-key", str(raised.exception))
        self.assertNotIn("sensitive upstream body", str(raised.exception))
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
            idempotency_key="lifecycle-key-123",
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
        persisted_job = json.loads(request.call_args_list[0].kwargs["body"].decode())
        self.assertEqual(persisted_job["idempotency_key"], "lifecycle-key-123")
        self.assertIn("on_conflict=provider%2Cidempotency_key", request.call_args_list[0].args[0])
        persisted_targets = json.loads(request.call_args_list[1].kwargs["body"].decode())
        self.assertEqual(persisted_targets[0]["buffer_post_id"], "post-1")
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

    @patch("platforms_connectors.MediaStaging.staging.urlopen")
    @patch("platforms_connectors.MediaStaging.staging.stage_file")
    @patch("platforms_connectors.MediaStaging.staging.subprocess.run")
    def test_terabox_reference_uses_numeric_fs_id_and_dlink(self, run, stage, urlopen):
        import tempfile
        from contextlib import contextmanager

        class Response:
            def read(self, size=-1):
                if self.done:
                    return b""
                self.done = True
                return b"fixture"

            def __enter__(self):
                self.done = False
                return self

            def __exit__(self, *args):
                return False

        @contextmanager
        def fake_open(*args, **kwargs):
            response = Response()
            response.__enter__()
            yield response

        urlopen.side_effect = fake_open
        run.side_effect = [
            type(
                "Result",
                (),
                {
                    "stdout": json.dumps({"configured": True, "authenticated": True}),
                    "stderr": "",
                },
            )(),
            type(
                "Result",
                (),
                {
                    "stdout": json.dumps({"dlink": "https://download.example/file"}),
                    "stderr": "",
                },
            )(),
        ]
        stage.return_value = {"status": "staged"}
        with tempfile.TemporaryDirectory() as tmp:
            result = stage_terabox_reference(
                "/archive/clip.mp4", content_id="c1", fs_id=42, output_dir=tmp
            )
        self.assertEqual(run.call_args_list[0].args[0], ["terabox-sin", "status"])
        args = json.loads(run.call_args_list[1].args[0][3])
        self.assertEqual(args, [[42]])
        self.assertEqual(urlopen.call_args.args[0], "https://download.example/file")
        self.assertEqual(result["source_fs_id"], 42)

    @patch("platforms_connectors.MediaStaging.staging.urlopen")
    @patch("platforms_connectors.MediaStaging.staging.stage_file")
    @patch("platforms_connectors.MediaStaging.staging.subprocess.run")
    def test_terabox_reference_fails_before_download_when_not_authenticated(
        self, run, stage, urlopen
    ):
        from platforms_connectors.MediaStaging.staging import StagingError

        run.return_value = type(
            "Result",
            (),
            {
                "stdout": json.dumps({"configured": False, "authenticated": False}),
                "stderr": "",
            },
        )()
        with self.assertRaisesRegex(StagingError, "not configured and authenticated"):
            stage_terabox_reference("/archive/clip.mp4", content_id="c1", fs_id=42)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0], ["terabox-sin", "status"])
        stage.assert_not_called()
        urlopen.assert_not_called()

    @patch("platforms_connectors.MediaStaging.staging._request")
    @patch(
        "platforms_connectors.MediaStaging.staging._config",
        return_value=("https://supabase.example", "service-key", "social-staging"),
    )
    def test_draft_reservation_conflict_returns_existing_durable_job(
        self, config, request
    ):
        request.side_effect = [
            [],
            [
                {
                    "job_id": "job-existing",
                    "content_id": "item-1",
                    "idempotency_key": "same-key",
                    "status": "scheduled",
                }
            ],
            [
                {
                    "account": 3,
                    "platform": "youtube",
                    "channel_id": "yt",
                    "buffer_post_id": "post-existing",
                    "status": "scheduled",
                    "last_error": None,
                }
            ],
        ]
        result = record_scheduled(
            content_id="item-1",
            scheduled_at=None,
            targets=[],
            idempotency_key="same-key",
            status="draft",
        )
        self.assertTrue(result["existing"])
        self.assertEqual(result["job_id"], "job-existing")
        self.assertEqual(result["targets"][0]["buffer_post_id"], "post-existing")
        self.assertIn(
            "resolution=ignore-duplicates",
            request.call_args_list[0].kwargs["headers"]["Prefer"],
        )


if __name__ == "__main__":
    unittest.main()
