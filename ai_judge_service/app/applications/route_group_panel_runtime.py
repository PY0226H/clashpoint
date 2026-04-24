from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Header, Query

AsyncPayloadFn = Callable[..., Awaitable[dict[str, Any]]]
PanelRuntimeRouteGuardFn = Callable[
    [Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]
]
RequireInternalKeyFn = Callable[[Any, str | None], None]


@dataclass(frozen=True)
class PanelRuntimeRouteHandles:
    list_panel_runtime_profiles: AsyncPayloadFn
    get_panel_runtime_readiness: AsyncPayloadFn


@dataclass(frozen=True)
class PanelRuntimeRouteDependencies:
    runtime: Any
    require_internal_key_fn: RequireInternalKeyFn
    await_payload_or_raise_http_500: AsyncPayloadFn
    build_panel_runtime_profiles_payload: AsyncPayloadFn
    build_panel_runtime_readiness_payload: AsyncPayloadFn
    list_judge_case_fairness: AsyncPayloadFn
    run_panel_runtime_route_guard: PanelRuntimeRouteGuardFn


def register_panel_runtime_routes(
    *,
    app: FastAPI,
    deps: PanelRuntimeRouteDependencies,
) -> PanelRuntimeRouteHandles:
    runtime = deps.runtime

    @app.get("/internal/judge/panels/runtime/profiles")
    async def list_panel_runtime_profiles(
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        dispatch_type: str | None = Query(default=None),
        winner: str | None = Query(default=None),
        policy_version: str | None = Query(default=None),
        has_open_review: bool | None = Query(default=None),
        gate_conclusion: str | None = Query(default=None),
        challenge_state: str | None = Query(default=None),
        review_required: bool | None = Query(default=None),
        panel_high_disagreement: bool | None = Query(default=None),
        judge_id: str | None = Query(default=None),
        profile_source: str | None = Query(default=None),
        profile_id: str | None = Query(default=None),
        model_strategy: str | None = Query(default=None),
        strategy_slot: str | None = Query(default=None),
        domain_slot: str | None = Query(default=None),
        sort_by: str = Query(default="updated_at"),
        sort_order: str = Query(default="desc"),
        offset: int = Query(default=0, ge=0, le=5000),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.await_payload_or_raise_http_500(
            self_awaitable=deps.build_panel_runtime_profiles_payload(
                x_ai_internal_key=x_ai_internal_key,
                status=status,
                dispatch_type=dispatch_type,
                winner=winner,
                policy_version=policy_version,
                has_open_review=has_open_review,
                gate_conclusion=gate_conclusion,
                challenge_state=challenge_state,
                review_required=review_required,
                panel_high_disagreement=panel_high_disagreement,
                judge_id=judge_id,
                profile_source=profile_source,
                profile_id=profile_id,
                model_strategy=model_strategy,
                strategy_slot=strategy_slot,
                domain_slot=domain_slot,
                sort_by=sort_by,
                sort_order=sort_order,
                offset=offset,
                limit=limit,
                list_judge_case_fairness=deps.list_judge_case_fairness,
                run_panel_runtime_route_guard=deps.run_panel_runtime_route_guard,
            ),
            code="panel_runtime_profile_contract_violation",
        )

    @app.get("/internal/judge/panels/runtime/readiness")
    async def get_panel_runtime_readiness(
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        dispatch_type: str | None = Query(default="final"),
        winner: str | None = Query(default=None),
        policy_version: str | None = Query(default=None),
        has_open_review: bool | None = Query(default=None),
        gate_conclusion: str | None = Query(default=None),
        challenge_state: str | None = Query(default=None),
        review_required: bool | None = Query(default=None),
        panel_high_disagreement: bool | None = Query(default=None),
        judge_id: str | None = Query(default=None),
        profile_source: str | None = Query(default=None),
        profile_id: str | None = Query(default=None),
        model_strategy: str | None = Query(default=None),
        strategy_slot: str | None = Query(default=None),
        domain_slot: str | None = Query(default=None),
        profile_scan_limit: int = Query(default=600, ge=50, le=5000),
        group_limit: int = Query(default=50, ge=1, le=200),
        attention_limit: int = Query(default=20, ge=1, le=100),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.build_panel_runtime_readiness_payload(
            x_ai_internal_key=x_ai_internal_key,
            status=status,
            dispatch_type=dispatch_type,
            winner=winner,
            policy_version=policy_version,
            has_open_review=has_open_review,
            gate_conclusion=gate_conclusion,
            challenge_state=challenge_state,
            review_required=review_required,
            panel_high_disagreement=panel_high_disagreement,
            judge_id=judge_id,
            profile_source=profile_source,
            profile_id=profile_id,
            model_strategy=model_strategy,
            strategy_slot=strategy_slot,
            domain_slot=domain_slot,
            profile_scan_limit=profile_scan_limit,
            group_limit=group_limit,
            attention_limit=attention_limit,
            list_panel_runtime_profiles=list_panel_runtime_profiles,
            run_panel_runtime_route_guard=deps.run_panel_runtime_route_guard,
        )

    return PanelRuntimeRouteHandles(
        list_panel_runtime_profiles=list_panel_runtime_profiles,
        get_panel_runtime_readiness=get_panel_runtime_readiness,
    )
