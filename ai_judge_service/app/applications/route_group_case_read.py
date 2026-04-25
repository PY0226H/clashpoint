from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Header, Query

from .case_courtroom_views import (
    build_case_evidence_view as build_case_evidence_view_v3,
)
from .case_courtroom_views import (
    build_courtroom_case_sort_key as build_courtroom_case_sort_key_v3,
)
from .case_courtroom_views import (
    build_courtroom_drilldown_action_hints as build_courtroom_drilldown_action_hints_v3,
)
from .case_courtroom_views import (
    build_evidence_claim_action_hints as build_evidence_claim_action_hints_v3,
)
from .case_courtroom_views import (
    build_evidence_claim_ops_profile as build_evidence_claim_ops_profile_v3,
)
from .case_courtroom_views import (
    build_evidence_claim_queue_sort_key as build_evidence_claim_queue_sort_key_v3,
)
from .case_courtroom_views import (
    normalize_courtroom_case_sort_by as normalize_courtroom_case_sort_by_v3,
)
from .case_courtroom_views import (
    normalize_courtroom_case_sort_order as normalize_courtroom_case_sort_order_v3,
)
from .case_courtroom_views import (
    normalize_evidence_claim_queue_sort_by as normalize_evidence_claim_queue_sort_by_v3,
)
from .case_courtroom_views import (
    normalize_evidence_claim_queue_sort_order as normalize_evidence_claim_queue_sort_order_v3,
)
from .case_courtroom_views import (
    normalize_evidence_claim_reliability_level as normalize_evidence_claim_reliability_level_v3,
)
from .case_courtroom_views import (
    serialize_claim_ledger_record as serialize_claim_ledger_record_v3,
)
from .case_read_routes import (
    build_case_claim_ledger_route_payload as build_case_claim_ledger_route_payload_v3,
)
from .case_read_routes import (
    build_case_courtroom_cases_route_payload as build_case_courtroom_cases_route_payload_v3,
)
from .case_read_routes import (
    build_case_courtroom_drilldown_bundle_route_payload as build_case_courtroom_drilldown_bundle_route_payload_v3,
)
from .case_read_routes import (
    build_case_courtroom_read_model_payload as build_case_courtroom_read_model_payload_v3,
)
from .case_read_routes import (
    build_case_courtroom_read_model_route_payload as build_case_courtroom_read_model_route_payload_v3,
)
from .case_read_routes import (
    build_case_evidence_claim_ops_queue_route_payload as build_case_evidence_claim_ops_queue_route_payload_v3,
)
from .case_read_routes import (
    build_case_overview_payload as build_case_overview_payload_v3,
)
from .case_read_routes import (
    build_case_overview_replay_items as build_case_overview_replay_items_v3,
)
from .case_read_routes import (
    build_case_overview_route_payload as build_case_overview_route_payload_v3,
)
from .replay_audit_ops import build_verdict_contract as build_verdict_contract_v3
from .replay_audit_ops import serialize_alert_item as serialize_alert_item_v3
from .replay_audit_ops import (
    serialize_dispatch_receipt as serialize_dispatch_receipt_v3,
)
from .review_alert_routes import (
    normalize_review_case_risk_level as normalize_review_case_risk_level_v3,
)
from .review_alert_routes import (
    normalize_review_case_sla_bucket as normalize_review_case_sla_bucket_v3,
)

AsyncPayloadFn = Callable[..., Awaitable[dict[str, Any]]]
CaseReadRouteGuardFn = Callable[[Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]]
RequireInternalKeyFn = Callable[[Any, str | None], None]
ValidateContractFn = Callable[[dict[str, Any]], None]
ValidateOrRaiseFn = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class CaseReadRouteHandles:
    get_judge_case: AsyncPayloadFn
    get_judge_case_claim_ledger: AsyncPayloadFn
    get_judge_case_courtroom_read_model: AsyncPayloadFn
    list_judge_courtroom_cases: AsyncPayloadFn
    list_judge_courtroom_drilldown_bundle: AsyncPayloadFn
    list_judge_evidence_claim_ops_queue: AsyncPayloadFn


@dataclass(frozen=True)
class CaseReadRouteDependencies:
    runtime: Any
    require_internal_key_fn: RequireInternalKeyFn
    run_case_read_route_guard: CaseReadRouteGuardFn
    validate_contract_or_raise_http_500: ValidateOrRaiseFn
    workflow_get_job: AsyncPayloadFn
    workflow_list_events: AsyncPayloadFn
    get_dispatch_receipt: Callable[..., Awaitable[Any | None]]
    trace_get: Callable[..., Any]
    list_replay_records: Callable[..., Awaitable[list[Any]]]
    list_audit_alerts: Callable[..., Awaitable[list[Any]]]
    get_claim_ledger_record: Callable[..., Awaitable[Any | None]]
    list_claim_ledger_records: Callable[..., Awaitable[list[Any]]]
    resolve_report_context_for_case: Callable[..., Awaitable[dict[str, Any]]]
    workflow_list_jobs: Callable[..., Awaitable[list[Any]]]
    build_judge_core_view: Callable[..., dict[str, Any]]
    build_review_case_risk_profile: Callable[..., dict[str, Any]]
    build_courtroom_read_model_view: Callable[..., dict[str, Any]]
    build_courtroom_read_model_light_summary: Callable[..., dict[str, Any]]
    build_courtroom_drilldown_bundle_view: Callable[..., dict[str, Any]]
    serialize_workflow_job: Callable[[Any], dict[str, Any]]
    normalize_workflow_status: Callable[[str | None], str | None]
    workflow_statuses: set[str]
    normalize_query_datetime: Callable[[datetime | str | None], datetime | None]
    review_case_risk_level_values: set[str]
    review_case_sla_bucket_values: set[str]
    courtroom_case_sort_fields: set[str]
    evidence_claim_reliability_level_values: set[str]
    evidence_claim_queue_sort_fields: set[str]
    validate_case_overview_contract: ValidateContractFn
    validate_courtroom_read_model_contract: ValidateContractFn
    validate_courtroom_drilldown_bundle_contract: ValidateContractFn
    validate_evidence_claim_ops_queue_contract: ValidateContractFn
    get_trust_registry_snapshot: Callable[..., Awaitable[Any | None]] | None = None


def register_case_read_routes(
    *,
    app: FastAPI,
    deps: CaseReadRouteDependencies,
) -> CaseReadRouteHandles:
    runtime = deps.runtime

    @app.get("/internal/judge/cases/{case_id}")
    async def get_judge_case(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        payload = await deps.run_case_read_route_guard(
            build_case_overview_route_payload_v3(
                case_id=case_id,
                workflow_get_job=deps.workflow_get_job,
                workflow_list_events=deps.workflow_list_events,
                get_dispatch_receipt=deps.get_dispatch_receipt,
                trace_get=deps.trace_get,
                list_replay_records=deps.list_replay_records,
                list_audit_alerts=deps.list_audit_alerts,
                get_claim_ledger_record=deps.get_claim_ledger_record,
                build_verdict_contract=build_verdict_contract_v3,
                build_case_evidence_view=build_case_evidence_view_v3,
                build_judge_core_view=deps.build_judge_core_view,
                build_case_overview_replay_items=build_case_overview_replay_items_v3,
                build_case_overview_payload=build_case_overview_payload_v3,
                serialize_workflow_job=deps.serialize_workflow_job,
                serialize_dispatch_receipt=serialize_dispatch_receipt_v3,
                serialize_alert_item=serialize_alert_item_v3,
                get_trust_registry_snapshot=deps.get_trust_registry_snapshot,
            )
        )
        return deps.validate_contract_or_raise_http_500(
            payload=payload,
            validate_contract=deps.validate_case_overview_contract,
            code="case_overview_contract_violation",
        )

    @app.get("/internal/judge/cases/{case_id}/claim-ledger")
    async def get_judge_case_claim_ledger(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
        limit: int = Query(default=20, ge=1, le=200),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.run_case_read_route_guard(
            build_case_claim_ledger_route_payload_v3(
                case_id=case_id,
                dispatch_type=dispatch_type,
                limit=limit,
                list_claim_ledger_records=deps.list_claim_ledger_records,
                get_claim_ledger_record=deps.get_claim_ledger_record,
                serialize_claim_ledger_record=serialize_claim_ledger_record_v3,
            )
        )

    @app.get("/internal/judge/cases/{case_id}/courtroom-read-model")
    async def get_judge_case_courtroom_read_model(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
        include_events: bool = Query(default=False),
        include_alerts: bool = Query(default=True),
        alert_limit: int = Query(default=200, ge=1, le=500),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        response_payload = await deps.run_case_read_route_guard(
            build_case_courtroom_read_model_route_payload_v3(
                case_id=case_id,
                dispatch_type=dispatch_type,
                include_events=include_events,
                include_alerts=include_alerts,
                alert_limit=alert_limit,
                resolve_report_context_for_case=deps.resolve_report_context_for_case,
                workflow_get_job=deps.workflow_get_job,
                workflow_list_events=deps.workflow_list_events,
                trace_get=deps.trace_get,
                get_claim_ledger_record=deps.get_claim_ledger_record,
                build_verdict_contract=build_verdict_contract_v3,
                build_case_evidence_view=build_case_evidence_view_v3,
                build_courtroom_read_model_view=deps.build_courtroom_read_model_view,
                build_judge_core_view=deps.build_judge_core_view,
                list_audit_alerts=deps.list_audit_alerts,
                build_case_courtroom_read_model_payload=(
                    build_case_courtroom_read_model_payload_v3
                ),
                serialize_workflow_job=deps.serialize_workflow_job,
                serialize_alert_item=serialize_alert_item_v3,
            )
        )
        return deps.validate_contract_or_raise_http_500(
            payload=response_payload,
            validate_contract=deps.validate_courtroom_read_model_contract,
            code="courtroom_read_model_contract_violation",
        )

    @app.get("/internal/judge/courtroom/cases")
    async def list_judge_courtroom_cases(
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        dispatch_type: str = Query(default="auto"),
        winner: str | None = Query(default=None),
        review_required: bool | None = Query(default=None),
        risk_level: str | None = Query(default=None),
        sla_bucket: str | None = Query(default=None),
        updated_from: datetime | None = Query(default=None),
        updated_to: datetime | None = Query(default=None),
        sort_by: str = Query(default="updated_at"),
        sort_order: str = Query(default="desc"),
        scan_limit: int = Query(default=500, ge=20, le=2000),
        offset: int = Query(default=0, ge=0, le=5000),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.run_case_read_route_guard(
            build_case_courtroom_cases_route_payload_v3(
                status=status,
                dispatch_type=dispatch_type,
                winner=winner,
                review_required=review_required,
                risk_level=risk_level,
                sla_bucket=sla_bucket,
                updated_from=updated_from,
                updated_to=updated_to,
                sort_by=sort_by,
                sort_order=sort_order,
                scan_limit=scan_limit,
                offset=offset,
                limit=limit,
                normalize_workflow_status=deps.normalize_workflow_status,
                workflow_statuses=deps.workflow_statuses,
                normalize_review_case_risk_level=normalize_review_case_risk_level_v3,
                review_case_risk_level_values=deps.review_case_risk_level_values,
                normalize_review_case_sla_bucket=normalize_review_case_sla_bucket_v3,
                review_case_sla_bucket_values=deps.review_case_sla_bucket_values,
                normalize_query_datetime=deps.normalize_query_datetime,
                normalize_courtroom_case_sort_by=normalize_courtroom_case_sort_by_v3,
                normalize_courtroom_case_sort_order=normalize_courtroom_case_sort_order_v3,
                courtroom_case_sort_fields=deps.courtroom_case_sort_fields,
                workflow_list_jobs=deps.workflow_list_jobs,
                resolve_report_context_for_case=deps.resolve_report_context_for_case,
                trace_get=deps.trace_get,
                build_review_case_risk_profile=deps.build_review_case_risk_profile,
                build_verdict_contract=build_verdict_contract_v3,
                build_case_evidence_view=build_case_evidence_view_v3,
                build_courtroom_read_model_view=deps.build_courtroom_read_model_view,
                serialize_workflow_job=deps.serialize_workflow_job,
                build_courtroom_read_model_light_summary=(
                    deps.build_courtroom_read_model_light_summary
                ),
                build_courtroom_case_sort_key=build_courtroom_case_sort_key_v3,
            )
        )

    @app.get("/internal/judge/courtroom/drilldown-bundle")
    async def list_judge_courtroom_drilldown_bundle(
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        dispatch_type: str = Query(default="auto"),
        winner: str | None = Query(default=None),
        review_required: bool | None = Query(default=None),
        risk_level: str | None = Query(default=None),
        sla_bucket: str | None = Query(default=None),
        updated_from: datetime | None = Query(default=None),
        updated_to: datetime | None = Query(default=None),
        sort_by: str = Query(default="updated_at"),
        sort_order: str = Query(default="desc"),
        scan_limit: int = Query(default=500, ge=20, le=2000),
        offset: int = Query(default=0, ge=0, le=5000),
        limit: int = Query(default=50, ge=1, le=200),
        claim_preview_limit: int = Query(default=10, ge=1, le=100),
        evidence_preview_limit: int = Query(default=10, ge=1, le=100),
        panel_preview_limit: int = Query(default=10, ge=1, le=100),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        payload = await deps.run_case_read_route_guard(
            build_case_courtroom_drilldown_bundle_route_payload_v3(
                status=status,
                dispatch_type=dispatch_type,
                winner=winner,
                review_required=review_required,
                risk_level=risk_level,
                sla_bucket=sla_bucket,
                updated_from=updated_from,
                updated_to=updated_to,
                sort_by=sort_by,
                sort_order=sort_order,
                scan_limit=scan_limit,
                offset=offset,
                limit=limit,
                claim_preview_limit=claim_preview_limit,
                evidence_preview_limit=evidence_preview_limit,
                panel_preview_limit=panel_preview_limit,
                normalize_workflow_status=deps.normalize_workflow_status,
                workflow_statuses=deps.workflow_statuses,
                normalize_review_case_risk_level=normalize_review_case_risk_level_v3,
                review_case_risk_level_values=deps.review_case_risk_level_values,
                normalize_review_case_sla_bucket=normalize_review_case_sla_bucket_v3,
                review_case_sla_bucket_values=deps.review_case_sla_bucket_values,
                normalize_query_datetime=deps.normalize_query_datetime,
                normalize_courtroom_case_sort_by=normalize_courtroom_case_sort_by_v3,
                normalize_courtroom_case_sort_order=normalize_courtroom_case_sort_order_v3,
                courtroom_case_sort_fields=deps.courtroom_case_sort_fields,
                workflow_list_jobs=deps.workflow_list_jobs,
                resolve_report_context_for_case=deps.resolve_report_context_for_case,
                trace_get=deps.trace_get,
                build_review_case_risk_profile=deps.build_review_case_risk_profile,
                build_verdict_contract=build_verdict_contract_v3,
                build_case_evidence_view=build_case_evidence_view_v3,
                build_courtroom_read_model_view=deps.build_courtroom_read_model_view,
                build_courtroom_drilldown_bundle_view=(
                    deps.build_courtroom_drilldown_bundle_view
                ),
                build_courtroom_drilldown_action_hints=(
                    build_courtroom_drilldown_action_hints_v3
                ),
                serialize_workflow_job=deps.serialize_workflow_job,
                build_courtroom_case_sort_key=build_courtroom_case_sort_key_v3,
            )
        )
        return deps.validate_contract_or_raise_http_500(
            payload=payload,
            validate_contract=deps.validate_courtroom_drilldown_bundle_contract,
            code="courtroom_drilldown_bundle_contract_violation",
        )

    @app.get("/internal/judge/evidence-claim/ops-queue")
    async def list_judge_evidence_claim_ops_queue(
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        dispatch_type: str = Query(default="auto"),
        winner: str | None = Query(default=None),
        review_required: bool | None = Query(default=None),
        risk_level: str | None = Query(default=None),
        sla_bucket: str | None = Query(default=None),
        reliability_level: str | None = Query(default=None),
        has_conflict: bool | None = Query(default=None),
        has_unanswered_claim: bool | None = Query(default=None),
        updated_from: datetime | None = Query(default=None),
        updated_to: datetime | None = Query(default=None),
        sort_by: str = Query(default="updated_at"),
        sort_order: str = Query(default="desc"),
        scan_limit: int = Query(default=500, ge=20, le=2000),
        offset: int = Query(default=0, ge=0, le=5000),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        payload = await deps.run_case_read_route_guard(
            build_case_evidence_claim_ops_queue_route_payload_v3(
                status=status,
                dispatch_type=dispatch_type,
                winner=winner,
                review_required=review_required,
                risk_level=risk_level,
                sla_bucket=sla_bucket,
                reliability_level=reliability_level,
                has_conflict=has_conflict,
                has_unanswered_claim=has_unanswered_claim,
                updated_from=updated_from,
                updated_to=updated_to,
                sort_by=sort_by,
                sort_order=sort_order,
                scan_limit=scan_limit,
                offset=offset,
                limit=limit,
                normalize_workflow_status=deps.normalize_workflow_status,
                workflow_statuses=deps.workflow_statuses,
                normalize_review_case_risk_level=normalize_review_case_risk_level_v3,
                review_case_risk_level_values=deps.review_case_risk_level_values,
                normalize_review_case_sla_bucket=normalize_review_case_sla_bucket_v3,
                review_case_sla_bucket_values=deps.review_case_sla_bucket_values,
                normalize_evidence_claim_reliability_level=(
                    normalize_evidence_claim_reliability_level_v3
                ),
                evidence_claim_reliability_level_values=(
                    deps.evidence_claim_reliability_level_values
                ),
                normalize_query_datetime=deps.normalize_query_datetime,
                normalize_evidence_claim_queue_sort_by=(
                    normalize_evidence_claim_queue_sort_by_v3
                ),
                normalize_evidence_claim_queue_sort_order=(
                    normalize_evidence_claim_queue_sort_order_v3
                ),
                evidence_claim_queue_sort_fields=deps.evidence_claim_queue_sort_fields,
                workflow_list_jobs=deps.workflow_list_jobs,
                resolve_report_context_for_case=deps.resolve_report_context_for_case,
                trace_get=deps.trace_get,
                build_review_case_risk_profile=deps.build_review_case_risk_profile,
                build_verdict_contract=build_verdict_contract_v3,
                build_case_evidence_view=build_case_evidence_view_v3,
                build_courtroom_read_model_view=deps.build_courtroom_read_model_view,
                build_courtroom_read_model_light_summary=(
                    deps.build_courtroom_read_model_light_summary
                ),
                build_evidence_claim_ops_profile=build_evidence_claim_ops_profile_v3,
                build_evidence_claim_action_hints=build_evidence_claim_action_hints_v3,
                serialize_workflow_job=deps.serialize_workflow_job,
                build_evidence_claim_queue_sort_key=(
                    build_evidence_claim_queue_sort_key_v3
                ),
            )
        )
        return deps.validate_contract_or_raise_http_500(
            payload=payload,
            validate_contract=deps.validate_evidence_claim_ops_queue_contract,
            code="evidence_claim_ops_queue_contract_violation",
        )

    return CaseReadRouteHandles(
        get_judge_case=get_judge_case,
        get_judge_case_claim_ledger=get_judge_case_claim_ledger,
        get_judge_case_courtroom_read_model=get_judge_case_courtroom_read_model,
        list_judge_courtroom_cases=list_judge_courtroom_cases,
        list_judge_courtroom_drilldown_bundle=list_judge_courtroom_drilldown_bundle,
        list_judge_evidence_claim_ops_queue=list_judge_evidence_claim_ops_queue,
    )
