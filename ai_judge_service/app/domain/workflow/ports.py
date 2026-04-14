from __future__ import annotations

from typing import Any, Protocol

from .models import WorkflowEvent, WorkflowJob


class WorkflowPort(Protocol):
    async def register_job(
        self,
        *,
        job: WorkflowJob,
        event_type: str,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob: ...

    async def transition_status(
        self,
        *,
        job_id: int,
        status: str,
        event_type: str,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowJob: ...

    async def append_event(
        self,
        *,
        job_id: int,
        event_type: str,
        event_payload: dict[str, Any] | None = None,
    ) -> WorkflowEvent: ...

    async def get_job(self, *, job_id: int) -> WorkflowJob | None: ...

    async def list_jobs(
        self,
        *,
        status: str | None = None,
        dispatch_type: str | None = None,
        limit: int = 50,
    ) -> list[WorkflowJob]: ...

    async def list_events(self, *, job_id: int) -> list[WorkflowEvent]: ...
