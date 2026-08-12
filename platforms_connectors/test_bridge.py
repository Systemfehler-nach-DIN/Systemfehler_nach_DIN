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
        os.environ.pop("PUBLISH_MODE", None)
        os.environ.pop("ALLOW_REAL_POSTS", None)
        os.environ.pop("YOUTUBE_API_LIVE_APPROVED", None)

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
        self.assertEqual(result["results"][0]["backend"], "SIN-Browser-Use CLI 3.0 / TikTok Studio")
        self.assertEqual(result["results"][0]["mode"], "DRAFT")

    def test_missing_required_field_rejected(self):
        with self.assertRaises(ValueError):
            bridge.publish({"title": "", "excerpt": "x"})

    def test_unknown_platform_rejected(self):
        with self.assertRaises(ValueError):
            bridge.publish(SAMPLE, ["not-a-platform"])

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

    def test_live_is_fail_closed_even_when_enabled(self):
        os.environ["PUBLISH_MODE"] = "LIVE"
        os.environ["ALLOW_REAL_POSTS"] = "true"
        with self.assertRaises(PermissionError):
            bridge.publish(SAMPLE, ["discord"])


if __name__ == "__main__":
    unittest.main()
