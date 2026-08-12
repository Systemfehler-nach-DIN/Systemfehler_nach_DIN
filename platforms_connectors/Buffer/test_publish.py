import unittest
from unittest.mock import patch

from platforms_connectors.Buffer.publish import publish


class BufferPublishTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "title": "Test",
            "excerpt": "Excerpt",
            "body": "Body",
            "media_url": "https://cdn.example/test.jpg",
            "buffer": {
                "channel_id": "channel",
                "service": "instagram",
            },
        }

    def test_dry_run_requires_no_key_or_network(self):
        result = publish(self.payload, dry_run=True)
        self.assertEqual(result["mode"], "DRY_RUN")
        self.assertEqual(result["backend"], "Buffer API (GraphQL)")

    @patch("platforms_connectors.Buffer.publish.request_json")
    def test_live_uses_bearer_and_returns_post_id(self, request):
        request.return_value = {
            "data": {
                "createPost": {
                    "__typename": "PostActionSuccess",
                    "post": {"id": "post-1"},
                }
            }
        }
        with patch.dict("os.environ", {"BUFFER_API_KEY": "key"}):
            result = publish(self.payload, dry_run=False)
        self.assertEqual(result["external_id"], "post-1")
        self.assertIn(
            "Bearer key", request.call_args.kwargs["headers"]["Authorization"]
        )

    def test_account_three_youtube_registry_shape(self):
        payload = {
            "title": "Video", "excerpt": "E", "body": "B",
            "media_url": "https://cdn.example/video.mp4",
            "buffer_targets": [{"account": 3, "platform": "youtube",
                "channel_id": "6a7cf0c4b2d9d57743679762", "media_type": "video"}],
        }
        result = publish(payload, dry_run=True)
        target = result["targets"][0]
        self.assertEqual(target["channelId"], "6a7cf0c4b2d9d57743679762")
        self.assertEqual(target["assets"][0]["video"]["url"], payload["media_url"])
        self.assertEqual(target["metadata"]["youtube"]["categoryId"], "22")

    def test_multiple_buffer_targets_are_fanned_out(self):
        payload = {**self.payload, "buffer_targets": [
            {"account": 1, "platform": "instagram", "channel_id": "ig", "media_type": "image"},
            {"account": 3, "platform": "youtube", "channel_id": "yt", "media_type": "video"},
        ], "media_url": "https://cdn.example/video.mp4"}
        result = publish(payload, dry_run=True)
        self.assertEqual([x["channelId"] for x in result["targets"]], ["ig", "yt"])

    def test_registry_default_contains_nine_channels(self):
        from platforms_connectors.Buffer.router import all_channels
        self.assertEqual(len(all_channels()), 9)
        self.assertEqual(next(x for x in all_channels() if x["platform"] == "youtube")["account"], "3")
