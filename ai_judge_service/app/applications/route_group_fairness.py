from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Header, Query, Request

from .fairness_analysis import (
    build_fairness_calibration_drift_summary as build_fairness_calibration_drift_summary_v3,
)
from .fairness_analysis import (
    build_fairness_calibration_risk_items as build_fairness_calibration_risk_items_v3,
)
from .fairness_analysis import (
    build_fairness_calibration_threshold_suggestions as build_fairness_calibration_threshold_suggestions_v3,
)
from .fairness_analysis import (
    build_fairness_dashboard_case_trends as build_fairness_dashboard_case_trends_v3,
)
from .fairness_analysis import (
    build_fairness_dashboard_run_trends as build_fairness_dashboard_run_trends_v3,
)
from .fairness_analysis import (
    build_fairness_dashboard_top_risk_cases as build_fairness_dashboard_top_risk_cases_v3,
)
from .fairness_calibration_decision_log import (
    InMemoryFairnessCalibrationDecisionLogStore,
    build_fairness_calibration_decision_create_payload,
    build_fairness_calibration_decision_list_payload,
)
from .fairness_case_scan import (
    collect_fairness_case_items as collect_fairness_case_items_v3,
)
from .fairness_runtime_routes import FairnessRouteError
from .fairness_runtime_routes import (
    build_case_fairness_sort_key as build_case_fairness_sort_key_v3,
)
from .fairness_runtime_routes import (
    build_fairness_benchmark_list_payload as build_fairness_benchmark_list_payload_v3,
)
from .fairness_runtime_routes import (
    build_fairness_benchmark_upsert_payload as build_fairness_benchmark_upsert_payload_v3,
)
from .fairness_runtime_routes import (
    build_fairness_calibration_on_env_input_template as build_fairness_calibration_on_env_input_template_v3,
)
from .fairness_runtime_routes import (
    build_fairness_calibration_pack_payload as build_fairness_calibration_pack_payload_v3,
)
from .fairness_runtime_routes import (
    build_fairness_case_detail_payload as build_fairness_case_detail_payload_v3,
)
from .fairness_runtime_routes import (
    build_fairness_case_list_payload as build_fairness_case_list_payload_v3,
)
from .fairness_runtime_routes import (
    build_fairness_dashboard_payload as build_fairness_dashboard_payload_v3,
)
from .fairness_runtime_routes import (
    build_fairness_policy_calibration_advisor_payload as build_fairness_policy_calibration_advisor_payload_v3,
)
from .fairness_runtime_routes import (
    build_fairness_policy_calibration_recommended_actions as build_fairness_policy_calibration_recommended_actions_v3,
)
from .fairness_runtime_routes import (
    build_fairness_shadow_list_payload as build_fairness_shadow_list_payload_v3,
)
from .fairness_runtime_routes import (
    build_fairness_shadow_upsert_payload as build_fairness_shadow_upsert_payload_v3,
)
from .fairness_runtime_routes import (
    normalize_case_fairness_challenge_state as normalize_case_fairness_challenge_state_v3,
)
from .fairness_runtime_routes import (
    normalize_case_fairness_gate_conclusion as normalize_case_fairness_gate_conclusion_v3,
)
from .fairness_runtime_routes import (
    normalize_case_fairness_sort_by as normalize_case_fairness_sort_by_v3,
)
from .fairness_runtime_routes import (
    normalize_case_fairness_sort_order as normalize_case_fairness_sort_order_v3,
)
from .judge_command_routes import extract_optional_bool as extract_optional_bool_v3
from .judge_command_routes import extract_optional_float as extract_optional_float_v3
from .judge_command_routes import extract_optional_int as extract_optional_int_v3
from .judge_command_routes import extract_optional_str as extract_optional_str_v3
from .replay_audit_ops import serialize_alert_item as serialize_alert_item_v3

AsyncPayloadFn = Callable[..., Awaitable[dict[str, Any]]]
FairnessRouteGuardFn = Callable[[Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]]
RequireInternalKeyFn = Callable[[Any, str | None], None]
ValidateContractFn = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class FairnessRouteHandles:
    upsert_judge_fairness_benchmark_run: AsyncPayloadFn
    list_judge_fairness_benchmark_runs: AsyncPayloadFn
    upsert_judge_fairness_shadow_run: AsyncPayloadFn
    list_judge_fairness_shadow_runs: AsyncPayloadFn
    get_judge_case_fairness: AsyncPayloadFn
    list_judge_case_fairness: AsyncPayloadFn
    get_judge_fairness_dashboard: AsyncPayloadFn
    get_judge_fairness_calibration_pack: AsyncPayloadFn
    get_judge_fairness_policy_calibration_advisor: AsyncPayloadFn
    create_judge_fairness_policy_calibration_decision: AsyncPayloadFn
    list_judge_fairness_policy_calibration_decisions: AsyncPayloadFn


@dataclass(frozen=True)
class FairnessRouteDependencies:
    runtime: Any
    require_internal_key_fn: RequireInternalKeyFn
    read_json_object_or_raise_422: Callable[..., Awaitable[dict[str, Any]]]
    run_fairness_route_guard: FairnessRouteGuardFn
    workflow_get_job: Callable[..., Awaitable[Any]]
    workflow_list_events: Callable[..., Awaitable[list[Any]]]
    workflow_list_jobs: Callable[..., Awaitable[list[Any]]]
    get_trace: Callable[..., Any]
    resolve_report_context_for_case: Callable[..., Awaitable[dict[str, Any]]]
    list_fairness_benchmark_runs: Callable[..., Awaitable[list[Any]]]
    list_fairness_shadow_runs: Callable[..., Awaitable[list[Any]]]
    upsert_fairness_benchmark_run: Callable[..., Awaitable[Any]]
    upsert_fairness_shadow_run: Callable[..., Awaitable[Any]]
    sync_audit_alert_to_facts: Callable[..., Awaitable[Any]]
    serialize_fairness_benchmark_run: Callable[[Any], dict[str, Any]]
    serialize_fairness_shadow_run: Callable[[Any], dict[str, Any]]
    build_case_fairness_item: Callable[..., dict[str, Any]]
    build_case_fairness_aggregations: Callable[[list[dict[str, Any]]], dict[str, Any]]
    evaluate_policy_release_fairness_gate: Callable[..., Awaitable[dict[str, Any]]]
    extract_optional_datetime: Callable[..., Any]
    normalize_workflow_status: Callable[[str | None], str | None]
    workflow_statuses: set[str] | frozenset[str]
    case_fairness_sort_fields: set[str] | frozenset[str]
    case_fairness_gate_conclusions: set[str] | frozenset[str]
    case_fairness_challenge_states: set[str] | frozenset[str]
    validate_case_fairness_detail_contract: ValidateContractFn
    validate_case_fairness_list_contract: ValidateContractFn
    validate_fairness_dashboard_contract: ValidateContractFn
    calibration_decision_log_store: Any | None = None


async def _build_fairness_calibration_pack_payload(
    *,
    x_ai_internal_key: str | None,
    dispatch_type: str | None,
    status: str | None,
    winner: str | None,
    policy_version: str | None,
    challenge_state: str | None,
    case_scan_limit: int,
    risk_limit: int,
    benchmark_limit: int,
    shadow_limit: int,
    deps: FairnessRouteDependencies,
    list_judge_case_fairness: AsyncPayloadFn,
) -> dict[str, Any]:
    return await build_fairness_calibration_pack_payload_v3(
        x_ai_internal_key=x_ai_internal_key,
        dispatch_type=dispatch_type,
        status=status,
        winner=winner,
        policy_version=policy_version,
        challenge_state=challenge_state,
        case_scan_limit=case_scan_limit,
        risk_limit=risk_limit,
        benchmark_limit=benchmark_limit,
        shadow_limit=shadow_limit,
        collect_fairness_case_items=collect_fairness_case_items_v3,
        list_judge_case_fairness=list_judge_case_fairness,
        list_fairness_benchmark_runs=deps.list_fairness_benchmark_runs,
        list_fairness_shadow_runs=deps.list_fairness_shadow_runs,
        build_fairness_dashboard_top_risk_cases=(
            build_fairness_dashboard_top_risk_cases_v3
        ),
        build_fairness_calibration_threshold_suggestions=(
            build_fairness_calibration_threshold_suggestions_v3
        ),
        build_fairness_calibration_drift_summary=(
            build_fairness_calibration_drift_summary_v3
        ),
        build_fairness_calibration_risk_items=build_fairness_calibration_risk_items_v3,
        build_fairness_calibration_on_env_input_template=(
            build_fairness_calibration_on_env_input_template_v3
        ),
    )


async def _build_fairness_policy_calibration_advisor_payload(
    *,
    x_ai_internal_key: str | None,
    dispatch_type: str | None,
    status: str | None,
    winner: str | None,
    policy_version: str | None,
    challenge_state: str | None,
    case_scan_limit: int,
    risk_limit: int,
    benchmark_limit: int,
    shadow_limit: int,
    deps: FairnessRouteDependencies,
    list_judge_case_fairness: AsyncPayloadFn,
    calibration_decision_log_store: Any,
) -> dict[str, Any]:
    payload = await build_fairness_policy_calibration_advisor_payload_v3(
        x_ai_internal_key=x_ai_internal_key,
        dispatch_type=dispatch_type,
        status=status,
        winner=winner,
        policy_version=policy_version,
        challenge_state=challenge_state,
        case_scan_limit=case_scan_limit,
        risk_limit=risk_limit,
        benchmark_limit=benchmark_limit,
        shadow_limit=shadow_limit,
        collect_fairness_case_items=collect_fairness_case_items_v3,
        list_judge_case_fairness=list_judge_case_fairness,
        list_fairness_benchmark_runs=deps.list_fairness_benchmark_runs,
        list_fairness_shadow_runs=deps.list_fairness_shadow_runs,
        build_fairness_dashboard_top_risk_cases=(
            build_fairness_dashboard_top_risk_cases_v3
        ),
        build_fairness_calibration_threshold_suggestions=(
            build_fairness_calibration_threshold_suggestions_v3
        ),
        build_fairness_calibration_drift_summary=(
            build_fairness_calibration_drift_summary_v3
        ),
        build_fairness_calibration_risk_items=build_fairness_calibration_risk_items_v3,
        evaluate_policy_release_fairness_gate=(
            deps.evaluate_policy_release_fairness_gate
        ),
        build_fairness_policy_calibration_recommended_actions=(
            build_fairness_policy_calibration_recommended_actions_v3
        ),
    )
    effective_policy_version = (
        (payload.get("filters") or {}).get("effectivePolicyVersion")
        or (payload.get("overview") or {}).get("policyVersion")
        or policy_version
    )
    decision_log = await build_fairness_calibration_decision_list_payload(
        store=calibration_decision_log_store,
        policy_version=effective_policy_version,
        source_recommendation_id=None,
        decision=None,
        limit=50,
    )
    payload["decisionLog"] = decision_log
    overview = payload.get("overview")
    if isinstance(overview, dict):
        summary = decision_log.get("summary") or {}
        release_gate_reference = decision_log.get("releaseGateReference") or {}
        overview["decisionCount"] = int(summary.get("totalCount") or 0)
        overview["acceptedForReviewDecisionCount"] = int(
            summary.get("acceptedForReviewCount") or 0
        )
        overview["productionReadyDecisionCount"] = int(
            summary.get("productionReadyDecisionCount") or 0
        )
        overview["decisionLogBlocksProductionReadyCount"] = int(
            release_gate_reference.get("blockingDecisionCount") or 0
        )
    return payload


def _raise_decision_log_error(err: ValueError) -> None:
    detail = str(err)
    status_code = 409 if detail == "duplicate_calibration_decision_id" else 422
    raise FairnessRouteError(status_code=status_code, detail=detail) from err


async def _guard_decision_log_value_errors(
    awaitable: Awaitable[dict[str, Any]],
) -> dict[str, Any]:
    try:
        return await awaitable
    except ValueError as err:
        _raise_decision_log_error(err)


def register_fairness_routes(
    *,
    app: FastAPI,
    deps: FairnessRouteDependencies,
) -> FairnessRouteHandles:
    runtime = deps.runtime
    calibration_decision_log_store = (
        deps.calibration_decision_log_store
        if deps.calibration_decision_log_store is not None
        else InMemoryFairnessCalibrationDecisionLogStore()
    )

    @app.post("/internal/judge/fairness/benchmark-runs")
    async def upsert_judge_fairness_benchmark_run(
        request: Request,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        raw_payload = await deps.read_json_object_or_raise_422(request=request)
        return await deps.run_fairness_route_guard(
            build_fairness_benchmark_upsert_payload_v3(
                raw_payload=raw_payload,
                extract_optional_int=extract_optional_int_v3,
                extract_optional_float=extract_optional_float_v3,
                extract_optional_str=extract_optional_str_v3,
                extract_optional_bool=extract_optional_bool_v3,
                extract_optional_datetime=deps.extract_optional_datetime,
                list_fairness_benchmark_runs=deps.list_fairness_benchmark_runs,
                upsert_fairness_benchmark_run=deps.upsert_fairness_benchmark_run,
                upsert_audit_alert=runtime.trace_store.upsert_audit_alert,
                sync_audit_alert_to_facts=deps.sync_audit_alert_to_facts,
                serialize_alert_item=serialize_alert_item_v3,
                serialize_fairness_benchmark_run=(
                    deps.serialize_fairness_benchmark_run
                ),
            )
        )

    @app.get("/internal/judge/fairness/benchmark-runs")
    async def list_judge_fairness_benchmark_runs(
        x_ai_internal_key: str | None = Header(default=None),
        policy_version: str | None = Query(default=None),
        environment_mode: str | None = Query(default=None),
        status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.run_fairness_route_guard(
            build_fairness_benchmark_list_payload_v3(
                policy_version=policy_version,
                environment_mode=environment_mode,
                status=status,
                limit=limit,
                list_fairness_benchmark_runs=deps.list_fairness_benchmark_runs,
                serialize_fairness_benchmark_run=(
                    deps.serialize_fairness_benchmark_run
                ),
            )
        )

    @app.post("/internal/judge/fairness/shadow-runs")
    async def upsert_judge_fairness_shadow_run(
        request: Request,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        raw_payload = await deps.read_json_object_or_raise_422(request=request)
        return await deps.run_fairness_route_guard(
            build_fairness_shadow_upsert_payload_v3(
                raw_payload=raw_payload,
                extract_optional_int=extract_optional_int_v3,
                extract_optional_float=extract_optional_float_v3,
                extract_optional_str=extract_optional_str_v3,
                extract_optional_bool=extract_optional_bool_v3,
                extract_optional_datetime=deps.extract_optional_datetime,
                list_fairness_benchmark_runs=deps.list_fairness_benchmark_runs,
                list_fairness_shadow_runs=deps.list_fairness_shadow_runs,
                upsert_fairness_shadow_run=deps.upsert_fairness_shadow_run,
                upsert_audit_alert=runtime.trace_store.upsert_audit_alert,
                sync_audit_alert_to_facts=deps.sync_audit_alert_to_facts,
                serialize_alert_item=serialize_alert_item_v3,
                serialize_fairness_shadow_run=deps.serialize_fairness_shadow_run,
            )
        )

    @app.get("/internal/judge/fairness/shadow-runs")
    async def list_judge_fairness_shadow_runs(
        x_ai_internal_key: str | None = Header(default=None),
        policy_version: str | None = Query(default=None),
        benchmark_run_id: str | None = Query(default=None),
        environment_mode: str | None = Query(default=None),
        status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.run_fairness_route_guard(
            build_fairness_shadow_list_payload_v3(
                policy_version=policy_version,
                benchmark_run_id=benchmark_run_id,
                environment_mode=environment_mode,
                status=status,
                limit=limit,
                list_fairness_shadow_runs=deps.list_fairness_shadow_runs,
                serialize_fairness_shadow_run=deps.serialize_fairness_shadow_run,
            )
        )

    @app.get("/internal/judge/fairness/cases/{case_id}")
    async def get_judge_case_fairness(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.run_fairness_route_guard(
            build_fairness_case_detail_payload_v3(
                case_id=case_id,
                dispatch_type=dispatch_type,
                resolve_report_context_for_case=deps.resolve_report_context_for_case,
                workflow_get_job=deps.workflow_get_job,
                workflow_list_events=deps.workflow_list_events,
                list_fairness_benchmark_runs=deps.list_fairness_benchmark_runs,
                list_fairness_shadow_runs=deps.list_fairness_shadow_runs,
                build_case_fairness_item=deps.build_case_fairness_item,
                validate_case_fairness_detail_contract=(
                    deps.validate_case_fairness_detail_contract
                ),
            )
        )

    @app.get("/internal/judge/fairness/cases")
    async def list_judge_case_fairness(
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        dispatch_type: str | None = Query(default=None),
        winner: str | None = Query(default=None),
        policy_version: str | None = Query(default=None),
        has_drift_breach: bool | None = Query(default=None),
        has_threshold_breach: bool | None = Query(default=None),
        has_shadow_breach: bool | None = Query(default=None),
        has_open_review: bool | None = Query(default=None),
        gate_conclusion: str | None = Query(default=None),
        challenge_state: str | None = Query(default=None),
        sort_by: str = Query(default="updated_at"),
        sort_order: str = Query(default="desc"),
        review_required: bool | None = Query(default=None),
        panel_high_disagreement: bool | None = Query(default=None),
        offset: int = Query(default=0, ge=0, le=2000),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.run_fairness_route_guard(
            build_fairness_case_list_payload_v3(
                status=status,
                dispatch_type=dispatch_type,
                winner=winner,
                policy_version=policy_version,
                has_drift_breach=has_drift_breach,
                has_threshold_breach=has_threshold_breach,
                has_shadow_breach=has_shadow_breach,
                has_open_review=has_open_review,
                gate_conclusion=gate_conclusion,
                challenge_state=challenge_state,
                sort_by=sort_by,
                sort_order=sort_order,
                review_required=review_required,
                panel_high_disagreement=panel_high_disagreement,
                offset=offset,
                limit=limit,
                normalize_workflow_status=deps.normalize_workflow_status,
                workflow_statuses=deps.workflow_statuses,
                normalize_case_fairness_sort_by=normalize_case_fairness_sort_by_v3,
                case_fairness_sort_fields=deps.case_fairness_sort_fields,
                normalize_case_fairness_sort_order=normalize_case_fairness_sort_order_v3,
                normalize_case_fairness_gate_conclusion=(
                    normalize_case_fairness_gate_conclusion_v3
                ),
                case_fairness_gate_conclusions=deps.case_fairness_gate_conclusions,
                normalize_case_fairness_challenge_state=(
                    normalize_case_fairness_challenge_state_v3
                ),
                case_fairness_challenge_states=deps.case_fairness_challenge_states,
                workflow_list_jobs=deps.workflow_list_jobs,
                get_trace=deps.get_trace,
                workflow_list_events=deps.workflow_list_events,
                list_fairness_benchmark_runs=deps.list_fairness_benchmark_runs,
                list_fairness_shadow_runs=deps.list_fairness_shadow_runs,
                build_case_fairness_item=deps.build_case_fairness_item,
                build_case_fairness_sort_key=build_case_fairness_sort_key_v3,
                build_case_fairness_aggregations=deps.build_case_fairness_aggregations,
                validate_case_fairness_list_contract=(
                    deps.validate_case_fairness_list_contract
                ),
            )
        )

    @app.get("/internal/judge/fairness/dashboard")
    async def get_judge_fairness_dashboard(
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        dispatch_type: str | None = Query(default="final"),
        winner: str | None = Query(default=None),
        policy_version: str | None = Query(default=None),
        challenge_state: str | None = Query(default=None),
        window_days: int = Query(default=7, ge=1, le=30),
        top_limit: int = Query(default=10, ge=1, le=50),
        case_scan_limit: int = Query(default=200, ge=20, le=1000),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.run_fairness_route_guard(
            build_fairness_dashboard_payload_v3(
                x_ai_internal_key=x_ai_internal_key,
                status=status,
                dispatch_type=dispatch_type,
                winner=winner,
                policy_version=policy_version,
                challenge_state=challenge_state,
                window_days=window_days,
                top_limit=top_limit,
                case_scan_limit=case_scan_limit,
                collect_fairness_case_items=collect_fairness_case_items_v3,
                list_judge_case_fairness=list_judge_case_fairness,
                build_case_fairness_aggregations=deps.build_case_fairness_aggregations,
                build_fairness_dashboard_case_trends=(
                    build_fairness_dashboard_case_trends_v3
                ),
                build_fairness_dashboard_run_trends=(
                    build_fairness_dashboard_run_trends_v3
                ),
                build_fairness_dashboard_top_risk_cases=(
                    build_fairness_dashboard_top_risk_cases_v3
                ),
                list_fairness_benchmark_runs=deps.list_fairness_benchmark_runs,
                list_fairness_shadow_runs=deps.list_fairness_shadow_runs,
                validate_fairness_dashboard_contract=(
                    deps.validate_fairness_dashboard_contract
                ),
            )
        )

    @app.get("/internal/judge/fairness/calibration-pack")
    async def get_judge_fairness_calibration_pack(
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str | None = Query(default="final"),
        status: str | None = Query(default=None),
        winner: str | None = Query(default=None),
        policy_version: str | None = Query(default=None),
        challenge_state: str | None = Query(default=None),
        case_scan_limit: int = Query(default=200, ge=20, le=1000),
        risk_limit: int = Query(default=50, ge=1, le=200),
        benchmark_limit: int = Query(default=200, ge=1, le=500),
        shadow_limit: int = Query(default=200, ge=1, le=500),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await _build_fairness_calibration_pack_payload(
            x_ai_internal_key=x_ai_internal_key,
            dispatch_type=dispatch_type,
            status=status,
            winner=winner,
            policy_version=policy_version,
            challenge_state=challenge_state,
            case_scan_limit=case_scan_limit,
            risk_limit=risk_limit,
            benchmark_limit=benchmark_limit,
            shadow_limit=shadow_limit,
            deps=deps,
            list_judge_case_fairness=list_judge_case_fairness,
        )

    @app.get("/internal/judge/fairness/policy-calibration-advisor")
    async def get_judge_fairness_policy_calibration_advisor(
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str | None = Query(default="final"),
        status: str | None = Query(default=None),
        winner: str | None = Query(default=None),
        policy_version: str | None = Query(default=None),
        challenge_state: str | None = Query(default=None),
        case_scan_limit: int = Query(default=200, ge=20, le=1000),
        risk_limit: int = Query(default=50, ge=1, le=200),
        benchmark_limit: int = Query(default=200, ge=1, le=500),
        shadow_limit: int = Query(default=200, ge=1, le=500),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await _build_fairness_policy_calibration_advisor_payload(
            x_ai_internal_key=x_ai_internal_key,
            dispatch_type=dispatch_type,
            status=status,
            winner=winner,
            policy_version=policy_version,
            challenge_state=challenge_state,
            case_scan_limit=case_scan_limit,
            risk_limit=risk_limit,
            benchmark_limit=benchmark_limit,
            shadow_limit=shadow_limit,
            deps=deps,
            list_judge_case_fairness=list_judge_case_fairness,
            calibration_decision_log_store=calibration_decision_log_store,
        )

    @app.post("/internal/judge/fairness/policy-calibration-decisions")
    async def create_judge_fairness_policy_calibration_decision(
        request: Request,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        raw_payload = await deps.read_json_object_or_raise_422(request=request)
        return await deps.run_fairness_route_guard(
            _guard_decision_log_value_errors(
                build_fairness_calibration_decision_create_payload(
                    raw_payload=raw_payload,
                    store=calibration_decision_log_store,
                )
            )
        )

    @app.get("/internal/judge/fairness/policy-calibration-decisions")
    async def list_judge_fairness_policy_calibration_decisions(
        x_ai_internal_key: str | None = Header(default=None),
        policy_version: str | None = Query(default=None),
        source_recommendation_id: str | None = Query(default=None),
        decision: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=500),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.run_fairness_route_guard(
            _guard_decision_log_value_errors(
                build_fairness_calibration_decision_list_payload(
                    store=calibration_decision_log_store,
                    policy_version=policy_version,
                    source_recommendation_id=source_recommendation_id,
                    decision=decision,
                    limit=limit,
                )
            )
        )

    return FairnessRouteHandles(
        upsert_judge_fairness_benchmark_run=upsert_judge_fairness_benchmark_run,
        list_judge_fairness_benchmark_runs=list_judge_fairness_benchmark_runs,
        upsert_judge_fairness_shadow_run=upsert_judge_fairness_shadow_run,
        list_judge_fairness_shadow_runs=list_judge_fairness_shadow_runs,
        get_judge_case_fairness=get_judge_case_fairness,
        list_judge_case_fairness=list_judge_case_fairness,
        get_judge_fairness_dashboard=get_judge_fairness_dashboard,
        get_judge_fairness_calibration_pack=get_judge_fairness_calibration_pack,
        get_judge_fairness_policy_calibration_advisor=(
            get_judge_fairness_policy_calibration_advisor
        ),
        create_judge_fairness_policy_calibration_decision=(
            create_judge_fairness_policy_calibration_decision
        ),
        list_judge_fairness_policy_calibration_decisions=(
            list_judge_fairness_policy_calibration_decisions
        ),
    )
