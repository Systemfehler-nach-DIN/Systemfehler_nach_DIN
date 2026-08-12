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
        payload = {**SAMPLE, "buffer_targets": [{"account": 3, "platform": "youtube", "channel_id": "yt", "media_type": "video"}]}
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
