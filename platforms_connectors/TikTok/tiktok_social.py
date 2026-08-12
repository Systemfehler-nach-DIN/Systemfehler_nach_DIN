#!/usr/bin/env python3
"""Fail-closed TikTok Studio publisher through SIN-Browser-Use."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


class TikTokError(RuntimeError):
    """TikTok UI preflight, publish, or verification failure."""


def browser_command() -> str:
    configured = os.getenv("SIN_BROWSER_USE_BIN")
    if configured:
        return configured
    found = shutil.which("sin-browser-use")
    if found:
        return found
    candidate = Path.home() / ".local" / "bin" / "sin-browser-use"
    if candidate.is_file():
        return str(candidate)
    raise TikTokError("SIN-Browser-Use-Wrapper nicht gefunden")


def publish_video(
    video_path: str,
    description: str,
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    path = Path(video_path).expanduser()
    if not path.is_file():
        raise TikTokError(f"TikTok-Videodatei nicht gefunden: {path}")
    if dry_run:
        return {"ok": True, "mode": "DRY_RUN", "video_path": str(path), "description_length": len(description)}
    if any(os.getenv(k, "").lower() != "true" for k in ("ALLOW_REAL_POSTS", "TIKTOK_BROWSER_LIVE_APPROVED")) or os.getenv("PUBLISH_MODE", "DRY_RUN").upper() != "LIVE":
        raise TikTokError("TikTok-LIVE ist nicht explizit freigegeben")
    command = browser_command()
    url = "https://www.tiktok.com/tiktokstudio/upload"
    script = "\n".join([
        "import json, time",
        f"target = new_tab({json.dumps(url)})",
        "wait_for_load()",
        "time.sleep(3)",
        "if 'login' in page_info().get('url', '').lower():",
        "    close_tab(target)",
        "    raise RuntimeError('TikTok-Session ist nicht angemeldet')",
        f"upload_file('input[type=file]', {json.dumps(str(path))})",
        "time.sleep(5)",
        "editor = js('Boolean(document.querySelector(\"[contenteditable=true]\"))')",
        "if not editor:",
        "    close_tab(target)",
        "    raise RuntimeError('TikTok-Beschreibungsfeld nicht gefunden')",
        f"filled = js({json.dumps("(()=>{let e=document.querySelector('[contenteditable=true]'); if(!e)return false; e.focus(); e.innerText=" + json.dumps(description, ensure_ascii=False) + "; e.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText'})); return true;})()", ensure_ascii=False)})",
        "if not filled:",
        "    close_tab(target)",
        "    raise RuntimeError('TikTok-Beschreibung konnte nicht gesetzt werden')",
        f"published = js({json.dumps("(()=>{let e=[...document.querySelectorAll('button')].find(e=>(e.innerText||'').trim()==='Veröffentlichen'); if(!e)return false; e.click(); return true})()")})",
        "if not published:",
        "    close_tab(target)",
        "    raise RuntimeError('TikTok-Veröffentlichen-Schaltfläche nicht gefunden')",
        "time.sleep(8)",
        "info = page_info()",
        "body = js('document.body.innerText') or ''",
        "if '/tiktokstudio/content' not in info.get('url', '') or 'Inhalt' not in body:",
        "    close_tab(target)",
        "    raise RuntimeError('TikTok-Publish konnte nicht verifiziert werden')",
        "print(json.dumps({'ok': True, 'url': info.get('url', ''), 'description_length': len(" + json.dumps(description) + ")}))",
        "close_tab(target)",
    ])
    result = subprocess.run([command], input=script, text=True, capture_output=True, timeout=180, check=False)
    if result.returncode:
        raise TikTokError((result.stderr.strip() or result.stdout.strip())[-1200:] or "TikTok-Publish fehlgeschlagen")
    return {"ok": True, "mode": "LIVE", "url": "https://www.tiktok.com/tiktokstudio/content", "description_length": len(description)}
