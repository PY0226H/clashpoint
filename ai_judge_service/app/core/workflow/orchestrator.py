from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.domain.workflow import (
    WORKFLOW_EVENT_REGISTERED,
    WORKFLOW_EVENT_STATUS_CHANGED,
    WORKFLOW_STATUS_ARBITRATED,
    WORKFLOW_STATUS_ARCHIVED,
    WORKFLOW_STATUS_BLINDED,
    WORKFLOW_STATUS_BLOCKED_FAILED,
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
    WorkflowPort,
)

from .errors import WorkflowTransitionError

_ALLOWED_TRANSITIONS = {
    WORKFLOW_STATUS_QUEUED: {
        WORKFLOW_STATUS_BLINDED,
        WORKFLOW_STATUS_CASE_BUILT,
        WORKFLOW_STATUS_REVIEW_REQUIRED,
        WORKFLOW_STATUS_BLOCKED_FAILED,
    },
    WORKFLOW_STATUS_BLINDED: {
        WORKFLOW_STATUS_CASE_BUILT,
        WORKFLOW_STATUS_CLAIM_GRAPH_READY,
        WORKFLOW_STATUS_REVIEW_REQUIRED,
        WORKFLOW_STATUS_DRAW_PENDING_VOTE,
        WORKFLOW_STATUS_BLOCKED_FAILED,
    },
    WORKFLOW_STATUS_CASE_BUILT: {
        WORKFLOW_STATUS_CLAIM_GRAPH_READY,
        WORKFLOW_STATUS_REVIEW_REQUIRED,
        WORKFLOW_STATUS_DRAW_PENDING_VOTE,
        WORKFLOW_STATUS_BLOCKED_FAILED,
    },
    WORKFLOW_STATUS_CLAIM_GRAPH_READY: {
        WORKFLOW_STATUS_EVIDENCE_READY,
        WORKFLOW_STATUS_REVIEW_REQUIRED,
        WORKFLOW_STATUS_DRAW_PENDING_VOTE,
        WORKFLOW_STATUS_BLOCKED_FAILED,
    },
    WORKFLOW_STATUS_EVIDENCE_READY: {
        WORKFLOW_STATUS_PANEL_JUDGED,
        WORKFLOW_STATUS_REVIEW_REQUIRED,
        WORKFLOW_STATUS_DRAW_PENDING_VOTE,
        WORKFLOW_STATUS_BLOCKED_FAILED,
    },
    WORKFLOW_STATUS_PANEL_JUDGED: {
        WORKFLOW_STATUS_FAIRNESS_CHECKED,
        WORKFLOW_STATUS_REVIEW_REQUIRED,
        WORKFLOW_STATUS_DRAW_PENDING_VOTE,
        WORKFLOW_STATUS_BLOCKED_FAILED,
    },
    WORKFLOW_STATUS_FAIRNESS_CHECKED: {
        WORKFLOW_STATUS_ARBITRATED,
        WORKFLOW_STATUS_REVIEW_REQUIRED,
        WORKFLOW_STATUS_DRAW_PENDING_VOTE,
        WORKFLOW_STATUS_BLOCKED_FAILED,
    },
    WORKFLOW_STATUS_ARBITRATED: {
        WORKFLOW_STATUS_OPINION_WRITTEN,
        WORKFLOW_STATUS_REVIEW_REQUIRED,
        WORKFLOW_STATUS_DRAW_PENDING_VOTE,
        WORKFLOW_STATUS_BLOCKED_FAILED,
    },
    WORKFLOW_STATUS_OPINION_WRITTEN: {
        WORKFLOW_STATUS_CALLBACK_REPORTED,
        WORKFLOW_STATUS_REVIEW_REQUIRED,
        WORKFLOW_STATUS_DRAW_PENDING_VOTE,
        WORKFLOW_STATUS_BLOCKED_FAILED,
    },
    WORKFLOW_STATUS_CALLBACK_REPORTED: {
        WORKFLOW_STATUS_ARCHIVED,
        WORKFLOW_STATUS_REVIEW_REQUIRED,
        WORKFLOW_STATUS_DRAW_PENDING_VOTE,
    },
    WORKFLOW_STATUS_DRAW_PENDING_VOTE: {
        WORKFLOW_STATUS_ARBITRATED,
        WORKFLOW_STATUS_OPINION_WRITTEN,
        WORKFLOW_STATUS_CALLBACK_REPORTED,
        WORKFLOW_STATUS_ARCHIVED,
        WORKFLOW_STATUS_REVIEW_REQUIRED,
        WORKFLOW_STATUS_BLOCKED_FAILED,
    },
    WORKFLOW_STATUS_REVIEW_REQUIRED: {
        WORKFLOW_STATUS_ARBITRATED,
        WORKFLOW_STATUS_OPINION_WRITTEN,
        WORKFLOW_STATUS_CALLBACK_REPORTED,
        WORKFLOW_STATUS_ARCHIVED,
        WORKFLOW_STATUS_DRAW_PENDING_VOTE,
        WORKFLOW_STATUS_BLOCKED_FAILED,
    },
    WORKFLOW_STATUS_ARCHIVED: set(),
    WORKFLOW_STATUS_BLOCKED_FAILED: set(),
}


class WorkflowOrchestrator:
    def __init__(self, *, workflow_port: WorkflowPort) -> None:
        self._workflow_port = workflow_port

    async def register_job(
        self,
        *,
        job: WorkflowJob,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        queued_job = replace(job, status=WORKFLOW_STATUS_QUEUED)
        return await self._workflow_port.register_job(
            job=queued_job,
            event_type=WORKFLOW_EVENT_REGISTERED,
            event_payload=event_payload,
        )

    async def mark_case_built(
        self,
        *,
        job_id: int,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        return await self._transition(
            job_id=job_id,
            to_status=WORKFLOW_STATUS_CASE_BUILT,
            event_payload=event_payload,
        )

    async def mark_blinded(
        self,
        *,
        job_id: int,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        return await self._transition(
            job_id=job_id,
            to_status=WORKFLOW_STATUS_BLINDED,
            event_payload=event_payload,
        )

    async def mark_claim_graph_ready(
        self,
        *,
        job_id: int,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        return await self._transition(
            job_id=job_id,
            to_status=WORKFLOW_STATUS_CLAIM_GRAPH_READY,
            event_payload=event_payload,
        )

    async def mark_evidence_ready(
        self,
        *,
        job_id: int,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        return await self._transition(
            job_id=job_id,
            to_status=WORKFLOW_STATUS_EVIDENCE_READY,
            event_payload=event_payload,
        )

    async def mark_panel_judged(
        self,
        *,
        job_id: int,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        return await self._transition(
            job_id=job_id,
            to_status=WORKFLOW_STATUS_PANEL_JUDGED,
            event_payload=event_payload,
        )

    async def mark_fairness_checked(
        self,
        *,
        job_id: int,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        return await self._transition(
            job_id=job_id,
            to_status=WORKFLOW_STATUS_FAIRNESS_CHECKED,
            event_payload=event_payload,
        )

    async def mark_arbitrated(
        self,
        *,
        job_id: int,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        return await self._transition(
            job_id=job_id,
            to_status=WORKFLOW_STATUS_ARBITRATED,
            event_payload=event_payload,
        )

    async def mark_opinion_written(
        self,
        *,
        job_id: int,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        return await self._transition(
            job_id=job_id,
            to_status=WORKFLOW_STATUS_OPINION_WRITTEN,
            event_payload=event_payload,
        )

    async def mark_callback_reported(
        self,
        *,
        job_id: int,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        return await self._transition(
            job_id=job_id,
            to_status=WORKFLOW_STATUS_CALLBACK_REPORTED,
            event_payload=event_payload,
        )

    async def mark_review_required(
        self,
        *,
        job_id: int,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        return await self._transition(
            job_id=job_id,
            to_status=WORKFLOW_STATUS_REVIEW_REQUIRED,
            event_payload=event_payload,
        )

    async def mark_draw_pending_vote(
        self,
        *,
        job_id: int,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        return await self._transition(
            job_id=job_id,
            to_status=WORKFLOW_STATUS_DRAW_PENDING_VOTE,
            event_payload=event_payload,
        )

    async def mark_archived(
        self,
        *,
        job_id: int,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        return await self._transition(
            job_id=job_id,
            to_status=WORKFLOW_STATUS_ARCHIVED,
            event_payload=event_payload,
        )

    async def mark_blocked_failed(
        self,
        *,
        job_id: int,
        error_code: str,
        error_message: str,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        payload = dict(event_payload or {})
        payload.setdefault("errorCode", error_code)
        payload.setdefault("errorMessage", error_message)
        return await self._transition(
            job_id=job_id,
            to_status=WORKFLOW_STATUS_BLOCKED_FAILED,
            event_payload=payload,
        )

    async def get_job(self, *, job_id: int) -> WorkflowJob | None:
        return await self._workflow_port.get_job(job_id=job_id)

    async def list_jobs(
        self,
        *,
        status: str | None = None,
        dispatch_type: str | None = None,
        limit: int = 50,
    ) -> list[WorkflowJob]:
        return await self._workflow_port.list_jobs(
            status=status,
            dispatch_type=dispatch_type,
            limit=limit,
        )

    async def list_events(self, *, job_id: int):
        return await self._workflow_port.list_events(job_id=job_id)

    async def append_event(
        self,
        *,
        job_id: int,
        event_type: str,
        event_payload: dict[str, Any] | None = None,
    ):
        return await self._workflow_port.append_event(
            job_id=job_id,
            event_type=event_type,
            event_payload=event_payload,
        )

    async def _transition(
        self,
        *,
        job_id: int,
        to_status: str,
        event_payload: dict[str, Any] | None,
    ) -> WorkflowJob:
        current = await self._workflow_port.get_job(job_id=job_id)
        if current is None:
            raise LookupError(f"workflow job not found: job_id={job_id}")
        from_status = current.status
        allowed = _ALLOWED_TRANSITIONS.get(from_status, set())
        if to_status not in allowed:
            raise WorkflowTransitionError(
                job_id=job_id,
                from_status=from_status,
                to_status=to_status,
            )
        payload = dict(event_payload or {})
        payload.setdefault("fromStatus", from_status)
        payload.setdefault("toStatus", to_status)
        return await self._workflow_port.transition_status(
            job_id=job_id,
            status=to_status,
            event_type=WORKFLOW_EVENT_STATUS_CHANGED,
            event_payload=payload,
        )
