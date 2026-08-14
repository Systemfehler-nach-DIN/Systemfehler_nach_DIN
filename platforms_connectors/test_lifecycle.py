import unittest

from platforms_connectors.lifecycle import idempotency_key, run_buffer_lifecycle


class LifecycleTests(unittest.TestCase):
    def test_terabox_staging_url_does_not_change_job_identity(self):
        source = {
            "content_id": "c-stage",
            "title": "x",
            "terabox_source": {"remote_path": "/archive/a.mp4", "fs_id": 42},
            "media_url": "",
        }
        staged = {**source, "media_url": "https://supabase.example/object/a.mp4"}
        self.assertEqual(idempotency_key(source), idempotency_key(staged))

    def test_restart_retry_reconciles_without_second_buffer_create(self):
        durable = {}
        publish_calls = []
        cleanup_calls = []
        reconcile_round = {"count": 0}

        def lookup(**kw):
            row = durable.get(kw["idempotency_key"])
            return dict(row) if row else None

        def persist(**kw):
            key = kw["idempotency_key"]
            current = durable.get(key)
            if kw["status"] == "draft" and current:
                return {**current, "existing": True}
            row = {
                "job_id": "job-1",
                "content_id": kw["content_id"],
                "idempotency_key": key,
                "status": kw["status"],
                "targets": [dict(x) for x in kw.get("targets", [])],
            }
            durable[key] = row
            return {**row, "existing": False}

        def publish(payload, **kw):
            publish_calls.append(kw["idempotency_key"])
            return {
                "target_metadata": [
                    {
                        "account": 3,
                        "platform": "youtube",
                        "channel_id": "yt",
                        "buffer_post_id": "buffer-post-1",
                        "status": "scheduled",
                    }
                ]
            }

        def reconcile(**kw):
            reconcile_round["count"] += 1
            targets = [dict(x) for x in kw["targets"]]
            if reconcile_round["count"] == 1:
                return {
                    "all_sent": False,
                    "job_status": "scheduled",
                    "targets": targets,
                }
            targets[0]["status"] = "sent"
            return {"all_sent": True, "job_status": "sent", "targets": targets}

        def cleanup(**kw):
            cleanup_calls.append(dict(kw))
            return {"deleted": 0, "skipped": 1}

        payload = {"content_id": "c1", "title": "x"}
        first = run_buffer_lifecycle(
            payload,
            publish=publish,
            persist=persist,
            reconcile=reconcile,
            cleanup=cleanup,
            lookup=lookup,
            dry_run=False,
        )
        self.assertEqual(first["status"], "scheduled")
        self.assertEqual(len(publish_calls), 1)
        self.assertEqual(
            first["scheduled"]["targets"][0]["buffer_post_id"], "buffer-post-1"
        )

        # Simulates a new process: only the durable lookup survives. The second
        # execution must reconcile the persisted Buffer ID, never create again.
        second = run_buffer_lifecycle(
            payload,
            publish=publish,
            persist=persist,
            reconcile=reconcile,
            cleanup=cleanup,
            lookup=lookup,
            dry_run=False,
        )
        self.assertTrue(second["deduplicated"])
        self.assertEqual(second["status"], "sent")
        self.assertEqual(len(publish_calls), 1)
        self.assertEqual(second["idempotency_key"], first["idempotency_key"])
        self.assertEqual(len(cleanup_calls), 1)
        self.assertTrue(cleanup_calls[0]["first_sent"])

        third = run_buffer_lifecycle(
            payload,
            publish=publish,
            persist=persist,
            reconcile=reconcile,
            cleanup=cleanup,
            lookup=lookup,
            dry_run=False,
        )
        self.assertEqual(third["status"], "sent")
        self.assertEqual(len(publish_calls), 1)
        self.assertEqual(len(cleanup_calls), 2)
        self.assertFalse(cleanup_calls[-1]["first_sent"])

    def test_existing_draft_reservation_fails_closed_without_publish(self):
        published = []
        key_holder = {}

        def persist(**kw):
            key_holder["key"] = kw["idempotency_key"]
            return {
                "job_id": "job-1",
                "idempotency_key": kw["idempotency_key"],
                "content_id": kw["content_id"],
                "status": "draft",
                "targets": [],
                "existing": True,
            }

        result = run_buffer_lifecycle(
            {"content_id": "c-reserved"},
            publish=lambda *a, **k: published.append(1),
            persist=persist,
            reconcile=lambda **k: self.fail("draft must not reconcile"),
            lookup=lambda **k: None,
            dry_run=False,
        )
        self.assertEqual(result["status"], "draft")
        self.assertTrue(result["deduplicated"])
        self.assertEqual(published, [])
        self.assertEqual(result["idempotency_key"], key_holder["key"])

    def test_failed_reconciliation_keeps_asset(self):
        cleaned = []
        result = run_buffer_lifecycle(
            {"content_id": "c2"},
            publish=lambda *a, **k: {"target_metadata": []},
            persist=lambda **k: {"status": k["status"], "targets": k.get("targets", [])},
            reconcile=lambda **k: {"all_sent": False, "job_status": "scheduled"},
            cleanup=lambda **k: cleaned.append(1),
        )
        self.assertEqual(result["status"], "scheduled")
        self.assertEqual(cleaned, [])


if __name__ == "__main__":
    unittest.main()
