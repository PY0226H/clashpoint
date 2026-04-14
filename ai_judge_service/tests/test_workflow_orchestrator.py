import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.core.workflow import WorkflowOrchestrator, WorkflowTransitionError
from app.domain.workflow import (
    WORKFLOW_STATUS_BLINDED,
    WORKFLOW_STATUS_BLOCKED_FAILED,
    WORKFLOW_STATUS_CALLBACK_REPORTED,
    WORKFLOW_STATUS_QUEUED,
    WORKFLOW_STATUS_REVIEW_REQUIRED,
    WorkflowJob,
)
from app.infra.db.runtime import build_database_runtime
from app.infra.workflow import PostgresWorkflowStore


class WorkflowOrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        db_file = Path(self._tmpdir.name) / "workflow_test.db"
        settings = SimpleNamespace(
            db_url=f"sqlite+aiosqlite:///{db_file}",
            db_echo=False,
            db_pool_size=5,
            db_max_overflow=5,
        )
        self._db_runtime = build_database_runtime(settings=settings)
        await self._db_runtime.create_schema()

        store = PostgresWorkflowStore(session_factory=self._db_runtime.session_factory)
        self._orchestrator = WorkflowOrchestrator(workflow_port=store)

    async def asyncTearDown(self) -> None:
        await self._db_runtime.dispose()
        self._tmpdir.cleanup()

    async def test_orchestrator_should_persist_status_and_events(self) -> None:
        registered = await self._orchestrator.register_job(
            job=WorkflowJob(
                job_id=9001,
                dispatch_type="final",
                trace_id="trace-9001",
                status=WORKFLOW_STATUS_QUEUED,
                scope_id=7,
                session_id=100,
                idempotency_key="idemp-9001",
                rubric_version="r1",
                judge_policy_version="jp1",
                topic_domain="finance",
                retrieval_profile="strict",
            ),
            event_payload={"source": "unit-test"},
        )
        self.assertEqual(registered.status, WORKFLOW_STATUS_QUEUED)

        blinded = await self._orchestrator.mark_blinded(
            job_id=9001,
            event_payload={"phase": "blind_input"},
        )
        case_built = await self._orchestrator.mark_case_built(
            job_id=9001,
            event_payload={"phase": "build_case"},
        )
        claim_graph = await self._orchestrator.mark_claim_graph_ready(job_id=9001)
        evidence_ready = await self._orchestrator.mark_evidence_ready(job_id=9001)
        panel_judged = await self._orchestrator.mark_panel_judged(job_id=9001)
        fairness_checked = await self._orchestrator.mark_fairness_checked(job_id=9001)
        arbitrated = await self._orchestrator.mark_arbitrated(job_id=9001)
        opinion_written = await self._orchestrator.mark_opinion_written(job_id=9001)
        callback_reported = await self._orchestrator.mark_callback_reported(
            job_id=9001,
            event_payload={"winner": "pro"},
        )

        self.assertEqual(blinded.status, WORKFLOW_STATUS_BLINDED)
        self.assertEqual(case_built.status, "case_built")
        self.assertEqual(claim_graph.status, "claim_graph_ready")
        self.assertEqual(evidence_ready.status, "evidence_ready")
        self.assertEqual(panel_judged.status, "panel_judged")
        self.assertEqual(fairness_checked.status, "fairness_checked")
        self.assertEqual(arbitrated.status, "arbitrated")
        self.assertEqual(opinion_written.status, "opinion_written")
        self.assertEqual(callback_reported.status, WORKFLOW_STATUS_CALLBACK_REPORTED)

        current = await self._orchestrator.get_job(job_id=9001)
        self.assertIsNotNone(current)
        assert current is not None
        self.assertEqual(current.status, WORKFLOW_STATUS_CALLBACK_REPORTED)

        events = await self._orchestrator.list_events(job_id=9001)
        self.assertEqual([row.event_seq for row in events], list(range(1, 11)))
        self.assertEqual(events[0].event_type, "job_registered")
        self.assertEqual(events[-1].payload.get("winner"), "pro")

    async def test_orchestrator_should_block_invalid_transition(self) -> None:
        await self._orchestrator.register_job(
            job=WorkflowJob(
                job_id=9002,
                dispatch_type="phase",
                trace_id="trace-9002",
                status=WORKFLOW_STATUS_QUEUED,
            )
        )

        with self.assertRaises(WorkflowTransitionError):
            await self._orchestrator.mark_callback_reported(job_id=9002)

        failed = await self._orchestrator.mark_blocked_failed(
            job_id=9002,
            error_code="provider_timeout",
            error_message="provider timeout",
        )
        self.assertEqual(failed.status, WORKFLOW_STATUS_BLOCKED_FAILED)

        events = await self._orchestrator.list_events(job_id=9002)
        self.assertEqual(events[-1].payload.get("errorCode"), "provider_timeout")

    async def test_orchestrator_should_list_jobs_by_status(self) -> None:
        await self._orchestrator.register_job(
            job=WorkflowJob(
                job_id=9010,
                dispatch_type="final",
                trace_id="trace-9010",
                status=WORKFLOW_STATUS_QUEUED,
            )
        )
        await self._orchestrator.mark_blinded(job_id=9010)
        await self._orchestrator.mark_review_required(
            job_id=9010,
            event_payload={"reason": "panel disagreement"},
        )

        await self._orchestrator.register_job(
            job=WorkflowJob(
                job_id=9011,
                dispatch_type="phase",
                trace_id="trace-9011",
                status=WORKFLOW_STATUS_QUEUED,
            )
        )
        await self._orchestrator.mark_blinded(job_id=9011)
        await self._orchestrator.mark_draw_pending_vote(job_id=9011)
        await self._orchestrator.mark_callback_reported(job_id=9011)

        review_jobs = await self._orchestrator.list_jobs(
            status=WORKFLOW_STATUS_REVIEW_REQUIRED,
            dispatch_type="final",
            limit=20,
        )
        self.assertEqual([item.job_id for item in review_jobs], [9010])

    async def test_orchestrator_should_append_event_without_changing_status(self) -> None:
        await self._orchestrator.register_job(
            job=WorkflowJob(
                job_id=9012,
                dispatch_type="final",
                trace_id="trace-9012",
                status=WORKFLOW_STATUS_QUEUED,
            )
        )
        await self._orchestrator.mark_blinded(job_id=9012)
        await self._orchestrator.append_event(
            job_id=9012,
            event_type="replay_marked",
            event_payload={"judgeCoreStage": "replay_computed"},
        )
        current = await self._orchestrator.get_job(job_id=9012)
        self.assertIsNotNone(current)
        assert current is not None
        self.assertEqual(current.status, "blinded")
        events = await self._orchestrator.list_events(job_id=9012)
        self.assertEqual(events[-1].event_type, "replay_marked")
        self.assertEqual(events[-1].payload.get("judgeCoreStage"), "replay_computed")
