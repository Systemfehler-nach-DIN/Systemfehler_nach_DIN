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
