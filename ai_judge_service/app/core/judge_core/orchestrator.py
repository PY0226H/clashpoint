from __future__ import annotations

from typing import Any

from app.core.workflow import WorkflowOrchestrator
from app.domain.workflow import WORKFLOW_EVENT_REPLAY_MARKED, WorkflowJob

JUDGE_CORE_VERSION = "v1"
JUDGE_CORE_STAGE_CASE_BUILT = "case_built"
JUDGE_CORE_STAGE_RUNNING = "running"
JUDGE_CORE_STAGE_REPORTED = "reported"
JUDGE_CORE_STAGE_REVIEW_REQUIRED = "review_required"
JUDGE_CORE_STAGE_FAILED = "failed"
JUDGE_CORE_STAGE_REVIEW_APPROVED = "review_approved"
JUDGE_CORE_STAGE_REVIEW_REJECTED = "review_rejected"
JUDGE_CORE_STAGE_REPLAY_COMPUTED = "replay_computed"


class JudgeCoreOrchestrator:
    """Unifies case lifecycle transitions for phase/final/replay/review."""

    def __init__(self, *, workflow_orchestrator: WorkflowOrchestrator) -> None:
        self._workflow_orchestrator = workflow_orchestrator

    async def register_case_built(
        self,
        *,
        job: WorkflowJob,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        payload = self._build_event_payload(
            dispatch_type=job.dispatch_type,
            stage=JUDGE_CORE_STAGE_CASE_BUILT,
            event_payload=event_payload,
        )
        await self._workflow_orchestrator.register_job(
            job=job,
            event_payload=payload,
        )
        return await self._workflow_orchestrator.mark_case_built(
            job_id=job.job_id,
            event_payload=payload,
        )

    async def register_running(
        self,
        *,
        job: WorkflowJob,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        payload = self._build_event_payload(
            dispatch_type=job.dispatch_type,
            stage=JUDGE_CORE_STAGE_RUNNING,
            event_payload=event_payload,
        )
        await self._workflow_orchestrator.register_job(
            job=job,
            event_payload=payload,
        )
        return await self._workflow_orchestrator.mark_running(
            job_id=job.job_id,
            event_payload=payload,
        )

    async def mark_reported(
        self,
        *,
        job_id: int,
        dispatch_type: str,
        review_required: bool,
        completed_stage: str = JUDGE_CORE_STAGE_REPORTED,
        review_required_stage: str = JUDGE_CORE_STAGE_REVIEW_REQUIRED,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        stage = (
            str(review_required_stage or "").strip() or JUDGE_CORE_STAGE_REVIEW_REQUIRED
            if review_required
            else str(completed_stage or "").strip() or JUDGE_CORE_STAGE_REPORTED
        )
        payload = self._build_event_payload(
            dispatch_type=dispatch_type,
            stage=stage,
            event_payload=event_payload,
        )
        if review_required:
            return await self._workflow_orchestrator.mark_review_required(
                job_id=job_id,
                event_payload=payload,
            )
        return await self._workflow_orchestrator.mark_completed(
            job_id=job_id,
            event_payload=payload,
        )

    async def mark_failed(
        self,
        *,
        job_id: int,
        dispatch_type: str,
        error_code: str,
        error_message: str,
        stage: str = JUDGE_CORE_STAGE_FAILED,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        payload = self._build_event_payload(
            dispatch_type=dispatch_type,
            stage=str(stage or "").strip() or JUDGE_CORE_STAGE_FAILED,
            event_payload=event_payload,
        )
        return await self._workflow_orchestrator.mark_failed(
            job_id=job_id,
            error_code=error_code,
            error_message=error_message,
            event_payload=payload,
        )

    async def mark_replay(
        self,
        *,
        job_id: int,
        dispatch_type: str,
        event_payload: dict[str, Any] | None = None,
    ) -> None:
        payload = self._build_event_payload(
            dispatch_type=dispatch_type,
            stage=JUDGE_CORE_STAGE_REPLAY_COMPUTED,
            event_payload=event_payload,
        )
        await self._workflow_orchestrator.append_event(
            job_id=job_id,
            event_type=WORKFLOW_EVENT_REPLAY_MARKED,
            event_payload=payload,
        )

    def _build_event_payload(
        self,
        *,
        dispatch_type: str,
        stage: str,
        event_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload = dict(event_payload or {})
        normalized_dispatch_type = str(dispatch_type or "").strip().lower()
        if normalized_dispatch_type:
            payload.setdefault("dispatchType", normalized_dispatch_type)
        payload["judgeCoreStage"] = stage
        payload["judgeCoreVersion"] = JUDGE_CORE_VERSION
        return payload
