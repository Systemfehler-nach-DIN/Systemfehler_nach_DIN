import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from platforms_connectors.YouTube import youtube_api


class YouTubeApiTests(unittest.TestCase):
    def test_client_config_and_token_are_loaded_without_network(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            client = root / "client.json"
            token = root / "token.json"
            client.write_text(
                json.dumps(
                    {
                        "installed": {
                            "client_id": "client-id",
                            "client_secret": "secret",
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": youtube_api.TOKEN_URL,
                        }
                    }
                )
            )
            token.write_text(
                json.dumps(
                    {
                        "access_token": "access",
                        "refresh_token": "refresh",
                        "expires_at": 4102444800,
                    }
                )
            )
            api = youtube_api.YouTubeApi(str(client), str(token))
            self.assertEqual(api.token.access_token, "access")
            self.assertEqual(api.token.client_id, "client-id")

    def test_comment_and_moderation_operations_use_documented_endpoints(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            client = root / "client.json"
            token = root / "token.json"
            client.write_text(
                json.dumps(
                    {"installed": {"client_id": "id", "client_secret": "secret"}}
                )
            )
            token.write_text(
                json.dumps({"access_token": "access", "expires_at": 4102444800})
            )
            api = youtube_api.YouTubeApi(str(client), str(token))
            requests = []

            def fake_request(req, timeout=60):
                requests.append(req)
                return 200, {}, b'{"ok":true}'

            with patch.object(youtube_api, "_request", side_effect=fake_request):
                api.list_comment_threads("video")
                api.reply("parent", "reply")
                api.update_comment("comment", "edited")
                api.delete_comment("comment")
                api.moderate_comment("comment", "rejected")
            urls = [request.full_url for request in requests]
            self.assertIn("commentThreads", urls[0])
            self.assertIn("comments?part=snippet", urls[1])
            self.assertIn("setModerationStatus", urls[-1])

    def test_search_and_playlist_lifecycle_use_official_resources(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            client = root / "client.json"
            token = root / "token.json"
            client.write_text(json.dumps({"installed": {"client_id": "id", "client_secret": "secret"}}))
            token.write_text(json.dumps({"access_token": "access", "expires_at": 4102444800}))
            api = youtube_api.YouTubeApi(str(client), str(token))
            requests = []

            def fake_request(req, timeout=60):
                requests.append(req)
                if req.method == "GET" and "playlists?part" in req.full_url:
                    return 200, {}, b'{"items":[{"id":"pl","snippet":{"title":"Old","description":""},"status":{"privacyStatus":"private"}}]}'
                return 200, {}, b'{"items":[]}'

            with patch.object(youtube_api, "_request", side_effect=fake_request):
                api.search("sin", resource_type="video")
                api.list_playlists()
                api.update_playlist("pl", title="New")
                api.delete_playlist("pl")
            self.assertIn("/search?", requests[0].full_url)
            self.assertIn("/playlists?part=snippet%2Cstatus%2CcontentDetails", requests[1].full_url)
            self.assertEqual(requests[2].method, "GET")
            self.assertEqual(requests[-1].method, "DELETE")

    def test_upload_uses_resumable_protocol(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            client = root / "client.json"
            token = root / "token.json"
            video = root / "test.mp4"
            client.write_text(
                json.dumps(
                    {"installed": {"client_id": "id", "client_secret": "secret"}}
                )
            )
            token.write_text(
                json.dumps({"access_token": "access", "expires_at": 4102444800})
            )
            video.write_bytes(b"video")
            api = youtube_api.YouTubeApi(str(client), str(token))
            requests = []

            def fake_request(req, timeout=60):
                requests.append(req)
                if len(requests) == 1:
                    return 200, {"Location": "https://upload.example/session"}, b""
                return 200, {}, b'{"id":"video-id"}'

            with patch.object(youtube_api, "_request", side_effect=fake_request):
                result = api.upload(str(video), "Test")
            self.assertEqual(result["id"], "video-id")
            self.assertIn("uploadType=resumable", requests[0].full_url)
            self.assertEqual(requests[1].get_header("Content-range"), "bytes 0-4/5")

    def test_upload_rejects_missing_local_file(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            client = root / "client.json"
            token = root / "token.json"
            client.write_text(
                json.dumps(
                    {"installed": {"client_id": "id", "client_secret": "secret"}}
                )
            )
            token.write_text(
                json.dumps({"access_token": "access", "expires_at": 4102444800})
            )
            api = youtube_api.YouTubeApi(str(client), str(token))
            with self.assertRaises(youtube_api.YouTubeApiError):
                api.upload(str(root / "missing.mp4"), "Test")


if __name__ == "__main__":
    unittest.main()
