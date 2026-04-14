import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.core.judge_core import JudgeCoreOrchestrator
from app.core.workflow import WorkflowOrchestrator
from app.domain.workflow import (
    WORKFLOW_STATUS_BLINDED,
    WORKFLOW_STATUS_BLOCKED_FAILED,
    WORKFLOW_STATUS_CALLBACK_REPORTED,
    WORKFLOW_STATUS_CASE_BUILT,
    WORKFLOW_STATUS_QUEUED,
    WORKFLOW_STATUS_REVIEW_REQUIRED,
    WorkflowJob,
)
from app.infra.db.runtime import build_database_runtime
from app.infra.workflow import PostgresWorkflowStore


class JudgeCoreOrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        db_file = Path(self._tmpdir.name) / "judge_core_test.db"
        settings = SimpleNamespace(
            db_url=f"sqlite+aiosqlite:///{db_file}",
            db_echo=False,
            db_pool_size=5,
            db_max_overflow=5,
        )
        self._db_runtime = build_database_runtime(settings=settings)
        await self._db_runtime.create_schema()

        store = PostgresWorkflowStore(session_factory=self._db_runtime.session_factory)
        workflow_orchestrator = WorkflowOrchestrator(workflow_port=store)
        self._judge_core = JudgeCoreOrchestrator(
            workflow_orchestrator=workflow_orchestrator
        )
        self._workflow_orchestrator = workflow_orchestrator

    async def asyncTearDown(self) -> None:
        await self._db_runtime.dispose()
        self._tmpdir.cleanup()

    async def test_judge_core_should_register_case_built_with_unified_event_payload(self) -> None:
        built = await self._judge_core.register_case_built(
            job=WorkflowJob(
                job_id=9201,
                dispatch_type="case",
                trace_id="trace-9201",
                status=WORKFLOW_STATUS_QUEUED,
                scope_id=1,
                session_id=2,
                idempotency_key="case:9201",
                rubric_version="v3",
                judge_policy_version="v3-default",
                topic_domain="tft",
                retrieval_profile="hybrid_v1",
            ),
            event_payload={"source": "unit-test"},
        )
        self.assertEqual(built.status, WORKFLOW_STATUS_CASE_BUILT)
        events = await self._workflow_orchestrator.list_events(job_id=9201)
        self.assertEqual(
            [item.event_type for item in events],
            ["job_registered", "status_changed", "status_changed"],
        )
        self.assertEqual(events[-1].payload.get("judgeCoreStage"), "case_built")
        self.assertEqual(events[-1].payload.get("judgeCoreVersion"), "v1")
        self.assertEqual(events[-1].payload.get("dispatchType"), "case")

    async def test_judge_core_should_mark_reported_completed_and_review_required(self) -> None:
        await self._judge_core.register_blinded(
            job=WorkflowJob(
                job_id=9202,
                dispatch_type="final",
                trace_id="trace-9202",
                status=WORKFLOW_STATUS_QUEUED,
            ),
            event_payload={"source": "unit-test"},
        )
        completed = await self._judge_core.mark_reported(
            job_id=9202,
            dispatch_type="final",
            review_required=False,
            event_payload={"winner": "pro"},
        )
        self.assertEqual(completed.status, WORKFLOW_STATUS_CALLBACK_REPORTED)
        events = await self._workflow_orchestrator.list_events(job_id=9202)
        self.assertEqual(events[-1].payload.get("judgeCoreStage"), "reported")
        self.assertEqual(events[-1].payload.get("dispatchType"), "final")
        self.assertEqual(events[-1].payload.get("winner"), "pro")

        await self._judge_core.register_blinded(
            job=WorkflowJob(
                job_id=9203,
                dispatch_type="final",
                trace_id="trace-9203",
                status=WORKFLOW_STATUS_QUEUED,
            ),
            event_payload={"source": "unit-test"},
        )
        review_required = await self._judge_core.mark_reported(
            job_id=9203,
            dispatch_type="final",
            review_required=True,
            event_payload={"reviewRequired": True},
        )
        self.assertEqual(review_required.status, WORKFLOW_STATUS_REVIEW_REQUIRED)
        events_review = await self._workflow_orchestrator.list_events(job_id=9203)
        self.assertEqual(events_review[-1].payload.get("judgeCoreStage"), "review_required")
        self.assertEqual(events_review[-1].payload.get("dispatchType"), "final")
        self.assertEqual(events_review[-1].payload.get("reviewRequired"), True)

    async def test_judge_core_should_mark_failed_with_unified_stage_payload(self) -> None:
        running = await self._judge_core.register_blinded(
            job=WorkflowJob(
                job_id=9204,
                dispatch_type="phase",
                trace_id="trace-9204",
                status=WORKFLOW_STATUS_QUEUED,
            ),
            event_payload={"phaseNo": 1},
        )
        self.assertEqual(running.status, WORKFLOW_STATUS_BLINDED)

        failed = await self._judge_core.mark_failed(
            job_id=9204,
            dispatch_type="phase",
            error_code="phase_callback_failed",
            error_message="callback failed",
            event_payload={"callbackStatus": "failed_reported"},
        )
        self.assertEqual(failed.status, WORKFLOW_STATUS_BLOCKED_FAILED)
        events = await self._workflow_orchestrator.list_events(job_id=9204)
        self.assertEqual(events[-1].payload.get("judgeCoreStage"), "blocked_failed")
        self.assertEqual(events[-1].payload.get("judgeCoreVersion"), "v1")
        self.assertEqual(events[-1].payload.get("dispatchType"), "phase")
        self.assertEqual(events[-1].payload.get("errorCode"), "phase_callback_failed")
        self.assertEqual(events[-1].payload.get("callbackStatus"), "failed_reported")

    async def test_judge_core_should_append_replay_event_without_status_transition(self) -> None:
        await self._judge_core.register_blinded(
            job=WorkflowJob(
                job_id=9205,
                dispatch_type="final",
                trace_id="trace-9205",
                status=WORKFLOW_STATUS_QUEUED,
            ),
            event_payload={"source": "unit-test"},
        )
        completed = await self._judge_core.mark_reported(
            job_id=9205,
            dispatch_type="final",
            review_required=False,
            event_payload={"winner": "pro"},
        )
        self.assertEqual(completed.status, WORKFLOW_STATUS_CALLBACK_REPORTED)

        await self._judge_core.mark_replay(
            job_id=9205,
            dispatch_type="final",
            event_payload={"winner": "draw", "traceId": "trace-9205"},
        )

        current = await self._workflow_orchestrator.get_job(job_id=9205)
        self.assertIsNotNone(current)
        assert current is not None
        self.assertEqual(current.status, WORKFLOW_STATUS_CALLBACK_REPORTED)
        events = await self._workflow_orchestrator.list_events(job_id=9205)
        self.assertEqual(events[-1].event_type, "replay_marked")
        self.assertEqual(events[-1].payload.get("judgeCoreStage"), "replay_computed")
        self.assertEqual(events[-1].payload.get("dispatchType"), "final")
        self.assertEqual(events[-1].payload.get("winner"), "draw")


if __name__ == "__main__":
    unittest.main()
