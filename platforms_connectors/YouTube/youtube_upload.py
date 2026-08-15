#!/usr/bin/env python3
"""YouTube-Upload ueber die internen YouTube-Studio-Endpoints (Cookie-basiert).

Nachbau von adasq/youtube-studio (MIT, https://github.com/adasq/youtube-studio)
in Stdlib-Python, damit die Bridge (stdlib-only) den Live-Upload ohne
offizielle API und ohne Browser ausfuehren kann.

Sicherheitsmodell (fail-closed):
  - Privacy-Default: PRIVATE. Echte Veroeffentlichung nur mit --privacy PUBLIC/UNLISTED.
  - Cookies nur aus Datei (YOUTUBE_COOKIE_PATH), nie aus Env/Args/Logs.
  - Keine Cookie-Werte werden gedruckt.
"""

import hashlib
import json
import os
import time
import atexit
import subprocess
import tempfile
import urllib.request
import urllib.error
import uuid

YT_STUDIO_URL = "https://studio.youtube.com"
UPLOAD_URL = "https://upload.youtube.com/upload/studio"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
FORM_CT = "application/x-www-form-urlencoded;charset=utf-8"



def resolve_cookie_path(path):
    """Return an existing cookie file, materializing the migrated legacy source from SIN-Infisical when needed."""
    expanded = os.path.expanduser(path)
    if os.path.isfile(expanded):
        return expanded
    cli = os.environ.get("SIN_INFISICAL_BIN", os.path.expanduser("~/.local/bin/sin-infisical"))
    if not os.path.isfile(cli):
        raise SystemExit(f"FEHLER: Cookie-Datei fehlt und sin-infisical ist nicht verfügbar: {expanded}")
    fd, tmp = tempfile.mkstemp(prefix="sin-youtube-cookies-")
    os.close(fd)
    os.chmod(tmp, 0o600)
    proc = subprocess.run(
        [cli, "agent", "materialize", "--source", expanded, "--dest", tmp],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=False, timeout=30,
    )
    if proc.returncode != 0:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise SystemExit("FEHLER: YouTube-Cookies konnten nicht aus SIN-Infisical materialisiert werden")
    atexit.register(lambda: os.path.exists(tmp) and os.unlink(tmp))
    return tmp

def load_cookies(path):
    """Liest Cookies aus Netscape-cookies.txt ODER Chrome-JSON und liefert die Werte."""
    needed = {"SID", "HSID", "SSID", "APISID", "SAPISID"}
    optional = {"LOGIN_INFO", "VISITOR_INFO1_LIVE"}
    found = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        head = f.read(1)
        f.seek(0)
        if head == "[":
            import json as _json

            entries = _json.load(f)
            for e in entries:
                name = e.get("name")
                if name in needed or name in optional:
                    found[name] = e.get("value")
        else:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) != 7:
                    continue
                _, _, _, _, _, name, value = parts
                if name in needed or name in optional:
                    found[name] = value
    missing = needed - set(found)
    if missing:
        raise SystemExit(f"FEHLER: fehlende Cookies in {path}: {sorted(missing)}")
    return found


def sapisid_hash(date_ms, sapisid):
    base = f"{date_ms} {sapisid} {YT_STUDIO_URL}"
    return f"{date_ms}_{hashlib.sha1(base.encode()).hexdigest()}"


def _open(req, timeout=60):
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def fetch_config(cookies):
    """Studio-Hauptseite laden und ytcfg-Werte (Key, Visitor, Channel) extrahieren."""
    date_ms = str(int(time.time() * 1000))
    headers = {
        "authorization": f"SAPISIDHASH {sapisid_hash(date_ms, cookies['SAPISID'])}",
        "cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
        "x-origin": YT_STUDIO_URL,
        "user-agent": USER_AGENT,
    }
    req = urllib.request.Request(YT_STUDIO_URL, headers=headers)
    status, _, body = _open(req)
    if status != 200 or b"accounts.google.com" in body[:2000]:
        raise SystemExit(
            "FEHLER: Studio-Login nicht akzeptiert (Redirect/Status "
            f"{status}) - Cookies ungueltig?"
        )
    html = body.decode("utf-8", "replace")
    # ytcfg-Script finden: window["ytcfg"].set({...}) / ytcfg.set({...}) / ytcfg = {...}
    import re

    m = (
        re.search(r"ytcfg\.set\(\s*(\{.*?\})\s*\)", html, re.S)
        or re.search(r"ytcfg\s*=\s*(\{.*?\})", html, re.S)
        or re.search(r'\[?"ytcfg"\]?\.set\(\s*(\{.*?\})\s*\)', html, re.S)
    )
    if not m:
        raise SystemExit(
            "FEHLER: ytcfg nicht in Studio-Seite gefunden (Login ok, Parsing?)"
        )
    raw = m.group(1)
    # JSON-Block bis zur schliessenden Klammer ausbalancieren
    depth = 0
    end = 0
    in_str = False
    esc = False
    for i, ch in enumerate(raw):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
    data = json.loads(raw[:end])
    cfg = {
        "INNERTUBE_API_KEY": data.get("INNERTUBE_API_KEY"),
        "VISITOR_DATA": data.get("VISITOR_DATA"),
        "DELEGATED_SESSION_ID": data.get("DELEGATED_SESSION_ID"),
        "CHANNEL_ID": data.get("CHANNEL_ID"),
    }
    return cfg


def playwright_upload(
    cookies, video_path, title, description, privacy, is_draft, cookie_json_path
):
    """Upload ueber die internen Endpoints, ausgefuehrt im Playwright-Chromium
    (echter Browser-Fingerprint). Kein UI-Klicken, keine offizielle API."""
    from playwright.sync_api import sync_playwright
    import base64

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        raw = json.load(open(cookie_json_path))
        pw_cookies = []
        for c in raw:
            if not c.get("value"):
                continue
            ss = {
                "no_restriction": "None",
                "None": "None",
                "lax": "Lax",
                "strict": "Strict",
            }.get(c.get("sameSite"), "Lax")
            entry = {
                "name": c["name"],
                "value": c["value"],
                "domain": c["domain"],
                "path": c.get("path", "/"),
                "secure": bool(c.get("secure")),
                "httpOnly": bool(c.get("httpOnly")),
                "sameSite": ss,
            }
            if c.get("expirationDate"):
                entry["expires"] = c["expirationDate"]
            pw_cookies.append(entry)
        ctx.add_cookies(pw_cookies)
        page = ctx.new_page()

        # Session validieren (Kanalauswahl-Prompt wird uebersprungen)
        page.goto(
            "https://www.youtube.com/", timeout=60000, wait_until="domcontentloaded"
        )
        page.wait_for_timeout(3000)
        page.goto(
            "https://studio.youtube.com/", timeout=60000, wait_until="domcontentloaded"
        )
        page.wait_for_timeout(4000)
        if "accounts.google.com" in page.url or "signin_prompt" in page.url:
            raise SystemExit(
                "FEHLER: Login nicht akzeptiert (signin_prompt) - "
                "Kanalauswahl nicht bestaetigt"
            )

        # ytcfg von www.youtube.com holen (Studio-SPA liefert es nicht im DOM)
        page.goto(
            "https://www.youtube.com/", timeout=60000, wait_until="domcontentloaded"
        )
        page.wait_for_timeout(4000)
        cfg = page.evaluate("""() => {
            const d = (window.ytcfg && window.ytcfg.data_) || {};
            return {
                INNERTUBE_API_KEY: d.INNERTUBE_API_KEY || '',
                VISITOR_DATA: d.VISITOR_DATA || '',
                DELEGATED_SESSION_ID: d.DELEGATED_SESSION_ID || '',
                CHANNEL_ID: d.CHANNEL_ID || '',
            };
        }""")
        if not cfg.get("INNERTUBE_API_KEY"):
            raise SystemExit("FEHLER: ytcfg unvollstaendig: " + str(cfg))
        if not cfg.get("CHANNEL_ID"):
            # Kanal-Id aus der oeffentlichen Kanalseite lesen
            try:
                page.goto(
                    "https://www.youtube.com/@Systemfehler_nach_DIN",
                    timeout=60000,
                    wait_until="domcontentloaded",
                )
                page.wait_for_timeout(4000)
                cid = page.evaluate(
                    "() => (document.querySelector('meta[itemprop=\"identifier\"]')"
                    "|| {}).content || ''"
                )
                cfg["CHANNEL_ID"] = cid or ""
            except Exception:
                pass
        if not cfg.get("CHANNEL_ID"):
            raise SystemExit("FEHLER: CHANNEL_ID nicht ermittelbar")

        # Datei im Browser-Kontext bereitstellen
        page.evaluate("""() => { window.__up = {}; }""")
        page.set_input_files('input[type="file"]', video_path) if False else None
        # Datei als ArrayBuffer in den Page-Kontext laden
        file_b64 = base64.b64encode(open(video_path, "rb").read()).decode()
        page.evaluate(
            """(b64) => {
            const bin = atob(b64);
            const bytes = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
            window.__up.file = new Blob([bytes]);
        }""",
            file_b64,
        )

        # 1) Resumable-Session starten
        date_ms = str(int(time.time() * 1000))
        auth = f"SAPISIDHASH {sapisid_hash(date_ms, cookies['SAPISID'])}"
        file_name = "file-" + str(int(time.time() * 1000))
        frontend_upload_id = f"innertube_studio:{uuid.uuid4()}:0"
        start_js = f"""async () => {{
            const res = await fetch("https://upload.youtube.com/upload/studio", {{
                method: "POST",
                headers: {{
                    "authorization": {json.dumps(auth)},
                    "content-type": "application/x-www-form-urlencoded;charset=utf-8",
                    "x-goog-upload-command": "start",
                    "x-goog-upload-file-name": {json.dumps(file_name)},
                    "x-goog-upload-protocol": "resumable",
                    "x-origin": "https://studio.youtube.com",
                }},
                body: JSON.stringify({{frontendUploadId: {json.dumps(frontend_upload_id)}}}),
                credentials: "include"
            }});
            return {{status: res.status, url: res.headers.get("x-goog-upload-url")}};
        }}"""
        start = page.evaluate(start_js)
        if start["status"] != 200 or not start["url"]:
            raise SystemExit(f"FEHLER: Upload-Start ({start['status']})")

        # 2) Datei hochladen (upload, finalize)
        upload_js = f"""async () => {{
            const res = await fetch({json.dumps(start["url"])}, {{
                method: "POST",
                headers: {{
                    "content-type": "application/x-www-form-urlencoded;charset=utf-8",
                    "x-goog-upload-command": "upload, finalize",
                    "x-goog-upload-file-name": {json.dumps(file_name)},
                    "x-goog-upload-offset": "0",
                    "referrer": "https://studio.youtube.com",
                }},
                body: window.__up.file,
                credentials: "include"
            }});
            const body = await res.json();
            return {{status: res.status, scotty: body.scottyResourceId}};
        }}"""
        up = page.evaluate(upload_js)
        if up["status"] != 200 or not up.get("scotty"):
            raise SystemExit(f"FEHLER: Datei-Upload ({up['status']})")

        # 3) Video-Metadaten erstellen (createvideo)
        create_body = {
            "channelId": cfg["CHANNEL_ID"],
            "resourceId": {"scottyResourceId": {"id": up["scotty"]}},
            "frontendUploadId": frontend_upload_id,
            "initialMetadata": {
                "title": {"newTitle": title},
                "description": {"newDescription": description, "shouldSegment": True},
                "privacy": {"newPrivacy": privacy},
                "draftState": {"isDraft": is_draft},
            },
            "context": {
                "client": {
                    "clientName": 62,
                    "clientVersion": "1.20201130.03.00",
                    "hl": "en-GB",
                    "gl": "PL",
                    "experimentsToken": "",
                    "utcOffsetMinutes": 60,
                },
                "request": {
                    "returnLogEntry": True,
                    "internalExperimentFlags": [],
                    "sessionInfo": {"token": ""},
                },
                "user": {
                    "onBehalfOfUser": cfg.get("DELEGATED_SESSION_ID") or "",
                    "delegationContext": {
                        "roleType": {
                            "channelRoleType": "CREATOR_CHANNEL_ROLE_TYPE_OWNER"
                        },
                        "externalChannelId": cfg["CHANNEL_ID"],
                    },
                    "serializedDelegationContext": "",
                },
                "clientScreenNonce": "",
            },
            "delegationContext": {
                "roleType": {"channelRoleType": "CREATOR_CHANNEL_ROLE_TYPE_OWNER"},
                "externalChannelId": cfg["CHANNEL_ID"],
            },
        }
        # createvideo muss mit Origin studio.youtube.com laufen
        page.goto(
            "https://studio.youtube.com/", timeout=60000, wait_until="domcontentloaded"
        )
        page.wait_for_timeout(4000)
        create_js = f"""async () => {{
            const res = await fetch(
                "https://studio.youtube.com/youtubei/v1/upload/createvideo?alt=json&key={cfg["INNERTUBE_API_KEY"]}",
                {{
                    method: "POST",
                    headers: {{
                        "authorization": {json.dumps(auth)},
                        "content-type": "application/json",
                        "x-origin": "https://studio.youtube.com",
                    }},
                    body: JSON.stringify({json.dumps(create_body)}),
                    credentials: "include"
                }});
            const body = await res.json();
            return {{status: res.status, body: body}};
        }}"""
        result = page.evaluate(create_js)
        browser.close()
        if result["status"] != 200 or "videoId" not in result["body"]:
            raise SystemExit(
                f"FEHLER: createvideo ({result['status']}): "
                f"{json.dumps(result['body'])[:400]}"
            )
        return result["body"]


def upload_video(cookies, cfg, video_path, title, description, privacy, is_draft):
    date_ms = str(int(time.time() * 1000))
    base_headers = {
        "authorization": f"SAPISIDHASH {sapisid_hash(date_ms, cookies['SAPISID'])}",
        "cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
        "x-origin": YT_STUDIO_URL,
        "user-agent": USER_AGENT,
        "referrer": YT_STUDIO_URL,
    }
    frontend_upload_id = f"innertube_studio:{uuid.uuid4()}:0"
    file_name = "file-" + str(int(time.time() * 1000))

    # 1) Resumable-Session starten
    start_headers = dict(base_headers)
    start_headers.update(
        {
            "content-type": FORM_CT,
            "x-goog-upload-command": "start",
            "x-goog-upload-file-name": file_name,
            "x-goog-upload-protocol": "resumable",
        }
    )
    req = urllib.request.Request(
        UPLOAD_URL,
        method="POST",
        headers=start_headers,
        data=json.dumps({"frontendUploadId": frontend_upload_id}).encode(),
    )
    status, hdrs, body = _open(req)
    upload_url = hdrs.get("x-goog-upload-url")
    if status != 200 or not upload_url:
        raise SystemExit(
            f"FEHLER: Upload-Start fehlgeschlagen ({status}): "
            f"{body.decode('utf-8', 'replace')[:300]}"
        )

    # 2) Datei hochladen (upload, finalize)
    with open(video_path, "rb") as f:
        video_bytes = f.read()
    up_headers = dict(base_headers)
    up_headers.update(
        {
            "content-type": FORM_CT,
            "x-goog-upload-command": "upload, finalize",
            "x-goog-upload-file-name": file_name,
            "x-goog-upload-offset": "0",
        }
    )
    req = urllib.request.Request(
        upload_url, method="POST", headers=up_headers, data=video_bytes
    )
    status, _, body = _open(req, timeout=600)
    scotty = json.loads(body.decode("utf-8", "replace")).get("scottyResourceId")
    if not scotty:
        raise SystemExit(
            f"FEHLER: Datei-Upload fehlgeschlagen ({status}): "
            f"{body.decode('utf-8', 'replace')[:300]}"
        )

    # 3) Video-Metadaten erstellen
    create_body = {
        "channelId": cfg["CHANNEL_ID"],
        "resourceId": {"scottyResourceId": {"id": scotty}},
        "frontendUploadId": frontend_upload_id,
        "initialMetadata": {
            "title": {"newTitle": title},
            "description": {"newDescription": description, "shouldSegment": True},
            "privacy": {"newPrivacy": privacy},
            "draftState": {"isDraft": is_draft},
        },
        "context": {
            "client": {
                "clientName": 62,
                "clientVersion": "1.20201130.03.00",
                "hl": "en-GB",
                "gl": "PL",
                "experimentsToken": "",
                "utcOffsetMinutes": 60,
            },
            "request": {
                "returnLogEntry": True,
                "internalExperimentFlags": [],
                "sessionInfo": {"token": ""},
            },
            "user": {
                "onBehalfOfUser": cfg.get("DELEGATED_SESSION_ID") or "",
                "delegationContext": {
                    "roleType": {"channelRoleType": "CREATOR_CHANNEL_ROLE_TYPE_OWNER"},
                    "externalChannelId": cfg["CHANNEL_ID"],
                },
                "serializedDelegationContext": "",
            },
            "clientScreenNonce": "",
        },
        "delegationContext": {
            "roleType": {"channelRoleType": "CREATOR_CHANNEL_ROLE_TYPE_OWNER"},
            "externalChannelId": cfg["CHANNEL_ID"],
        },
    }
    url = f"{YT_STUDIO_URL}/youtubei/v1/upload/createvideo?alt=json&key={cfg['INNERTUBE_API_KEY']}"
    req = urllib.request.Request(
        url, method="POST", headers=base_headers, data=json.dumps(create_body).encode()
    )
    status, _, body = _open(req)
    result = json.loads(body.decode("utf-8", "replace"))
    if status != 200 or "videoId" not in result:
        raise SystemExit(
            f"FEHLER: createvideo fehlgeschlagen ({status}): "
            f"{body.decode('utf-8', 'replace')[:400]}"
        )
    return result


def main():
    import argparse

    ap = argparse.ArgumentParser(description="YouTube-Upload (Cookie-basiert, intern)")
    ap.add_argument("--video", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--description", default="")
    ap.add_argument(
        "--privacy", default="PRIVATE", choices=["PRIVATE", "UNLISTED", "PUBLIC"]
    )
    ap.add_argument("--draft", action="store_true", help="als Entwurf speichern")
    ap.add_argument(
        "--cookies",
        default=os.environ.get(
            "YOUTUBE_COOKIE_PATH",
            os.path.expanduser("~/.config/sin-youtube/cookies.txt"),
        ),
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="nur Login+Config pruefen, kein Upload"
    )
    ap.add_argument(
        "--transport",
        default="playwright",
        choices=["playwright", "urllib"],
        help="Transport: playwright (Browser-Fingerprint, empfohlen) "
        "oder urllib (reiner HTTP)",
    )
    args = ap.parse_args()
    args.cookies = resolve_cookie_path(args.cookies)

    cookies = load_cookies(args.cookies)
    if args.transport == "playwright":
        print("Login-Check via Playwright (Browser-Fingerprint)...")
        cfg = None  # Config kommt aus dem Browser-Kontext
        if args.dry_run:
            # Nur Session-Gueltigkeit pruefen
            _pw_check(cookies, args.cookies)
            print("Dry-run: Login OK, kein Upload ausgefuehrt.")
            return
        result = playwright_upload(
            cookies,
            args.video,
            args.title,
            args.description,
            args.privacy,
            args.draft,
            args.cookies,
        )
        print(
            f"Upload OK: videoId={result.get('videoId')}  "
            f"status={result.get('status')}  privacy={args.privacy}"
        )
    else:
        cfg = fetch_config(cookies)
        print(
            f"Login OK - ChannelId: {cfg['CHANNEL_ID']}  "
            f"(DelegatedSession: {'ja' if cfg.get('DELEGATED_SESSION_ID') else 'nein'})"
        )
        if args.dry_run:
            print("Dry-run: kein Upload ausgefuehrt.")
            return
        result = upload_video(
            cookies,
            cfg,
            args.video,
            args.title,
            args.description,
            args.privacy,
            args.draft,
        )
        print(
            f"Upload OK: videoId={result.get('videoId')}  "
            f"status={result.get('status')}  privacy={args.privacy}"
        )
    if args.privacy != "PRIVATE":
        print(
            "HINWEIS: Video ist NICHT privat - sichtbar fuer "
            f"{'alle' if args.privacy == 'PUBLIC' else 'jeden mit Link'}!"
        )


def _pw_check(cookies, cookie_json_path):
    """Nur pruefen, ob die Cookies im Browser-Kontext eingeloggt sind."""
    from playwright.sync_api import sync_playwright
    import json as _json

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        raw = _json.load(open(cookie_json_path))
        for c in raw:
            if not c.get("value"):
                continue
            ss = {
                "no_restriction": "None",
                "None": "None",
                "lax": "Lax",
                "strict": "Strict",
            }.get(c.get("sameSite"), "Lax")
            entry = {
                "name": c["name"],
                "value": c["value"],
                "domain": c["domain"],
                "path": c.get("path", "/"),
                "secure": bool(c.get("secure")),
                "httpOnly": bool(c.get("httpOnly")),
                "sameSite": ss,
            }
            if c.get("expirationDate"):
                entry["expires"] = c["expirationDate"]
            ctx.add_cookies([entry])
        page = ctx.new_page()
        page.goto(
            "https://www.youtube.com/", timeout=60000, wait_until="domcontentloaded"
        )
        page.wait_for_timeout(2500)
        page.goto(
            "https://studio.youtube.com/", timeout=60000, wait_until="domcontentloaded"
        )
        page.wait_for_timeout(3000)
        ok = "accounts.google.com" not in page.url and "signin_prompt" not in page.url
        browser.close()
        if not ok:
            raise SystemExit("FEHLER: Login nicht akzeptiert: " + page.url)


if __name__ == "__main__":
    main()
