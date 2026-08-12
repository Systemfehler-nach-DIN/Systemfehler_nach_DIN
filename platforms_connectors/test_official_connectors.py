from __future__ import annotations

import importlib

import pytest

PLATFORMS = (
    "Instagram",
    "Facebook",
    "Threads",
    "X",
    "Reddit",
    "LinkedIn",
    "Pinterest",
    "Bluesky",
    "Mastodon",
    "Telegram",
    "Discord",
)


@pytest.fixture
def payload():
    return {
        "title": "Test",
        "excerpt": "Offline test",
        "body": "Offline test body",
        "media_url": "https://cdn.example/test.jpg",
        "url": "https://example.test",
    }


@pytest.mark.parametrize("platform", PLATFORMS)
def test_dry_run_never_requires_credentials_or_network(platform, payload):
    module = importlib.import_module(f"platforms_connectors.{platform}.publish")
    result = module.publish(payload, dry_run=True)
    assert result["mode"] == "DRY_RUN"
    assert result["published"] is False
    assert result["validated"] is True


def test_bridge_uses_official_backend_metadata():
    from platforms_connectors.bridge import ADAPTERS

    assert ADAPTERS["instagram"].backend == "Instagram Graph API"
    assert ADAPTERS["x"].backend == "X API v2"
    assert ADAPTERS["reddit"].backend == "Reddit OAuth API"
    assert "INSTAGRAM_PASSWORD" not in ADAPTERS["instagram"].auth_env


def test_bridge_dry_run_routes_all_official_targets(payload):
    from platforms_connectors.bridge import publish

    result = publish(payload, list(ADAPTERS_FOR_TEST))
    assert result["mode"] == "DRY_RUN"
    assert len(result["results"]) == len(ADAPTERS_FOR_TEST)


ADAPTERS_FOR_TEST = [p.lower() for p in PLATFORMS]


def test_live_paths_use_mocked_official_requests(monkeypatch, payload):
    """Every live adapter is exercised without credentials or network."""
    cases = {
        "Instagram": {
            "INSTAGRAM_USER_ID": "ig-user",
            "INSTAGRAM_ACCESS_TOKEN": "token",
        },
        "Facebook": {"FACEBOOK_PAGE_ID": "page", "FACEBOOK_PAGE_ACCESS_TOKEN": "token"},
        "Threads": {"THREADS_USER_ID": "thread-user", "THREADS_ACCESS_TOKEN": "token"},
        "X": {"X_ACCESS_TOKEN": "token"},
        "Reddit": {
            "REDDIT_ACCESS_TOKEN": "token",
            "REDDIT_USER_AGENT": "systemfehler-test/1.0",
            "REDDIT_SUBREDDIT": "test",
        },
        "LinkedIn": {
            "LINKEDIN_ACCESS_TOKEN": "token",
            "LINKEDIN_AUTHOR_URN": "urn:li:person:test",
        },
        "Pinterest": {"PINTEREST_ACCESS_TOKEN": "token", "PINTEREST_BOARD_ID": "board"},
        "Bluesky": {
            "BLUESKY_HANDLE": "handle.test",
            "BLUESKY_APP_PASSWORD": "app-password",
        },
        "Mastodon": {
            "MASTODON_ACCESS_TOKEN": "token",
            "MASTODON_BASE_URL": "https://mastodon.example",
        },
        "Telegram": {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"},
        "Discord": {"DISCORD_WEBHOOK_URL": "https://discord.example/webhook"},
    }
    for key, values in cases.items():
        for name, value in values.items():
            monkeypatch.setenv(name, value)
        module = importlib.import_module(f"platforms_connectors.{key}.publish")
        calls = []

        def fake_request(url, **kwargs):
            calls.append(url)
            if key == "Bluesky" and "createSession" in url:
                return {"did": "did:plc:test", "accessJwt": "jwt"}
            if key == "Reddit":
                return {"json": {"data": {"things": [{"data": {"name": "t3_test"}}]}}}
            if key == "Telegram":
                return {"ok": True, "result": {"message_id": 42}}
            if key == "LinkedIn":
                return {"_response_headers": {"x-restli-id": "urn:test"}}
            return {"id": "external-test", "uri": "at://test"}

        monkeypatch.setattr(module, "request_json", fake_request)
        result = module.publish(payload, dry_run=False)
        assert result["mode"] == "LIVE", key
        assert result["published"] is True, key
        assert calls, key
