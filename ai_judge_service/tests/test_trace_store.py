import unittest
from datetime import datetime, timezone

from app.trace_store import (
    TraceQuery,
    TraceStore,
    build_trace_store_from_settings,
)


class TraceStoreTests(unittest.TestCase):
    def test_register_and_query_trace(self) -> None:
        store = TraceStore(ttl_secs=3600)
        store.register_start(job_id=11, trace_id="trace-11", request={"job": {"job_id": 11}})
        store.register_success(
            job_id=11,
            response={"accepted": True, "jobId": 11},
            callback_status="reported",
            report_summary={"payload": {"provider": "openai"}},
        )

        record = store.get_trace(11)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.status, "completed")
        self.assertEqual(record.response["jobId"], 11)
        self.assertEqual(record.callback_status, "reported")

    def test_idempotency_should_cache_response(self) -> None:
        store = TraceStore(ttl_secs=3600)
        store.set_idempotency_pending(key="k1", job_id=21, ttl_secs=3600)
        pending = store.get_idempotency("k1")
        self.assertIsNotNone(pending)
        assert pending is not None
        self.assertIsNone(pending.response)

        store.set_idempotency_success(
            key="k1",
            job_id=21,
            response={"accepted": True, "jobId": 21},
            ttl_secs=3600,
        )
        cached = store.get_idempotency("k1")
        self.assertIsNotNone(cached)
        assert cached is not None
        self.assertEqual(cached.response["jobId"], 21)

    def test_clear_idempotency_should_remove_pending_record(self) -> None:
        store = TraceStore(ttl_secs=3600)
        store.set_idempotency_pending(key="k2", job_id=22, ttl_secs=3600)
        self.assertIsNotNone(store.get_idempotency("k2"))
        store.clear_idempotency("k2")
        self.assertIsNone(store.get_idempotency("k2"))

    def test_mark_replay_should_append_history(self) -> None:
        store = TraceStore(ttl_secs=3600)
        store.register_start(job_id=7, trace_id="trace-7", request={"job": {"job_id": 7}})
        store.mark_replay(job_id=7, winner="pro", needs_draw_vote=False, provider="openai")

        record = store.get_trace(7)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(len(record.replays), 1)
        self.assertEqual(record.replays[0].winner, "pro")

    def test_topic_memory_should_store_and_reuse_latest_items(self) -> None:
        store = TraceStore(ttl_secs=3600, topic_memory_limit=2)
        store.save_topic_memory(
            job_id=1,
            trace_id="t1",
            topic_domain="finance",
            rubric_version="v1",
            winner="pro",
            rationale="first",
            evidence_refs=[{"messageId": 1, "reason": "a"}],
            provider="openai",
        )
        store.save_topic_memory(
            job_id=2,
            trace_id="t2",
            topic_domain="finance",
            rubric_version="v1",
            winner="con",
            rationale="second",
            evidence_refs=[{"messageId": 2, "reason": "b"}],
            provider="openai",
        )
        store.save_topic_memory(
            job_id=3,
            trace_id="t3",
            topic_domain="finance",
            rubric_version="v1",
            winner="draw",
            rationale="third",
            evidence_refs=[{"messageId": 3, "reason": "c"}],
            provider="openai",
        )

        rows = store.list_topic_memory(topic_domain="finance", rubric_version="v1", limit=5)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].job_id, 3)
        self.assertEqual(rows[1].job_id, 2)

    def test_topic_memory_should_keep_audit_payload(self) -> None:
        store = TraceStore(ttl_secs=3600, topic_memory_limit=2)
        store.save_topic_memory(
            job_id=7,
            trace_id="trace-7",
            topic_domain="finance",
            rubric_version="v1",
            winner="pro",
            rationale="rationale for quality",
            evidence_refs=[{"messageId": 1, "reason": "test"}],
            provider="openai",
            audit={"qualityScore": 0.88, "accepted": True},
        )
        rows = store.list_topic_memory(topic_domain="finance", rubric_version="v1", limit=1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].audit["qualityScore"], 0.88)

    def test_list_traces_should_support_status_winner_and_audit_filters(self) -> None:
        store = TraceStore(ttl_secs=3600)
        for job_id, winner, with_alert in (
            (101, "pro", True),
            (102, "con", False),
            (103, "pro", False),
        ):
            store.register_start(
                job_id=job_id,
                trace_id=f"trace-{job_id}",
                request={"job": {"job_id": job_id}},
            )
            payload = {"provider": "openai"}
            if with_alert:
                payload["auditAlerts"] = [{"type": "compliance_violation"}]
            store.register_success(
                job_id=job_id,
                response={
                    "accepted": True,
                    "jobId": job_id,
                    "winner": winner,
                    "provider": "openai",
                },
                callback_status="reported",
                report_summary={"winner": winner, "payload": payload},
            )

        rows = store.list_traces(
            query=TraceQuery(status="completed", winner="pro", has_audit_alert=True, limit=5)
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].job_id, 101)

        rows = store.list_traces(query=TraceQuery(winner="pro", limit=5))
        self.assertEqual({row.job_id for row in rows}, {101, 103})

    def test_list_traces_should_support_created_at_range_filter(self) -> None:
        store = TraceStore(ttl_secs=3600)
        store.register_start(job_id=201, trace_id="trace-201", request={"job": {"job_id": 201}})
        store.register_success(
            job_id=201,
            response={"accepted": True, "jobId": 201, "winner": "pro"},
            callback_status="reported",
            report_summary={"winner": "pro", "payload": {}},
        )
        store.register_start(job_id=202, trace_id="trace-202", request={"job": {"job_id": 202}})
        store.register_success(
            job_id=202,
            response={"accepted": True, "jobId": 202, "winner": "con"},
            callback_status="reported",
            report_summary={"winner": "con", "payload": {}},
        )

        old = datetime(2026, 1, 1, tzinfo=timezone.utc)
        new = datetime(2026, 1, 3, tzinfo=timezone.utc)
        store._traces[201].created_at = old
        store._traces[202].created_at = new

        rows = store.list_traces(
            query=TraceQuery(
                created_after=datetime(2026, 1, 2, tzinfo=timezone.utc),
                created_before=datetime(2026, 1, 4, tzinfo=timezone.utc),
                limit=5,
            )
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].job_id, 202)

    def test_audit_alert_state_machine_and_outbox_should_work(self) -> None:
        store = TraceStore(ttl_secs=3600)
        alert = store.upsert_audit_alert(
            job_id=301,
            ws_id=1,
            trace_id="trace-301",
            alert_type="compliance_violation",
            severity="warning",
            title="AI Judge Compliance Violation",
            message="violations=display_missing_rationale",
            details={"violations": ["display_missing_rationale"]},
        )
        self.assertEqual(alert.status, "raised")

        rows = store.list_audit_alerts(job_id=301, status="raised", limit=10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].alert_id, alert.alert_id)

        acked = store.transition_audit_alert(
            job_id=301,
            alert_id=alert.alert_id,
            to_status="acked",
            actor="ops_user_1",
            reason="reviewed",
        )
        self.assertIsNotNone(acked)
        assert acked is not None
        self.assertEqual(acked.status, "acked")
        self.assertEqual(len(acked.transitions), 1)

        resolved = store.transition_audit_alert(
            job_id=301,
            alert_id=alert.alert_id,
            to_status="resolved",
            actor="ops_user_1",
            reason="fixed",
        )
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved.status, "resolved")
        self.assertEqual(len(resolved.transitions), 2)

        invalid = store.transition_audit_alert(
            job_id=301,
            alert_id=alert.alert_id,
            to_status="raised",
            actor="ops_user_1",
            reason="rollback",
        )
        self.assertIsNone(invalid)

        outbox = store.list_alert_outbox(delivery_status="pending", limit=10)
        self.assertGreaterEqual(len(outbox), 3)
        first_event = outbox[0]
        updated = store.mark_alert_outbox_delivery(
            event_id=first_event.event_id,
            delivery_status="sent",
            error_message=None,
        )
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated.delivery_status, "sent")


class _DummySettings:
    redis_enabled = True
    redis_required = False
    redis_url = "redis://127.0.0.1:6379/0"
    redis_pool_size = 20
    redis_key_prefix = "ai_judge:v2"
    trace_ttl_secs = 86400
    topic_memory_limit = 5
    topic_memory_min_evidence_refs = 1
    topic_memory_min_rationale_chars = 20
    topic_memory_min_quality_score = 0.55


class TraceStoreBuilderTests(unittest.TestCase):
    def test_build_store_should_fallback_to_memory_when_redis_unavailable(self) -> None:
        settings = _DummySettings()
        store = build_trace_store_from_settings(settings=settings)
        self.assertIsInstance(store, TraceStore)

    def test_build_store_should_raise_when_redis_required_and_unavailable(self) -> None:
        settings = _DummySettings()
        settings.redis_required = True
        with self.assertRaises(RuntimeError):
            build_trace_store_from_settings(settings=settings)


if __name__ == "__main__":
    unittest.main()
