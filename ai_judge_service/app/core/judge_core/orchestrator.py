from __future__ import annotations

from typing import Any

from app.core.workflow import WorkflowOrchestrator
from app.domain.workflow import (
    WORKFLOW_EVENT_REPLAY_MARKED,
    WORKFLOW_STATUS_ARBITRATED,
    WORKFLOW_STATUS_BLINDED,
    WORKFLOW_STATUS_CALLBACK_REPORTED,
    WORKFLOW_STATUS_CASE_BUILT,
    WORKFLOW_STATUS_CLAIM_GRAPH_READY,
    WORKFLOW_STATUS_DRAW_PENDING_VOTE,
    WORKFLOW_STATUS_EVIDENCE_READY,
    WORKFLOW_STATUS_FAIRNESS_CHECKED,
    WORKFLOW_STATUS_OPINION_WRITTEN,
    WORKFLOW_STATUS_PANEL_JUDGED,
    WORKFLOW_STATUS_QUEUED,
    WORKFLOW_STATUS_REVIEW_REQUIRED,
    WorkflowJob,
)

JUDGE_CORE_VERSION = "v1"
JUDGE_CORE_STAGE_BLINDED = "blinded"
JUDGE_CORE_STAGE_CASE_BUILT = "case_built"
JUDGE_CORE_STAGE_CLAIM_GRAPH_READY = "claim_graph_ready"
JUDGE_CORE_STAGE_EVIDENCE_READY = "evidence_ready"
JUDGE_CORE_STAGE_PANEL_JUDGED = "panel_judged"
JUDGE_CORE_STAGE_FAIRNESS_CHECKED = "fairness_checked"
JUDGE_CORE_STAGE_ARBITRATED = "arbitrated"
JUDGE_CORE_STAGE_OPINION_WRITTEN = "opinion_written"
JUDGE_CORE_STAGE_CALLBACK_REPORTED = "callback_reported"
JUDGE_CORE_STAGE_REPORTED = "reported"
JUDGE_CORE_STAGE_REVIEW_REQUIRED = "review_required"
JUDGE_CORE_STAGE_BLOCKED_FAILED = "blocked_failed"
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
        await self._workflow_orchestrator.mark_blinded(
            job_id=job.job_id,
            event_payload=self._build_event_payload(
                dispatch_type=job.dispatch_type,
                stage=JUDGE_CORE_STAGE_BLINDED,
                event_payload=event_payload,
            ),
        )
        return await self._workflow_orchestrator.mark_case_built(
            job_id=job.job_id,
            event_payload=payload,
        )

    async def register_blinded(
        self,
        *,
        job: WorkflowJob,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        payload = self._build_event_payload(
            dispatch_type=job.dispatch_type,
            stage=JUDGE_CORE_STAGE_BLINDED,
            event_payload=event_payload,
        )
        await self._workflow_orchestrator.register_job(
            job=job,
            event_payload=payload,
        )
        return await self._workflow_orchestrator.mark_blinded(
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
        return await self._advance_to_callback_reported(
            job_id=job_id,
            dispatch_type=dispatch_type,
            final_payload=payload,
        )

    async def mark_failed(
        self,
        *,
        job_id: int,
        dispatch_type: str,
        error_code: str,
        error_message: str,
        stage: str = JUDGE_CORE_STAGE_BLOCKED_FAILED,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        payload = self._build_event_payload(
            dispatch_type=dispatch_type,
            stage=str(stage or "").strip() or JUDGE_CORE_STAGE_BLOCKED_FAILED,
            event_payload=event_payload,
        )
        return await self._workflow_orchestrator.mark_blocked_failed(
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

    async def _advance_to_callback_reported(
        self,
        *,
        job_id: int,
        dispatch_type: str,
        final_payload: dict[str, Any],
    ) -> WorkflowJob:
        current = await self._workflow_orchestrator.get_job(job_id=job_id)
        if current is None:
            raise LookupError(f"workflow job not found: job_id={job_id}")

        progress_chain = [
            (
                WORKFLOW_STATUS_CLAIM_GRAPH_READY,
                JUDGE_CORE_STAGE_CLAIM_GRAPH_READY,
                self._workflow_orchestrator.mark_claim_graph_ready,
            ),
            (
                WORKFLOW_STATUS_EVIDENCE_READY,
                JUDGE_CORE_STAGE_EVIDENCE_READY,
                self._workflow_orchestrator.mark_evidence_ready,
            ),
            (
                WORKFLOW_STATUS_PANEL_JUDGED,
                JUDGE_CORE_STAGE_PANEL_JUDGED,
                self._workflow_orchestrator.mark_panel_judged,
            ),
            (
                WORKFLOW_STATUS_FAIRNESS_CHECKED,
                JUDGE_CORE_STAGE_FAIRNESS_CHECKED,
                self._workflow_orchestrator.mark_fairness_checked,
            ),
            (
                WORKFLOW_STATUS_ARBITRATED,
                JUDGE_CORE_STAGE_ARBITRATED,
                self._workflow_orchestrator.mark_arbitrated,
            ),
            (
                WORKFLOW_STATUS_OPINION_WRITTEN,
                JUDGE_CORE_STAGE_OPINION_WRITTEN,
                self._workflow_orchestrator.mark_opinion_written,
            ),
            (
                WORKFLOW_STATUS_CALLBACK_REPORTED,
                JUDGE_CORE_STAGE_CALLBACK_REPORTED,
                self._workflow_orchestrator.mark_callback_reported,
            ),
        ]
        review_resume_chain = [
            (
                WORKFLOW_STATUS_ARBITRATED,
                JUDGE_CORE_STAGE_ARBITRATED,
                self._workflow_orchestrator.mark_arbitrated,
            ),
            (
                WORKFLOW_STATUS_OPINION_WRITTEN,
                JUDGE_CORE_STAGE_OPINION_WRITTEN,
                self._workflow_orchestrator.mark_opinion_written,
            ),
            (
                WORKFLOW_STATUS_CALLBACK_REPORTED,
                JUDGE_CORE_STAGE_CALLBACK_REPORTED,
                self._workflow_orchestrator.mark_callback_reported,
            ),
        ]

        if current.status in {WORKFLOW_STATUS_REVIEW_REQUIRED, WORKFLOW_STATUS_DRAW_PENDING_VOTE}:
            chain = review_resume_chain
        elif current.status in {WORKFLOW_STATUS_QUEUED, WORKFLOW_STATUS_BLINDED, WORKFLOW_STATUS_CASE_BUILT}:
            chain = progress_chain
        elif current.status == WORKFLOW_STATUS_CALLBACK_REPORTED:
            return current
        else:
            return await self._workflow_orchestrator.mark_callback_reported(
                job_id=job_id,
                event_payload=final_payload,
            )

        latest = current
        for status, stage, transition in chain:
            if latest.status == status:
                continue
            payload = self._build_event_payload(
                dispatch_type=dispatch_type,
                stage=stage,
                event_payload=final_payload,
            )
            if status == WORKFLOW_STATUS_CALLBACK_REPORTED:
                payload = dict(final_payload)
                payload.setdefault("dispatchType", str(dispatch_type or "").strip().lower())
                payload.setdefault("judgeCoreVersion", JUDGE_CORE_VERSION)
                payload.setdefault("judgeCoreStage", JUDGE_CORE_STAGE_REPORTED)
            latest = await transition(
                job_id=job_id,
                event_payload=payload,
            )
        return latest

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
