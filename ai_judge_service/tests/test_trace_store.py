import unittest

from app.trace_store import TraceStore


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

    def test_mark_replay_should_append_history(self) -> None:
        store = TraceStore(ttl_secs=3600)
        store.register_start(job_id=7, trace_id="trace-7", request={"job": {"job_id": 7}})
        store.mark_replay(job_id=7, winner="pro", needs_draw_vote=False, provider="openai")

        record = store.get_trace(7)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(len(record.replays), 1)
        self.assertEqual(record.replays[0].winner, "pro")


if __name__ == "__main__":
    unittest.main()
