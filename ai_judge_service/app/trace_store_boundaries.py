from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


def _normalize_dispatch_type(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    return normalized or None


def _iso_datetime(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return None


def _payload_from_object(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    to_payload = getattr(value, "to_payload", None)
    if callable(to_payload):
        payload = to_payload()
        return dict(payload) if isinstance(payload, dict) else {}
    return dict(value) if isinstance(value, dict) else {}


def _record_item_presence(value: Any) -> bool:
    return bool(_payload_from_object(value))


def _serialize_replay_item(row: Any) -> dict[str, Any]:
    return {
        "dispatchType": getattr(row, "dispatch_type", None),
        "traceId": getattr(row, "trace_id", None),
        "winner": getattr(row, "winner", None),
        "needsDrawVote": getattr(row, "needs_draw_vote", None),
        "provider": getattr(row, "provider", None),
        "createdAt": _iso_datetime(getattr(row, "created_at", None)),
    }


def _serialize_workflow_event(row: Any) -> dict[str, Any]:
    return {
        "eventSeq": getattr(row, "event_seq", None),
        "eventType": getattr(row, "event_type", None),
        "createdAt": _iso_datetime(getattr(row, "created_at", None)),
    }


@dataclass(frozen=True)
class TraceWriteStore:
    store: Any

    def register_start(self, **kwargs: Any) -> Any:
        return self.store.register_start(**kwargs)

    def register_success(self, **kwargs: Any) -> Any:
        return self.store.register_success(**kwargs)

    def register_failure(self, **kwargs: Any) -> Any:
        return self.store.register_failure(**kwargs)

    def resolve_idempotency(self, **kwargs: Any) -> Any:
        return self.store.resolve_idempotency(**kwargs)

    def set_idempotency_success(self, **kwargs: Any) -> Any:
        return self.store.set_idempotency_success(**kwargs)

    def clear_idempotency(self, *args: Any, **kwargs: Any) -> Any:
        return self.store.clear_idempotency(*args, **kwargs)

    def save_dispatch_receipt(self, **kwargs: Any) -> Any:
        return self.store.save_dispatch_receipt(**kwargs)


@dataclass(frozen=True)
class ReplayStore:
    store: Any
    fact_repository: Any | None = None

    def mark_replay(self, **kwargs: Any) -> Any:
        return self.store.mark_replay(**kwargs)

    async def append_record(self, **kwargs: Any) -> Any:
        if self.fact_repository is None:
            raise RuntimeError("replay_fact_repository_not_configured")
        return await self.fact_repository.append_replay_record(**kwargs)

    async def list_records(
        self,
        *,
        job_id: int,
        dispatch_type: str | None = None,
        limit: int = 50,
    ) -> list[Any]:
        if self.fact_repository is None:
            return []
        return await self.fact_repository.list_replay_records(
            dispatch_type=dispatch_type,
            job_id=job_id,
            limit=limit,
        )


@dataclass(frozen=True)
class AuditAlertStore:
    store: Any

    def upsert_alert(self, **kwargs: Any) -> Any:
        return self.store.upsert_audit_alert(**kwargs)

    def list_alerts(self, **kwargs: Any) -> list[Any]:
        return self.store.list_audit_alerts(**kwargs)

    def transition_alert(self, **kwargs: Any) -> Any:
        return self.store.transition_audit_alert(**kwargs)

    def list_outbox(self, **kwargs: Any) -> list[Any]:
        return self.store.list_alert_outbox(**kwargs)

    def mark_outbox_delivery(self, **kwargs: Any) -> Any:
        return self.store.mark_alert_outbox_delivery(**kwargs)


@dataclass(frozen=True)
class TraceReadModel:
    store: Any
    workflow_store: Any | None = None
    fact_repository: Any | None = None

    def get_trace(self, job_id: int) -> Any | None:
        return self.store.get_trace(job_id)

    def list_traces(self, **kwargs: Any) -> list[Any]:
        return self.store.list_traces(**kwargs)

    def get_dispatch_receipt(self, **kwargs: Any) -> Any | None:
        return self.store.get_dispatch_receipt(**kwargs)

    def list_dispatch_receipts(self, **kwargs: Any) -> list[Any]:
        return self.store.list_dispatch_receipts(**kwargs)

    async def build_case_chain_summary(
        self,
        *,
        job_id: int,
        dispatch_type: str | None = None,
        replay_limit: int = 20,
    ) -> dict[str, Any]:
        normalized_dispatch_type = _normalize_dispatch_type(dispatch_type)
        trace = self.get_trace(job_id)
        errors: list[str] = []
        workflow_job = None
        workflow_events: list[Any] = []
        ledger_snapshot = None
        claim_ledger = None
        replay_records: list[Any] = []

        if self.workflow_store is not None:
            try:
                workflow_job = await self.workflow_store.get_job(job_id=job_id)
                workflow_events = await self.workflow_store.list_events(job_id=job_id)
            except Exception as err:  # read model 不应因单个事实源暂不可用而遮蔽 trace 主体。
                errors.append(f"workflow:{type(err).__name__}")

        if self.fact_repository is not None:
            get_snapshot = getattr(self.fact_repository, "get_judge_ledger_snapshot", None)
            if callable(get_snapshot):
                try:
                    ledger_snapshot = await get_snapshot(
                        case_id=job_id,
                        dispatch_type=normalized_dispatch_type,
                    )
                except Exception as err:
                    errors.append(f"judge_ledger_snapshot:{type(err).__name__}")
            try:
                claim_ledger = await self.fact_repository.get_claim_ledger_record(
                    case_id=job_id,
                    dispatch_type=normalized_dispatch_type,
                )
            except Exception as err:
                errors.append(f"claim_ledger:{type(err).__name__}")
            try:
                replay_records = await self.fact_repository.list_replay_records(
                    dispatch_type=normalized_dispatch_type,
                    job_id=job_id,
                    limit=replay_limit,
                )
            except Exception as err:
                errors.append(f"replay_records:{type(err).__name__}")

        alert_rows = self.store.list_audit_alerts(job_id=job_id, limit=100)
        alert_status_counts: dict[str, int] = {}
        for row in alert_rows:
            status = str(getattr(row, "status", "") or "unknown")
            alert_status_counts[status] = alert_status_counts.get(status, 0) + 1

        object_presence = self._build_object_presence(
            ledger_snapshot=ledger_snapshot,
            claim_ledger=claim_ledger,
        )
        return {
            "version": "trace-replay-audit-read-model-v1",
            "caseId": int(job_id),
            "dispatchType": normalized_dispatch_type,
            "durableKeys": {
                "jobId": int(job_id),
                "traceId": (
                    str(getattr(trace, "trace_id", "") or "").strip()
                    if trace is not None
                    else str(getattr(workflow_job, "trace_id", "") or "").strip()
                ),
                "workflowJobPresent": workflow_job is not None,
                "judgeLedgerSnapshotPresent": ledger_snapshot is not None,
                "claimLedgerRecordPresent": claim_ledger is not None,
            },
            "trace": {
                "present": trace is not None,
                "status": getattr(trace, "status", None),
                "callbackStatus": getattr(trace, "callback_status", None),
                "callbackError": getattr(trace, "callback_error", None),
            },
            "workflow": {
                "present": workflow_job is not None,
                "status": getattr(workflow_job, "status", None),
                "eventCount": len(workflow_events),
                "events": [_serialize_workflow_event(row) for row in workflow_events],
            },
            "ledgerChain": {
                "source": self._resolve_ledger_source(
                    ledger_snapshot=ledger_snapshot,
                    claim_ledger=claim_ledger,
                ),
                "objectPresence": object_presence,
                "complete": all(object_presence.values()),
            },
            "replay": {
                "count": len(replay_records),
                "items": [_serialize_replay_item(row) for row in replay_records],
            },
            "audit": {
                "alertCount": len(alert_rows),
                "openAlertCount": sum(
                    1
                    for row in alert_rows
                    if str(getattr(row, "status", "") or "").lower() != "resolved"
                ),
                "statusCounts": alert_status_counts,
            },
            "errors": errors,
        }

    @staticmethod
    def _resolve_ledger_source(*, ledger_snapshot: Any | None, claim_ledger: Any | None) -> str:
        if ledger_snapshot is not None:
            return "judge_ledger_snapshots"
        if claim_ledger is not None:
            return "claim_ledger_records"
        return "missing"

    @staticmethod
    def _build_object_presence(
        *,
        ledger_snapshot: Any | None,
        claim_ledger: Any | None,
    ) -> dict[str, bool]:
        if ledger_snapshot is not None:
            return {
                "caseDossier": _record_item_presence(getattr(ledger_snapshot, "case_dossier", None)),
                "claimGraph": _record_item_presence(getattr(ledger_snapshot, "claim_graph", None)),
                "evidenceLedger": _record_item_presence(
                    getattr(ledger_snapshot, "evidence_ledger", None)
                ),
                "verdictLedger": _record_item_presence(
                    getattr(ledger_snapshot, "verdict_ledger", None)
                ),
                "fairnessReport": _record_item_presence(
                    getattr(ledger_snapshot, "fairness_report", None)
                ),
                "opinionPack": _record_item_presence(getattr(ledger_snapshot, "opinion_pack", None)),
            }
        return {
            "caseDossier": _record_item_presence(getattr(claim_ledger, "case_dossier", None)),
            "claimGraph": _record_item_presence(getattr(claim_ledger, "claim_graph", None)),
            "evidenceLedger": _record_item_presence(
                getattr(claim_ledger, "evidence_ledger", None)
            ),
            "verdictLedger": False,
            "fairnessReport": False,
            "opinionPack": False,
        }


@dataclass(frozen=True)
class TraceStoreBoundaries:
    write_store: TraceWriteStore
    read_model: TraceReadModel
    replay_store: ReplayStore
    audit_alert_store: AuditAlertStore


def build_trace_store_boundaries(
    *,
    trace_store: Any,
    workflow_store: Any | None = None,
    fact_repository: Any | None = None,
) -> TraceStoreBoundaries:
    return TraceStoreBoundaries(
        write_store=TraceWriteStore(store=trace_store),
        read_model=TraceReadModel(
            store=trace_store,
            workflow_store=workflow_store,
            fact_repository=fact_repository,
        ),
        replay_store=ReplayStore(
            store=trace_store,
            fact_repository=fact_repository,
        ),
        audit_alert_store=AuditAlertStore(store=trace_store),
    )


__all__ = [
    "AuditAlertStore",
    "ReplayStore",
    "TraceReadModel",
    "TraceStoreBoundaries",
    "TraceWriteStore",
    "build_trace_store_boundaries",
]
