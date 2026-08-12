#!/usr/bin/env python3
"""Fail-closed Browser Use CLI fallback for YouTube Community/Studio gaps.

The official Data API does not expose creating Community posts. Browser Use CLI
3.0 is the default worker through the authenticated SIN-Chrome bot profile;
legacy storage-state Playwright is retained only as an explicit backend. This
module never bypasses CAPTCHA/2FA/consent or clicks publish without approval.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


class YouTubeBrowserError(RuntimeError):
    pass


class CommunityBrowser:
    def __init__(
        self,
        channel_id: str,
        storage_state: str | None = None,
        cookie_json: str | None = None,
        headless: bool = False,
        backend: str | None = None,
    ):
        self.channel_id = channel_id
        self.storage_state = storage_state or os.getenv("YOUTUBE_STORAGE_STATE")
        self.cookie_json = cookie_json or os.getenv("YOUTUBE_COOKIE_PATH")
        self.headless = headless
        self.backend = backend or os.getenv("SIN_YOUTUBE_BROWSER_BACKEND", "browser-use")

    def _context(self, playwright: Any) -> tuple[Any, Any]:
        if not self.storage_state and not self.cookie_json:
            raise YouTubeBrowserError(
                "YOUTUBE_STORAGE_STATE oder YOUTUBE_COOKIE_PATH erforderlich"
            )
        browser = playwright.chromium.launch(headless=self.headless)
        if self.storage_state:
            context = browser.new_context(
                storage_state=str(Path(self.storage_state).expanduser())
            )
        else:
            try:
                raw = json.loads(
                    Path(self.cookie_json).expanduser().read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError) as exc:
                browser.close()
                raise YouTubeBrowserError("Cookie-Datei nicht lesbar") from exc
            if not isinstance(raw, list):
                browser.close()
                raise YouTubeBrowserError("Cookie-JSON muss eine Liste sein")
            context = browser.new_context()
            context.add_cookies(
                [
                    {
                        "name": c["name"],
                        "value": c["value"],
                        "domain": c["domain"],
                        "path": c.get("path", "/"),
                        "secure": bool(c.get("secure")),
                        "httpOnly": bool(c.get("httpOnly")),
                    }
                    for c in raw
                    if c.get("name") and c.get("value") and c.get("domain")
                ]
            )
        return browser, context

    @staticmethod
    def _first_visible(page: Any, selectors: list[str]) -> Any:
        for selector in selectors:
            locator = page.locator(selector)
            if locator.count() and locator.first.is_visible():
                return locator.first
        return None

    @staticmethod
    def _browser_use_command() -> str:
        configured = os.getenv("SIN_BROWSER_USE_BIN")
        if configured:
            return configured
        found = shutil.which("sin-browser-use")
        if found:
            return found
        candidate = Path.home() / "dev" / "wow-my-zsh" / "integrations" / "browser-use-cli" / "bin" / "sin-browser-use"
        if candidate.is_file():
            return str(candidate)
        raise YouTubeBrowserError("SIN-Browser-Use-Wrapper nicht gefunden")

    def _create_post_browser_use(self, text: str) -> dict[str, Any]:
        """Run the live fallback through the persistent Browser Use CLI worker."""
        url = f"https://www.youtube.com/channel/{self.channel_id}/community"
        click_js = """(() => { const xs=[...document.querySelectorAll('button,[role="button"]')]; const x=xs.find(e=>/create a post|beitrag erstellen|post erstellen/i.test((e.innerText||e.getAttribute('aria-label')||'').trim())); if(!x) return false; x.click(); return true; })()"""
        fill_js = """(value => { const x=document.querySelector('textarea,[contenteditable="true"],[role="textbox"]'); if(!x) return false; if(x.tagName==='TEXTAREA') x.value=value; else x.textContent=value; x.dispatchEvent(new InputEvent('input',{bubbles:true,data:value,inputType:'insertText'})); return true; })"""
        fill_expr = f"({fill_js})({json.dumps(text, ensure_ascii=False)})"
        publish_js = """(() => { const xs=[...document.querySelectorAll('button,[role=\"button\"]')]; const x=xs.find(e=>/^(post|beitrag)$/i.test((e.innerText||e.getAttribute('aria-label')||'').trim())); if(!x) return false; x.click(); return true; })()"""
        script = "\n".join([
            "import json",
            f"text = {json.dumps(text, ensure_ascii=False)}",
            f"target = new_tab({json.dumps(url)})",
            "wait_for_load()",
            "info = page_info()",
            "body = js('document.body.innerText') or ''",
            "if 'accounts.google.com' in info.get('url', '') or 'Anmelden' in body[:2000]:",
            "    close_tab(target)",
            "    raise RuntimeError('Browser-Session ist nicht angemeldet')",
            f"opened = js({json.dumps(click_js)})",
            "if not opened:",
            "    close_tab(target)",
            "    raise RuntimeError('Community-Post-Schaltfläche nicht eindeutig gefunden')",
            "wait_for_load()",
            f"filled = js({json.dumps(fill_expr, ensure_ascii=False)})",
            "if not filled:",
            "    close_tab(target)",
            "    raise RuntimeError('Community-Textfeld nicht eindeutig gefunden')",
            f"published = js({json.dumps(publish_js)})",
            "if not published:",
            "    close_tab(target)",
            "    raise RuntimeError('Publish-Schaltfläche nicht eindeutig gefunden')",
            "wait_for_load()",
            "print(json.dumps({'ok': True, 'url': page_info().get('url', ''), 'text_length': len(text)}))",
            "close_tab(target)",
        ])
        try:
            completed = subprocess.run([self._browser_use_command()], input=script, text=True, capture_output=True, timeout=120, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            raise YouTubeBrowserError("SIN-Browser-Use konnte nicht gestartet werden") from exc
        if completed.returncode:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise YouTubeBrowserError(detail[-1000:] or "Browser Use Community-Aktion fehlgeschlagen")
        return {"ok": True, "mode": "LIVE", "channel_id": self.channel_id, "url": url, "text_length": len(text)}

    def create_post(self, text: str, dry_run: bool = True) -> dict[str, Any]:
        if not text.strip():
            raise YouTubeBrowserError("Community-Post darf nicht leer sein")
        url = f"https://www.youtube.com/channel/{self.channel_id}/community"
        if dry_run:
            return {
                "ok": True,
                "mode": "DRY_RUN",
                "would_open": url,
                "text_length": len(text),
            }
        if self.backend == "browser-use":
            if (
                os.getenv("PUBLISH_MODE", "DRY_RUN").upper() != "LIVE"
                or os.getenv("ALLOW_REAL_POSTS", "false").lower() != "true"
                or os.getenv("YOUTUBE_BROWSER_LIVE_APPROVED", "false").lower() != "true"
            ):
                raise YouTubeBrowserError("Browser Use Community-LIVE ist nicht explizit freigegeben")
            return self._create_post_browser_use(text)
        if self.backend not in {"playwright", "legacy"}:
            raise YouTubeBrowserError(f"Unbekanntes Browser-Backend: {self.backend}")
        if (
            os.getenv("PUBLISH_MODE", "DRY_RUN").upper() != "LIVE"
            or os.getenv("ALLOW_REAL_POSTS", "false").lower() != "true"
            or os.getenv("YOUTUBE_BROWSER_LIVE_APPROVED", "false").lower() != "true"
        ):
            raise YouTubeBrowserError(
                "Browser-Community-LIVE ist nicht explizit freigegeben"
            )
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise YouTubeBrowserError(
                "Playwright ist für den Browser-Fallback erforderlich"
            ) from exc
        with sync_playwright() as playwright:
            browser, context = self._context(playwright)
            try:
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2500)
                if "accounts.google.com" in page.url:
                    raise YouTubeBrowserError("Browser-Session ist nicht angemeldet")
                create = self._first_visible(
                    page,
                    [
                        'button:has-text("Create a post")',
                        'button:has-text("Beitrag erstellen")',
                        '[role="button"]:has-text("Create a post")',
                        '[role="button"]:has-text("Beitrag erstellen")',
                    ],
                )
                if not create:
                    raise YouTubeBrowserError(
                        "Community-Post-Schaltfläche nicht eindeutig gefunden"
                    )
                create.click()
                page.wait_for_timeout(500)
                box = self._first_visible(
                    page,
                    [
                        "textarea",
                        '[contenteditable="true"]',
                        '[role="textbox"]',
                    ],
                )
                if not box:
                    raise YouTubeBrowserError(
                        "Community-Textfeld nicht eindeutig gefunden"
                    )
                box.fill(text)
                post = self._first_visible(
                    page,
                    [
                        'button:has-text("Post")',
                        'button:has-text("Beitrag")',
                        '[role="button"]:has-text("Post")',
                        '[role="button"]:has-text("Beitrag")',
                    ],
                )
                if not post:
                    raise YouTubeBrowserError(
                        "Post-Schaltfläche nicht eindeutig gefunden"
                    )
                post.click()
                page.wait_for_timeout(1500)
                return {
                    "ok": True,
                    "mode": "LIVE",
                    "channel_id": self.channel_id,
                    "url": page.url,
                    "text_length": len(text),
                }
            finally:
                browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SIN-YouTube Community-Browser-Fallback"
    )
    parser.add_argument("--channel-id", required=True)
    parser.add_argument("--storage-state")
    parser.add_argument("--cookie-json")
    parser.add_argument("--post")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--backend", choices=("browser-use", "playwright", "legacy"), default="browser-use")
    args = parser.parse_args()
    if not args.post:
        parser.error("--post erforderlich")
    try:
        browser = CommunityBrowser(
            args.channel_id, args.storage_state, args.cookie_json, backend=args.backend
        )
        result = browser.create_post(args.post, dry_run=not args.live or args.dry_run)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except YouTubeBrowserError as exc:
        print(f"FEHLER: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
