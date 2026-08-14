"""Buffer-first lifecycle orchestration with idempotent durable checkpoints."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable


def idempotency_key(payload: dict[str, Any]) -> str:
    canonical_payload = dict(payload)
    # When TeraBox is the durable source, media_url is a derived Supabase staging
    # location. It must not change the logical job identity across restaging.
    if isinstance(canonical_payload.get("terabox_source"), dict):
        canonical_payload.pop("media_url", None)
    canonical = json.dumps(
        canonical_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def run_buffer_lifecycle(
    payload: dict[str, Any],
    *,
    publish: Callable[..., dict[str, Any]],
    persist: Callable[..., dict[str, Any]],
    reconcile: Callable[..., dict[str, Any]],
    cleanup: Callable[..., dict[str, int]] | None = None,
    lookup: Callable[..., dict[str, Any] | None] | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Reserve, publish once, reconcile persisted Buffer IDs and clean when due.

    The durable ``draft`` reservation is acquired before any provider mutation.
    A retry that finds an existing reservation/job never calls ``publish`` again:
    scheduled/error jobs are reconciled from their persisted Buffer post IDs and
    sent jobs only run the grace-period cleanup check. A stranded draft is kept
    fail-closed because blindly retrying after an unknown provider outcome could
    create duplicate Buffer posts.
    """
    key = idempotency_key(payload)
    content_id = str(payload.get("content_id") or key)

    def cleanup_if_configured(*, first_sent: bool) -> dict[str, int]:
        if cleanup is None:
            return {"deleted": 0, "skipped": 0}
        return cleanup(
            content_id=content_id,
            idempotency_key=key,
            first_sent=first_sent,
        )

    def resume(existing: dict[str, Any]) -> dict[str, Any]:
        current_status = str(existing.get("status") or "draft").lower()
        targets = (
            existing.get("targets")
            if isinstance(existing.get("targets"), list)
            else []
        )
        if current_status == "sent":
            return {
                "idempotency_key": key,
                "status": "sent",
                "deduplicated": True,
                "scheduled": existing,
                "reconciliation": {
                    "all_sent": True,
                    "status": "sent",
                    "targets": targets,
                },
                "cleanup": cleanup_if_configured(first_sent=False),
            }
        if current_status == "draft":
            return {
                "idempotency_key": key,
                "status": "draft",
                "deduplicated": True,
                "scheduled": existing,
                "reconciliation": {
                    "all_sent": False,
                    "status": "reserved",
                    "targets": targets,
                    "reason": "existing draft reservation is fail-closed",
                },
                "cleanup": {"deleted": 0, "skipped": 1},
            }

        reconciliation = reconcile(
            idempotency_key=key, content_id=content_id, targets=targets
        )
        reconciled_targets = (
            reconciliation.get("targets")
            if isinstance(reconciliation.get("targets"), list)
            else targets
        )
        all_sent = bool(reconciliation.get("all_sent"))
        next_status = (
            "sent"
            if all_sent
            else str(reconciliation.get("job_status") or current_status or "scheduled").lower()
        )
        if next_status not in {"scheduled", "sent", "error"}:
            next_status = "scheduled"
        scheduled = persist(
            content_id=content_id,
            idempotency_key=key,
            targets=reconciled_targets,
            status=next_status,
            provider_result=existing.get("provider_result"),
        )
        return {
            "idempotency_key": key,
            "status": next_status,
            "deduplicated": True,
            "scheduled": scheduled,
            "reconciliation": reconciliation,
            "cleanup": (
                cleanup_if_configured(first_sent=True)
                if all_sent
                else {"deleted": 0, "skipped": 1}
            ),
        }

    existing = lookup(idempotency_key=key) if lookup else None
    if existing:
        return resume(existing)

    reservation = persist(
        content_id=content_id, idempotency_key=key, targets=[], status="draft"
    )
    if reservation.get("existing"):
        return resume(reservation)

    result = publish(payload, dry_run=dry_run, idempotency_key=key, provider="buffer")
    targets = (
        result.get("target_metadata")
        or result.get("targets")
        or result.get("posts")
        or []
    )
    scheduled = persist(
        content_id=content_id,
        idempotency_key=key,
        targets=targets,
        status="scheduled",
        provider_result=result,
    )
    reconciliation = reconcile(
        idempotency_key=key, content_id=content_id, targets=targets
    )
    reconciled_targets = (
        reconciliation.get("targets")
        if isinstance(reconciliation.get("targets"), list)
        else targets
    )
    all_sent = bool(reconciliation.get("all_sent"))
    final_status = (
        "sent"
        if all_sent
        else str(reconciliation.get("job_status") or "scheduled").lower()
    )
    if final_status not in {"scheduled", "sent", "error"}:
        final_status = "scheduled"
    if final_status != "scheduled" or reconciled_targets != targets:
        scheduled = persist(
            content_id=content_id,
            idempotency_key=key,
            targets=reconciled_targets,
            status=final_status,
            provider_result=result,
        )
    cleaned = (
        cleanup_if_configured(first_sent=True)
        if all_sent
        else {"deleted": 0, "skipped": 1}
    )
    return {
        "idempotency_key": key,
        "buffer": result,
        "scheduled": scheduled,
        "reconciliation": reconciliation,
        "cleanup": cleaned,
        "deduplicated": False,
        "status": final_status,
    }
