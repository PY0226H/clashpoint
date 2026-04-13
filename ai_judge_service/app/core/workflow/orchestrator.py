from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.domain.workflow import (
    WORKFLOW_EVENT_REGISTERED,
    WORKFLOW_EVENT_STATUS_CHANGED,
    WORKFLOW_STATUS_CASE_BUILT,
    WORKFLOW_STATUS_COMPLETED,
    WORKFLOW_STATUS_FAILED,
    WORKFLOW_STATUS_QUEUED,
    WORKFLOW_STATUS_REVIEW_REQUIRED,
    WORKFLOW_STATUS_RUNNING,
    WorkflowJob,
    WorkflowPort,
)

from .errors import WorkflowTransitionError

_ALLOWED_TRANSITIONS = {
    WORKFLOW_STATUS_QUEUED: {
        WORKFLOW_STATUS_CASE_BUILT,
        WORKFLOW_STATUS_RUNNING,
        WORKFLOW_STATUS_REVIEW_REQUIRED,
        WORKFLOW_STATUS_FAILED,
    },
    WORKFLOW_STATUS_CASE_BUILT: {
        WORKFLOW_STATUS_RUNNING,
        WORKFLOW_STATUS_REVIEW_REQUIRED,
        WORKFLOW_STATUS_FAILED,
        WORKFLOW_STATUS_COMPLETED,
    },
    WORKFLOW_STATUS_RUNNING: {
        WORKFLOW_STATUS_REVIEW_REQUIRED,
        WORKFLOW_STATUS_FAILED,
        WORKFLOW_STATUS_COMPLETED,
    },
    WORKFLOW_STATUS_REVIEW_REQUIRED: {
        WORKFLOW_STATUS_RUNNING,
        WORKFLOW_STATUS_FAILED,
        WORKFLOW_STATUS_COMPLETED,
    },
    WORKFLOW_STATUS_COMPLETED: set(),
    WORKFLOW_STATUS_FAILED: set(),
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

    async def mark_running(
        self,
        *,
        job_id: int,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        return await self._transition(
            job_id=job_id,
            to_status=WORKFLOW_STATUS_RUNNING,
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

    async def mark_completed(
        self,
        *,
        job_id: int,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob:
        return await self._transition(
            job_id=job_id,
            to_status=WORKFLOW_STATUS_COMPLETED,
            event_payload=event_payload,
        )

    async def mark_failed(
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
            to_status=WORKFLOW_STATUS_FAILED,
            event_payload=payload,
        )

    async def get_job(self, *, job_id: int) -> WorkflowJob | None:
        return await self._workflow_port.get_job(job_id=job_id)

    async def list_events(self, *, job_id: int):
        return await self._workflow_port.list_events(job_id=job_id)

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
