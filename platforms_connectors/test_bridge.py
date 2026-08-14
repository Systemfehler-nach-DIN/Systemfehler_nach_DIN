import os
import unittest
from unittest.mock import patch

import bridge


SAMPLE = {
    "title": "Test title",
    "excerpt": "Test excerpt",
    "body": "Longer body",
    "media_url": "https://example.invalid/media.jpg",
    "url": "https://example.invalid/post",
    "cta": "Read more",
}


class BridgeTests(unittest.TestCase):
    def setUp(self):
        for name in (
            "PUBLISH_MODE",
            "ALLOW_REAL_POSTS",
            "YOUTUBE_API_LIVE_APPROVED",
            "TIKTOK_BROWSER_LIVE_APPROVED",
        ):
            os.environ.pop(name, None)
        self.addCleanup(self._clear_runtime_gates)

    @staticmethod
    def _clear_runtime_gates():
        for name in (
            "PUBLISH_MODE",
            "ALLOW_REAL_POSTS",
            "YOUTUBE_API_LIVE_APPROVED",
            "TIKTOK_BROWSER_LIVE_APPROVED",
        ):
            os.environ.pop(name, None)

    def test_all_decision_adapters_dry_run(self):
        result = bridge.publish(SAMPLE)
        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "DRY_RUN")
        self.assertEqual(
            set(x["platform"] for x in result["results"]), set(bridge.ADAPTERS)
        )
        self.assertTrue(all(x["validated"] for x in result["results"]))

    def test_tiktok_draft_uses_sin_browser_use_backend(self):
        result = bridge.publish(SAMPLE, ["tiktok"])
        self.assertEqual(
            result["results"][0]["backend"], "SIN-Browser-Use CLI 3.0 / TikTok Studio"
        )
        self.assertEqual(result["results"][0]["mode"], "DRAFT")

    def test_missing_required_field_rejected(self):
        with self.assertRaises(ValueError):
            bridge.publish({"title": "", "excerpt": "x"})

    def test_unknown_platform_rejected(self):
        with self.assertRaises(ValueError):
            bridge.publish(SAMPLE, ["not-a-platform"])

    def test_buffer_target_metadata_survives_normalization(self):
        payload = {
            **SAMPLE,
            "buffer_targets": [
                {
                    "account": 3,
                    "platform": "youtube",
                    "channel_id": "yt",
                    "media_type": "video",
                }
            ],
        }
        normalized = bridge.validate_payload(payload)
        self.assertEqual(normalized["buffer_targets"][0]["channel_id"], "yt")

    def test_youtube_api_live_gate_routes_to_api(self):
        os.environ["PUBLISH_MODE"] = "LIVE"
        os.environ["ALLOW_REAL_POSTS"] = "true"
        os.environ["YOUTUBE_API_LIVE_APPROVED"] = "true"
        with patch.object(
            bridge, "_publish_youtube_api", return_value={"video_id": "v"}
        ) as publisher:
            result = bridge.publish(SAMPLE, ["youtube"])
        publisher.assert_called_once()
        self.assertEqual(result["mode"], "LIVE")
        self.assertEqual(result["results"][0]["video_id"], "v")

    def test_tiktok_live_is_gated_to_browser_publisher(self):
        os.environ["PUBLISH_MODE"] = "LIVE"
        os.environ["ALLOW_REAL_POSTS"] = "true"
        os.environ["TIKTOK_BROWSER_LIVE_APPROVED"] = "true"
        with patch.object(
            bridge, "_publish_tiktok_browser", return_value={"video_id": "t"}
        ) as publisher:
            result = bridge.publish(SAMPLE, ["tiktok"])
        publisher.assert_called_once()
        self.assertEqual(result["mode"], "LIVE")

    def test_official_live_requires_per_platform_approval(self):
        os.environ["PUBLISH_MODE"] = "LIVE"
        os.environ["ALLOW_REAL_POSTS"] = "true"
        os.environ["INSTAGRAM_API_LIVE_APPROVED"] = "true"
        os.environ["INSTAGRAM_ACCESS_TOKEN"] = "test-token"
        os.environ["INSTAGRAM_USER_ID"] = "test-user"
        with patch(
            "platforms_connectors.Instagram.publish.publish",
            return_value={"platform": "instagram", "published": True},
        ) as publisher:
            result = bridge.publish(SAMPLE, ["instagram"])
        self.assertEqual(publisher.call_count, 2)
        self.assertEqual(publisher.call_args_list[-1].kwargs, {"dry_run": False})
        self.assertEqual(result["mode"], "LIVE")

    def test_live_is_fail_closed_even_when_enabled(self):
        os.environ["PUBLISH_MODE"] = "LIVE"
        os.environ["ALLOW_REAL_POSTS"] = "true"
        with self.assertRaises(PermissionError):
            bridge.publish(SAMPLE, ["discord"])


if __name__ == "__main__":
    unittest.main()


class LifecycleContractTests(unittest.TestCase):
    def setUp(self):
        bridge._LIFECYCLE_STORE.clear()

    def test_kestra_envelope_preserves_buffer_targets(self):
        payload, platforms = bridge._request_envelope(
            {
                "payload": {**SAMPLE, "content_id": "fixture-envelope"},
                "platforms": ["buffer"],
                "buffer_targets": [
                    {
                        "account": 3,
                        "platform": "youtube",
                        "channel_id": "yt-envelope",
                        "media_type": "video",
                    }
                ],
            }
        )
        self.assertEqual(platforms, ["buffer"])
        self.assertEqual(payload["buffer_targets"][0]["channel_id"], "yt-envelope")

    def test_buffer_published_is_terminal_sent_state(self):
        self.assertEqual(
            bridge._buffer_job_status(["sent", "published"]), (True, "sent")
        )
        self.assertEqual(
            bridge._buffer_job_status(["scheduled", "published"]),
            (False, "scheduled"),
        )
        self.assertEqual(
            bridge._buffer_job_status(["failed", "published"]), (False, "error")
        )

    def test_live_lifecycle_refuses_in_memory_durability(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "platforms_connectors.Buffer.publish.publish"
            ) as provider, self.assertRaisesRegex(
                PermissionError, "requires Supabase durability"
            ):
                bridge.lifecycle(
                    {**SAMPLE, "content_id": "fixture-live-no-db"}, dry_run=False
                )
        provider.assert_not_called()

    def test_lifecycle_dry_run_is_buffer_only_and_pending(self):
        from bridge import lifecycle

        payload = {
            **SAMPLE,
            "content_id": "fixture-1",
            "buffer_targets": [
                {
                    "account": 3,
                    "platform": "youtube",
                    "channel_id": "yt",
                    "media_type": "video",
                }
            ],
        }
        with patch.dict(os.environ, {}, clear=True):
            result = lifecycle(payload)
            self.assertEqual(result["status"], "scheduled")
            self.assertFalse(result["reconciliation"]["all_sent"])
            self.assertEqual(result["scheduled"]["durable"], False)
            again = lifecycle(payload)
        self.assertTrue(again["deduplicated"])
        self.assertEqual(result["idempotency_key"], again["idempotency_key"])

    def test_real_buffer_adapter_lifecycle_retry_never_creates_duplicate(self):
        durable = {}
        provider_calls = {"create": 0, "get": 0}

        def find_scheduled(*, idempotency_key):
            row = durable.get(idempotency_key)
            return dict(row) if row else None

        def record_scheduled(**kw):
            key = kw["idempotency_key"]
            current = durable.get(key)
            if kw["status"] == "draft" and current:
                return {**current, "existing": True}
            row = {
                "job_id": "job-r8",
                "content_id": kw["content_id"],
                "idempotency_key": key,
                "status": kw["status"],
                "targets": [dict(item) for item in kw.get("targets", [])],
                "durable": True,
            }
            if kw.get("provider_result") is not None:
                row["provider_result"] = kw["provider_result"]
            durable[key] = row
            return {**row, "existing": False}

        def request_json(endpoint, **kw):
            query = kw["data"]["query"]
            if "createPost" in query:
                provider_calls["create"] += 1
                return {
                    "data": {
                        "createPost": {
                            "__typename": "PostActionSuccess",
                            "post": {"id": "buffer-post-r8", "status": "scheduled"},
                        }
                    }
                }
            if "post(input:" in query:
                provider_calls["get"] += 1
                status = "scheduled" if provider_calls["get"] == 1 else "sent"
                return {
                    "data": {
                        "post": {
                            "id": "buffer-post-r8",
                            "status": status,
                            "dueAt": None,
                        }
                    }
                }
            self.fail("unexpected Buffer GraphQL operation")

        payload = {
            **SAMPLE,
            "content_id": "fixture-real-buffer-r8",
            "media_url": "https://example.invalid/video.mp4",
            "buffer_targets": [
                {
                    "account": 3,
                    "platform": "youtube",
                    "channel_id": "yt-r8",
                    "media_type": "video",
                }
            ],
        }
        env = {
            "SUPABASE_URL": "https://supabase.invalid",
            "SUPABASE_SERVICE_ROLE_KEY": "fixture-service-key",
            "BUFFER_API_KEY_ACCOUNT_3": "fixture-buffer-key",
            "BUFFER_RECONCILE_MAX_ATTEMPTS": "1",
            "BUFFER_RECONCILE_RETRY_SECONDS": "0",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch(
                "platforms_connectors.MediaStaging.staging.find_scheduled",
                side_effect=find_scheduled,
            ),
            patch(
                "platforms_connectors.MediaStaging.staging.record_scheduled",
                side_effect=record_scheduled,
            ),
            patch(
                "platforms_connectors.MediaStaging.staging.record_job_status"
            ) as record_job_status,
            patch(
                "platforms_connectors.MediaStaging.staging.record_target_status"
            ) as record_target_status,
            patch(
                "platforms_connectors.MediaStaging.staging.mark_published"
            ) as mark_published,
            patch(
                "platforms_connectors.MediaStaging.staging.cleanup_due",
                return_value={"deleted": 0, "skipped": 1},
            ) as cleanup_due,
            patch(
                "platforms_connectors.Buffer.publish.request_json",
                side_effect=request_json,
            ),
        ):
            first = bridge.lifecycle(payload, dry_run=False)
            second = bridge.lifecycle(payload, dry_run=False)
            third = bridge.lifecycle(payload, dry_run=False)

        self.assertEqual(first["status"], "scheduled")
        self.assertEqual(
            first["scheduled"]["targets"][0]["buffer_post_id"], "buffer-post-r8"
        )
        self.assertEqual(second["status"], "sent")
        self.assertTrue(second["deduplicated"])
        self.assertEqual(third["status"], "sent")
        self.assertTrue(third["deduplicated"])
        self.assertEqual(provider_calls["create"], 1)
        self.assertEqual(provider_calls["get"], 2)
        self.assertGreaterEqual(record_target_status.call_count, 2)
        self.assertGreaterEqual(record_job_status.call_count, 2)
        mark_published.assert_called_once()
        self.assertEqual(cleanup_due.call_count, 2)
