from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Header, Query

from .runtime_readiness_public_contract import build_runtime_readiness_public_payload

AsyncPayloadFn = Callable[..., Awaitable[dict[str, Any]]]
RequireInternalKeyFn = Callable[[Any, str | None], None]


@dataclass(frozen=True)
class OpsReadModelPackRouteHandles:
    get_judge_ops_read_model_pack: AsyncPayloadFn
    get_judge_runtime_readiness: AsyncPayloadFn


@dataclass(frozen=True)
class OpsReadModelPackRouteDependencies:
    runtime: Any
    require_internal_key_fn: RequireInternalKeyFn
    await_payload_or_raise_http_500: AsyncPayloadFn
    build_ops_read_model_pack_payload: AsyncPayloadFn
    get_judge_fairness_dashboard: AsyncPayloadFn
    get_registry_governance_overview: AsyncPayloadFn
    get_registry_prompt_tool_governance: AsyncPayloadFn
    get_policy_registry_dependency_health: AsyncPayloadFn
    get_judge_fairness_policy_calibration_advisor: AsyncPayloadFn
    get_panel_runtime_readiness: AsyncPayloadFn
    list_judge_courtroom_cases: AsyncPayloadFn
    list_judge_courtroom_drilldown_bundle: AsyncPayloadFn
    list_judge_evidence_claim_ops_queue: AsyncPayloadFn
    list_judge_trust_challenge_ops_queue: AsyncPayloadFn
    list_judge_review_jobs: AsyncPayloadFn
    simulate_policy_release_gate: AsyncPayloadFn
    get_judge_case_courtroom_read_model: AsyncPayloadFn
    get_judge_trust_public_verify: AsyncPayloadFn


def register_ops_read_model_pack_routes(
    *,
    app: FastAPI,
    deps: OpsReadModelPackRouteDependencies,
) -> OpsReadModelPackRouteHandles:
    runtime = deps.runtime

    def _build_pack_payload_awaitable(
        *,
        x_ai_internal_key: str | None,
        dispatch_type: str | None,
        policy_version: str | None,
        window_days: int,
        top_limit: int,
        case_scan_limit: int,
        include_case_trust: bool,
        trust_case_limit: int,
        dependency_limit: int,
        usage_preview_limit: int,
        release_limit: int,
        audit_limit: int,
        calibration_risk_limit: int,
        calibration_benchmark_limit: int,
        calibration_shadow_limit: int,
        panel_profile_scan_limit: int,
        panel_group_limit: int,
        panel_attention_limit: int,
    ) -> Awaitable[dict[str, Any]]:
        return deps.build_ops_read_model_pack_payload(
            x_ai_internal_key=x_ai_internal_key,
            dispatch_type=dispatch_type,
            policy_version=policy_version,
            window_days=window_days,
            top_limit=top_limit,
            case_scan_limit=case_scan_limit,
            include_case_trust=include_case_trust,
            trust_case_limit=trust_case_limit,
            dependency_limit=dependency_limit,
            usage_preview_limit=usage_preview_limit,
            release_limit=release_limit,
            audit_limit=audit_limit,
            calibration_risk_limit=calibration_risk_limit,
            calibration_benchmark_limit=calibration_benchmark_limit,
            calibration_shadow_limit=calibration_shadow_limit,
            panel_profile_scan_limit=panel_profile_scan_limit,
            panel_group_limit=panel_group_limit,
            panel_attention_limit=panel_attention_limit,
            runtime=runtime,
            get_judge_fairness_dashboard=deps.get_judge_fairness_dashboard,
            get_registry_governance_overview=(
                deps.get_registry_governance_overview
            ),
            get_registry_prompt_tool_governance=(
                deps.get_registry_prompt_tool_governance
            ),
            get_policy_registry_dependency_health=(
                deps.get_policy_registry_dependency_health
            ),
            get_judge_fairness_policy_calibration_advisor=(
                deps.get_judge_fairness_policy_calibration_advisor
            ),
            get_panel_runtime_readiness=deps.get_panel_runtime_readiness,
            list_judge_courtroom_cases=deps.list_judge_courtroom_cases,
            list_judge_courtroom_drilldown_bundle=(
                deps.list_judge_courtroom_drilldown_bundle
            ),
            list_judge_evidence_claim_ops_queue=(
                deps.list_judge_evidence_claim_ops_queue
            ),
            list_judge_trust_challenge_ops_queue=(
                deps.list_judge_trust_challenge_ops_queue
            ),
            list_judge_review_jobs=deps.list_judge_review_jobs,
            simulate_policy_release_gate=deps.simulate_policy_release_gate,
            get_judge_case_courtroom_read_model=(
                deps.get_judge_case_courtroom_read_model
            ),
            get_judge_trust_public_verify=deps.get_judge_trust_public_verify,
        )

    async def _build_runtime_readiness_payload(
        **kwargs: Any,
    ) -> dict[str, Any]:
        pack_payload = await _build_pack_payload_awaitable(**kwargs)
        return build_runtime_readiness_public_payload(pack_payload)

    @app.get("/internal/judge/ops/read-model/pack")
    async def get_judge_ops_read_model_pack(
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str | None = Query(default="final"),
        policy_version: str | None = Query(default=None),
        window_days: int = Query(default=7, ge=1, le=30),
        top_limit: int = Query(default=10, ge=1, le=50),
        case_scan_limit: int = Query(default=200, ge=20, le=1000),
        include_case_trust: bool = Query(default=True),
        trust_case_limit: int = Query(default=5, ge=1, le=20),
        dependency_limit: int = Query(default=200, ge=1, le=500),
        usage_preview_limit: int = Query(default=20, ge=1, le=200),
        release_limit: int = Query(default=50, ge=1, le=200),
        audit_limit: int = Query(default=100, ge=1, le=200),
        calibration_risk_limit: int = Query(default=50, ge=1, le=200),
        calibration_benchmark_limit: int = Query(default=200, ge=1, le=500),
        calibration_shadow_limit: int = Query(default=200, ge=1, le=500),
        panel_profile_scan_limit: int = Query(default=600, ge=50, le=5000),
        panel_group_limit: int = Query(default=50, ge=1, le=200),
        panel_attention_limit: int = Query(default=20, ge=1, le=100),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.await_payload_or_raise_http_500(
            self_awaitable=_build_pack_payload_awaitable(
                x_ai_internal_key=x_ai_internal_key,
                dispatch_type=dispatch_type,
                policy_version=policy_version,
                window_days=window_days,
                top_limit=top_limit,
                case_scan_limit=case_scan_limit,
                include_case_trust=include_case_trust,
                trust_case_limit=trust_case_limit,
                dependency_limit=dependency_limit,
                usage_preview_limit=usage_preview_limit,
                release_limit=release_limit,
                audit_limit=audit_limit,
                calibration_risk_limit=calibration_risk_limit,
                calibration_benchmark_limit=calibration_benchmark_limit,
                calibration_shadow_limit=calibration_shadow_limit,
                panel_profile_scan_limit=panel_profile_scan_limit,
                panel_group_limit=panel_group_limit,
                panel_attention_limit=panel_attention_limit,
            ),
            code="ops_read_model_pack_v5_contract_violation",
        )

    @app.get("/internal/judge/ops/runtime-readiness")
    async def get_judge_runtime_readiness(
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str | None = Query(default="final"),
        policy_version: str | None = Query(default=None),
        window_days: int = Query(default=7, ge=1, le=30),
        top_limit: int = Query(default=10, ge=1, le=50),
        case_scan_limit: int = Query(default=200, ge=20, le=1000),
        include_case_trust: bool = Query(default=True),
        trust_case_limit: int = Query(default=5, ge=1, le=20),
        dependency_limit: int = Query(default=200, ge=1, le=500),
        usage_preview_limit: int = Query(default=20, ge=1, le=200),
        release_limit: int = Query(default=50, ge=1, le=200),
        audit_limit: int = Query(default=100, ge=1, le=200),
        calibration_risk_limit: int = Query(default=50, ge=1, le=200),
        calibration_benchmark_limit: int = Query(default=200, ge=1, le=500),
        calibration_shadow_limit: int = Query(default=200, ge=1, le=500),
        panel_profile_scan_limit: int = Query(default=600, ge=50, le=5000),
        panel_group_limit: int = Query(default=50, ge=1, le=200),
        panel_attention_limit: int = Query(default=20, ge=1, le=100),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.await_payload_or_raise_http_500(
            self_awaitable=_build_runtime_readiness_payload(
                x_ai_internal_key=x_ai_internal_key,
                dispatch_type=dispatch_type,
                policy_version=policy_version,
                window_days=window_days,
                top_limit=top_limit,
                case_scan_limit=case_scan_limit,
                include_case_trust=include_case_trust,
                trust_case_limit=trust_case_limit,
                dependency_limit=dependency_limit,
                usage_preview_limit=usage_preview_limit,
                release_limit=release_limit,
                audit_limit=audit_limit,
                calibration_risk_limit=calibration_risk_limit,
                calibration_benchmark_limit=calibration_benchmark_limit,
                calibration_shadow_limit=calibration_shadow_limit,
                panel_profile_scan_limit=panel_profile_scan_limit,
                panel_group_limit=panel_group_limit,
                panel_attention_limit=panel_attention_limit,
            ),
            code="runtime_readiness_public_contract_violation",
        )

    return OpsReadModelPackRouteHandles(
        get_judge_ops_read_model_pack=get_judge_ops_read_model_pack,
        get_judge_runtime_readiness=get_judge_runtime_readiness,
    )
