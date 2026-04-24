from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Header, Query

from .review_alert_routes import (
    build_review_case_decision_payload as build_review_case_decision_payload_v3,
)

AsyncPayloadFn = Callable[..., Awaitable[dict[str, Any]]]
ReviewRouteGuardFn = Callable[[Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]]
RequireInternalKeyFn = Callable[[Any, str | None], None]


@dataclass(frozen=True)
class ReviewRouteHandles:
    list_judge_review_jobs: AsyncPayloadFn
    get_judge_review_job: AsyncPayloadFn
    decide_judge_review_job: AsyncPayloadFn


@dataclass(frozen=True)
class ReviewRouteDependencies:
    runtime: Any
    require_internal_key_fn: RequireInternalKeyFn
    await_payload_or_raise_http_422: AsyncPayloadFn
    await_payload_or_raise_http_404: AsyncPayloadFn
    await_payload_or_raise_http_422_404: AsyncPayloadFn
    build_review_cases_list_payload: AsyncPayloadFn
    build_review_case_detail_payload: AsyncPayloadFn
    run_review_route_guard: ReviewRouteGuardFn
    workflow_get_job: Callable[..., Awaitable[Any | None]]
    workflow_list_jobs: Callable[..., Awaitable[list[Any]]]
    workflow_list_events: Callable[..., Awaitable[list[Any]]]
    workflow_mark_completed: Callable[..., Awaitable[None]]
    workflow_mark_failed: Callable[..., Awaitable[None]]
    list_audit_alerts: Callable[..., Awaitable[list[Any]]]
    get_trace: Callable[..., Any]
    build_review_case_risk_profile: Callable[..., dict[str, Any]]
    build_trust_challenge_priority_profile: Callable[..., dict[str, Any]]
    build_review_trust_unified_priority_profile: Callable[..., dict[str, Any]]
    resolve_open_alerts_for_review: Callable[..., Awaitable[list[str]]]
    serialize_workflow_job: Callable[[Any], dict[str, Any]]
    serialize_alert_item: Callable[[Any], dict[str, Any]]


def register_review_routes(
    *,
    app: FastAPI,
    deps: ReviewRouteDependencies,
) -> ReviewRouteHandles:
    runtime = deps.runtime

    @app.get("/internal/judge/review/cases")
    async def list_judge_review_jobs(
        x_ai_internal_key: str | None = Header(default=None),
        status: str = Query(default="review_required"),
        dispatch_type: str | None = Query(default=None),
        risk_level: str | None = Query(default=None),
        sla_bucket: str | None = Query(default=None),
        challenge_state: str | None = Query(default=None),
        trust_review_state: str | None = Query(default=None),
        unified_priority_level: str | None = Query(default=None),
        sort_by: str = Query(default="updated_at"),
        sort_order: str = Query(default="desc"),
        scan_limit: int = Query(default=200, ge=20, le=1000),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.await_payload_or_raise_http_422(
            self_awaitable=deps.build_review_cases_list_payload(
                status=status,
                dispatch_type=dispatch_type,
                risk_level=risk_level,
                sla_bucket=sla_bucket,
                challenge_state=challenge_state,
                trust_review_state=trust_review_state,
                unified_priority_level=unified_priority_level,
                sort_by=sort_by,
                sort_order=sort_order,
                scan_limit=scan_limit,
                limit=limit,
                workflow_list_jobs=deps.workflow_list_jobs,
                workflow_list_events=deps.workflow_list_events,
                list_audit_alerts=deps.list_audit_alerts,
                get_trace=deps.get_trace,
                build_review_case_risk_profile=deps.build_review_case_risk_profile,
                build_trust_challenge_priority_profile=(
                    deps.build_trust_challenge_priority_profile
                ),
                build_review_trust_unified_priority_profile=(
                    deps.build_review_trust_unified_priority_profile
                ),
                serialize_workflow_job=deps.serialize_workflow_job,
            ),
        )

    @app.get("/internal/judge/review/cases/{case_id}")
    async def get_judge_review_job(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.await_payload_or_raise_http_404(
            self_awaitable=deps.build_review_case_detail_payload(
                case_id=case_id,
                workflow_get_job=deps.workflow_get_job,
                workflow_list_events=deps.workflow_list_events,
                list_audit_alerts=deps.list_audit_alerts,
                get_trace=deps.get_trace,
                serialize_workflow_job=deps.serialize_workflow_job,
                serialize_alert_item=deps.serialize_alert_item,
            ),
        )

    @app.post("/internal/judge/review/cases/{case_id}/decision")
    async def decide_judge_review_job(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        decision: str = Query(default="approve"),
        actor: str | None = Query(default=None),
        reason: str | None = Query(default=None),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.await_payload_or_raise_http_422_404(
            self_awaitable=deps.run_review_route_guard(
                build_review_case_decision_payload_v3(
                    case_id=case_id,
                    decision=decision,
                    actor=actor,
                    reason=reason,
                    workflow_get_job=deps.workflow_get_job,
                    workflow_mark_completed=deps.workflow_mark_completed,
                    workflow_mark_failed=deps.workflow_mark_failed,
                    resolve_open_alerts_for_review=(
                        deps.resolve_open_alerts_for_review
                    ),
                    serialize_workflow_job=deps.serialize_workflow_job,
                )
            ),
        )

    return ReviewRouteHandles(
        list_judge_review_jobs=list_judge_review_jobs,
        get_judge_review_job=get_judge_review_job,
        decide_judge_review_job=decide_judge_review_job,
    )
