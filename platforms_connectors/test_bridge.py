import os
import unittest

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

    def test_all_decision_adapters_dry_run(self):
        result = bridge.publish(SAMPLE)
        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "DRY_RUN")
        self.assertEqual(set(x["platform"] for x in result["results"]), set(bridge.ADAPTERS))
        self.assertTrue(all(x["validated"] for x in result["results"]))

    def test_missing_required_field_rejected(self):
        with self.assertRaises(ValueError):
            bridge.publish({"title": "", "excerpt": "x"})

    def test_unknown_platform_rejected(self):
        with self.assertRaises(ValueError):
            bridge.publish(SAMPLE, ["not-a-platform"])

    def test_live_is_fail_closed_even_when_enabled(self):
        os.environ["PUBLISH_MODE"] = "LIVE"
        os.environ["ALLOW_REAL_POSTS"] = "true"
        with self.assertRaises(PermissionError):
            bridge.publish(SAMPLE, ["discord"])


if __name__ == "__main__":
    unittest.main()
