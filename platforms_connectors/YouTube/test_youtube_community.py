from platforms_connectors.YouTube.youtube_community import CommunityBrowser


def test_browser_use_is_default_backend(monkeypatch):
    monkeypatch.delenv("SIN_YOUTUBE_BROWSER_BACKEND", raising=False)
    browser = CommunityBrowser("UCBWRl7VXRdy0kcsoV7or7Uw")
    assert browser.backend == "browser-use"


def test_dry_run_is_fail_closed_and_backend_agnostic():
    result = CommunityBrowser("UCBWRl7VXRdy0kcsoV7or7Uw").create_post("Willkommen", dry_run=True)
    assert result["mode"] == "DRY_RUN"
    assert result["would_open"].endswith("/community")
