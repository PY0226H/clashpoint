from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from .models import AuditAlert, DispatchReceipt, ReplayRecord


class JudgeFactPort(Protocol):
    async def upsert_dispatch_receipt(self, *, receipt: DispatchReceipt) -> DispatchReceipt: ...

    async def get_dispatch_receipt(
        self,
        *,
        dispatch_type: str,
        job_id: int,
    ) -> DispatchReceipt | None: ...

    async def list_dispatch_receipts(
        self,
        *,
        dispatch_type: str,
        session_id: int | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> list[DispatchReceipt]: ...

    async def append_replay_record(
        self,
        *,
        dispatch_type: str,
        job_id: int,
        trace_id: str,
        winner: str | None,
        needs_draw_vote: bool | None,
        provider: str | None,
        report_payload: dict[str, Any] | None,
    ) -> ReplayRecord: ...

    async def list_replay_records(
        self,
        *,
        dispatch_type: str | None = None,
        job_id: int | None = None,
        limit: int = 100,
    ) -> list[ReplayRecord]: ...

    async def upsert_audit_alert(
        self,
        *,
        job_id: int,
        scope_id: int,
        trace_id: str,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        details: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> AuditAlert: ...

    async def transition_audit_alert(
        self,
        *,
        alert_id: str,
        to_status: str,
        now: datetime | None = None,
    ) -> AuditAlert | None: ...

    async def list_audit_alerts(
        self,
        *,
        job_id: int | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[AuditAlert]: ...
