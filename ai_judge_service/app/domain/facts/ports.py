from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from .models import (
    AuditAlert,
    ClaimLedgerRecord,
    DispatchReceipt,
    FairnessBenchmarkRun,
    FairnessCalibrationDecision,
    FairnessShadowRun,
    ReplayRecord,
)


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

    async def upsert_claim_ledger_record(
        self,
        *,
        case_id: int,
        dispatch_type: str,
        trace_id: str,
        case_dossier: dict[str, Any] | None,
        claim_graph: dict[str, Any] | None,
        claim_graph_summary: dict[str, Any] | None,
        evidence_ledger: dict[str, Any] | None,
        verdict_evidence_refs: list[dict[str, Any]] | None,
    ) -> ClaimLedgerRecord: ...

    async def get_claim_ledger_record(
        self,
        *,
        case_id: int,
        dispatch_type: str | None = None,
    ) -> ClaimLedgerRecord | None: ...

    async def list_claim_ledger_records(
        self,
        *,
        case_id: int,
        limit: int = 20,
    ) -> list[ClaimLedgerRecord]: ...

    async def upsert_fairness_benchmark_run(
        self,
        *,
        run_id: str,
        policy_version: str,
        environment_mode: str,
        status: str,
        threshold_decision: str,
        needs_real_env_reconfirm: bool,
        needs_remediation: bool,
        sample_size: int | None,
        draw_rate: float | None,
        side_bias_delta: float | None,
        appeal_overturn_rate: float | None,
        thresholds: dict[str, Any] | None,
        metrics: dict[str, Any] | None,
        summary: dict[str, Any] | None,
        source: str | None,
        reported_by: str | None,
        reported_at: datetime | None = None,
    ) -> FairnessBenchmarkRun: ...

    async def list_fairness_benchmark_runs(
        self,
        *,
        policy_version: str | None = None,
        environment_mode: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[FairnessBenchmarkRun]: ...

    async def upsert_fairness_shadow_run(
        self,
        *,
        run_id: str,
        policy_version: str,
        benchmark_run_id: str | None,
        environment_mode: str,
        status: str,
        threshold_decision: str,
        needs_real_env_reconfirm: bool,
        needs_remediation: bool,
        sample_size: int | None,
        winner_flip_rate: float | None,
        score_shift_delta: float | None,
        review_required_delta: float | None,
        thresholds: dict[str, Any] | None,
        metrics: dict[str, Any] | None,
        summary: dict[str, Any] | None,
        source: str | None,
        reported_by: str | None,
        reported_at: datetime | None = None,
    ) -> FairnessShadowRun: ...

    async def list_fairness_shadow_runs(
        self,
        *,
        policy_version: str | None = None,
        benchmark_run_id: str | None = None,
        environment_mode: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[FairnessShadowRun]: ...

    async def append_fairness_calibration_decision(
        self,
        *,
        version: str,
        decision_id: str,
        source_recommendation_id: str,
        policy_version: str,
        decision: str,
        actor: dict[str, Any],
        reason_code: str,
        evidence_refs: list[dict[str, Any]],
        visibility: dict[str, Any],
        release_gate_input: dict[str, Any],
        created_at: datetime | None = None,
    ) -> FairnessCalibrationDecision: ...

    async def list_fairness_calibration_decisions(
        self,
        *,
        policy_version: str | None = None,
        source_recommendation_id: str | None = None,
        decision: str | None = None,
        limit: int = 50,
    ) -> list[FairnessCalibrationDecision]: ...

    async def upsert_audit_alert(
        self,
        *,
        alert_id: str | None = None,
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
