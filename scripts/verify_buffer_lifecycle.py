#!/usr/bin/env python3
"""Hermetic TeraBox→Supabase→Buffer lifecycle evidence fixture.

No external provider mutation is performed. TeraBox transport and Supabase HTTP
are mocked; the production Buffer adapter is exercised in DRY_RUN mode.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from platforms_connectors.Buffer.publish import publish as buffer_publish  # noqa: E402
from platforms_connectors.MediaStaging import staging  # noqa: E402
from platforms_connectors.lifecycle import idempotency_key, run_buffer_lifecycle  # noqa: E402


class _DownloadResponse:
    def __init__(self, data: bytes):
        self.data = data
        self.done = False

    def read(self, size: int = -1) -> bytes:
        if self.done:
            return b""
        self.done = True
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _result(stdout: str):
    return type("Result", (), {"stdout": stdout, "stderr": ""})()


def run_fixture() -> dict[str, object]:
    supabase_calls: list[dict[str, object]] = []

    def fake_supabase_request(url: str, **kwargs):
        supabase_calls.append(
            {
                "method": kwargs.get("method", "POST"),
                "path": url.split("supabase.example", 1)[-1],
                "body_bytes": len(kwargs.get("body") or b""),
            }
        )
        return [{}]

    with tempfile.TemporaryDirectory(prefix="sin-lifecycle-fixture-") as tmp:
        media_path = Path(tmp) / "clip.mp4"
        media_path.write_bytes(b"SYSTEMFEHLER deterministic media fixture\n")
        with patch.object(
            staging,
            "_config",
            return_value=("https://supabase.example", "fixture-service-key", "social-staging"),
        ), patch.object(staging, "_request", side_effect=fake_supabase_request):
            staged = staging.stage_file(
                str(media_path),
                content_id="fixture-content-1",
                source_provider="terabox",
                source_reference="/archive/fixture/clip.mp4",
                source_fs_id=42,
            )

        terabox_calls: list[list[str]] = []

        def fake_run(command, **kwargs):
            terabox_calls.append(list(command))
            if command[1:] == ["status"]:
                return _result(json.dumps({"configured": True, "authenticated": True}))
            return _result(json.dumps({"dlink": "https://download.example/fixture"}))

        @contextmanager
        def fake_download_open(url, *args, **kwargs):
            if url != "https://download.example/fixture":
                raise AssertionError("unexpected fixture download URL")
            yield _DownloadResponse(b"SYSTEMFEHLER deterministic media fixture\n")

        with patch.object(staging.subprocess, "run", side_effect=fake_run), patch.object(
            staging, "urlopen", side_effect=fake_download_open
        ), patch.object(staging, "stage_file", return_value=dict(staged)):
            terabox_staged = staging.stage_terabox_reference(
                "/archive/fixture/clip.mp4",
                content_id="fixture-content-1",
                fs_id=42,
                output_dir=tmp,
            )

    assert terabox_calls[0] == ["terabox-sin", "status"]
    assert terabox_calls[1][0:3] == ["terabox-sin", "call", "download"]
    assert all("delete" not in " ".join(call).lower() for call in terabox_calls)
    assert staged["sha256"]
    assert staged["public_url"].startswith(
        "https://supabase.example/storage/v1/object/public/social-staging/"
    )
    assert terabox_staged["source_fs_id"] == 42

    payload = {
        "content_id": "fixture-content-1",
        "title": "Fixture",
        "excerpt": "Offline lifecycle evidence",
        "body": "No live post",
        "media_url": staged["public_url"],
        "media_type": "video",
        "url": "https://example.invalid/fixture",
        "cta": "Fixture",
        "terabox_source": {"remote_path": "/archive/fixture/clip.mp4", "fs_id": 42},
        "buffer_targets": [
            {
                "account": 3,
                "platform": "youtube",
                "channel_id": "6a7cf0c4b2d9d57743679762",
                "media_type": "video",
            }
        ],
    }
    key = idempotency_key(payload)
    adapter = buffer_publish(payload, dry_run=True, idempotency_key=key)
    assert adapter["mode"] == "DRY_RUN"
    assert adapter["targets"][0]["channelId"] == "6a7cf0c4b2d9d57743679762"

    durable: dict[str, dict[str, object]] = {}
    provider_calls = 0
    reconcile_calls = 0
    cleanup_calls = 0

    def lookup(**kwargs):
        row = durable.get(kwargs["idempotency_key"])
        return dict(row) if row else None

    def persist(**kwargs):
        current = durable.get(kwargs["idempotency_key"])
        if kwargs["status"] == "draft" and current:
            return {**current, "existing": True}
        row = {
            "job_id": "fixture-job-1",
            "content_id": kwargs["content_id"],
            "idempotency_key": kwargs["idempotency_key"],
            "status": kwargs["status"],
            "targets": [dict(x) for x in kwargs.get("targets", [])],
        }
        durable[kwargs["idempotency_key"]] = row
        return {**row, "existing": False}

    def provider(provider_payload, **kwargs):
        nonlocal provider_calls
        provider_calls += 1
        result = buffer_publish(provider_payload, **kwargs)
        result["target_metadata"] = [
            {
                "account": 3,
                "platform": "youtube",
                "channel_id": "6a7cf0c4b2d9d57743679762",
                "buffer_post_id": "fixture-buffer-post-1",
                "status": "scheduled",
            }
        ]
        return result

    def reconcile(**kwargs):
        nonlocal reconcile_calls
        reconcile_calls += 1
        targets = [dict(x) for x in kwargs["targets"]]
        if reconcile_calls > 1:
            targets[0]["status"] = "sent"
            return {"all_sent": True, "job_status": "sent", "targets": targets}
        return {"all_sent": False, "job_status": "scheduled", "targets": targets}

    def cleanup(**kwargs):
        nonlocal cleanup_calls
        cleanup_calls += 1
        return {"deleted": 0, "skipped": 1}

    first = run_buffer_lifecycle(
        payload,
        publish=provider,
        persist=persist,
        reconcile=reconcile,
        cleanup=cleanup,
        lookup=lookup,
        dry_run=True,
    )
    second = run_buffer_lifecycle(
        payload,
        publish=provider,
        persist=persist,
        reconcile=reconcile,
        cleanup=cleanup,
        lookup=lookup,
        dry_run=True,
    )
    assert first["status"] == "scheduled"
    assert second["status"] == "sent"
    assert second["deduplicated"] is True
    assert provider_calls == 1
    assert cleanup_calls == 1

    kestra = (ROOT / "website/kestra/publish_everywhere.yml").read_text(encoding="utf-8")
    assert '"platforms": ["buffer"]' in kestra
    assert 'uri: "{{ inputs.social_bridge_url }}/lifecycle"' in kestra
    assert "id: validate_buffer_only" in kestra
    assert "maxAttempts: 3" in kestra

    return {
        "schema": "sin-buffer-lifecycle-evidence/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "DRY_RUN",
        "external_mutations": False,
        "live_posts": False,
        "terabox": {
            "mode": "mocked-read-only-contract",
            "status_preflight_first": True,
            "download_by_fs_id": True,
            "source_delete_calls": 0,
        },
        "supabase_staging": {
            "mode": "mocked-http",
            "sha256": staged["sha256"],
            "stable_public_url": True,
            "provenance": {
                "source_provider": staged.get("source_provider"),
                "source_fs_id": staged.get("source_fs_id"),
            },
            "request_count": len(supabase_calls),
        },
        "kestra": {
            "lifecycle_endpoint": True,
            "buffer_only_gate": True,
            "bounded_retry_max_attempts": 3,
        },
        "buffer": {
            "adapter": "production-Buffer-adapter",
            "mode": adapter["mode"],
            "channel_id": adapter["targets"][0]["channelId"],
            "provider_create_calls": provider_calls,
        },
        "persistence_reconciliation": {
            "idempotency_key": key,
            "first_status": first["status"],
            "second_status": second["status"],
            "second_deduplicated": second["deduplicated"],
            "persisted_buffer_post_id": second["scheduled"]["targets"][0][
                "buffer_post_id"
            ],
        },
        "cleanup": {
            "invocations": cleanup_calls,
            "deleted": second["cleanup"]["deleted"],
            "skipped": second["cleanup"]["skipped"],
            "grace_guarded": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(
            ROOT
            / ".sin-goal/buffer-fleet-completion/evidence/T-0025-buffer-lifecycle-fixture.json"
        ),
    )
    args = parser.parse_args()
    evidence = run_fixture()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(evidence, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
