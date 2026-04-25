from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Header, Query

from .judge_trace_replay_routes import (
    build_replay_post_route_payload as build_replay_post_route_payload_v3,
)
from .judge_trace_replay_routes import (
    build_trace_route_payload as build_trace_route_payload_v3,
)
from .judge_trace_replay_routes import (
    build_trace_route_read_payload as build_trace_route_read_payload_v3,
)
from .judge_trace_replay_routes import (
    build_trace_route_replay_items as build_trace_route_replay_items_v3,
)
from .replay_audit_ops import build_verdict_contract as build_verdict_contract_v3

AsyncPayloadFn = Callable[..., Awaitable[dict[str, Any]]]
ReplayReportsPayloadFn = Callable[..., dict[str, Any]]
ReplayRouteGuardFn = Callable[[Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]]
RequireInternalKeyFn = Callable[[Any, str | None], None]


@dataclass(frozen=True)
class ReplayRouteHandles:
    get_judge_job_trace: AsyncPayloadFn
    replay_judge_job: AsyncPayloadFn
    get_judge_replay_report: AsyncPayloadFn
    list_judge_replay_reports: AsyncPayloadFn


@dataclass(frozen=True)
class ReplayRouteDependencies:
    runtime: Any
    require_internal_key_fn: RequireInternalKeyFn
    run_replay_read_guard: ReplayRouteGuardFn
    build_replay_report_payload: AsyncPayloadFn
    build_replay_reports_payload: ReplayReportsPayloadFn
    replay_context_dependencies: Any
    replay_report_dependencies: Any
    replay_finalize_dependencies: Any
    get_trace: Callable[..., Any]
    list_replay_records: Callable[..., Awaitable[list[Any]]]
    get_claim_ledger_record: Callable[..., Awaitable[Any | None]]
    list_traces: Callable[..., list[Any]]
    build_case_chain_summary: Callable[..., Awaitable[dict[str, Any]]] | None = None


def register_replay_routes(
    *,
    app: FastAPI,
    deps: ReplayRouteDependencies,
) -> ReplayRouteHandles:
    runtime = deps.runtime

    @app.get("/internal/judge/cases/{case_id}/trace")
    async def get_judge_job_trace(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.run_replay_read_guard(
            build_trace_route_read_payload_v3(
                case_id=case_id,
                get_trace=deps.get_trace,
                list_replay_records=deps.list_replay_records,
                build_trace_route_replay_items=build_trace_route_replay_items_v3,
                build_verdict_contract=build_verdict_contract_v3,
                build_trace_route_payload=build_trace_route_payload_v3,
                build_case_chain_summary=deps.build_case_chain_summary,
            )
        )

    @app.post("/internal/judge/cases/{case_id}/replay")
    async def replay_judge_job(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.run_replay_read_guard(
            build_replay_post_route_payload_v3(
                case_id=case_id,
                dispatch_type=dispatch_type,
                context_dependencies=deps.replay_context_dependencies,
                # replay 主路由只保留 HTTP 语义，重算编排统一在 applications 层完成。
                report_dependencies=deps.replay_report_dependencies,
                finalize_dependencies=deps.replay_finalize_dependencies,
            )
        )

    @app.get("/internal/judge/cases/{case_id}/replay/report")
    async def get_judge_replay_report(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.build_replay_report_payload(
            case_id=case_id,
            get_trace=deps.get_trace,
            get_claim_ledger_record=deps.get_claim_ledger_record,
            run_replay_read_guard=deps.run_replay_read_guard,
        )

    @app.get("/internal/judge/cases/replay/reports")
    async def list_judge_replay_reports(
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        winner: str | None = Query(default=None),
        callback_status: str | None = Query(default=None),
        trace_id: str | None = Query(default=None),
        created_after: datetime | None = Query(default=None),
        created_before: datetime | None = Query(default=None),
        has_audit_alert: bool | None = Query(default=None),
        limit: int = Query(default=20, ge=1, le=200),
        include_report: bool = Query(default=False),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return deps.build_replay_reports_payload(
            status=status,
            winner=winner,
            callback_status=callback_status,
            trace_id=trace_id,
            created_after=created_after,
            created_before=created_before,
            has_audit_alert=has_audit_alert,
            limit=limit,
            include_report=include_report,
            list_traces=deps.list_traces,
        )

    return ReplayRouteHandles(
        get_judge_job_trace=get_judge_job_trace,
        replay_judge_job=replay_judge_job,
        get_judge_replay_report=get_judge_replay_report,
        list_judge_replay_reports=list_judge_replay_reports,
    )
