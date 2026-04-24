from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Header, Query

from .review_alert_routes import (
    build_alert_outbox_delivery_payload as build_alert_outbox_delivery_payload_v3,
)
from .review_alert_routes import (
    build_rag_diagnostics_payload as build_rag_diagnostics_payload_v3,
)

AsyncPayloadFn = Callable[..., Awaitable[dict[str, Any]]]
SyncPayloadFn = Callable[..., dict[str, Any]]
RequireInternalKeyFn = Callable[[Any, str | None], None]


@dataclass(frozen=True)
class AlertOpsRouteHandles:
    list_judge_job_alerts: AsyncPayloadFn
    ack_judge_job_alert: AsyncPayloadFn
    resolve_judge_job_alert: AsyncPayloadFn
    list_judge_alert_ops_view: AsyncPayloadFn
    list_judge_alert_outbox: AsyncPayloadFn
    mark_judge_alert_outbox_delivery: AsyncPayloadFn
    get_rag_diagnostics: AsyncPayloadFn


@dataclass(frozen=True)
class AlertOpsRouteDependencies:
    runtime: Any
    require_internal_key_fn: RequireInternalKeyFn
    await_payload_or_raise_http_422: AsyncPayloadFn
    build_payload_or_raise_http_404: SyncPayloadFn
    build_case_alerts_payload: AsyncPayloadFn
    transition_judge_alert_status: AsyncPayloadFn
    build_alert_ops_view_payload: AsyncPayloadFn
    build_alert_outbox_payload: SyncPayloadFn
    list_audit_alerts: Callable[..., Awaitable[list[Any]]]
    list_alert_outbox: Callable[..., list[Any]]
    mark_alert_outbox_delivery: Callable[..., Any]
    get_trace: Callable[..., Any]
    serialize_alert_item: Callable[[Any], dict[str, Any]]
    serialize_outbox_event: Callable[[Any], dict[str, Any]]


def register_alert_ops_routes(
    *,
    app: FastAPI,
    deps: AlertOpsRouteDependencies,
) -> AlertOpsRouteHandles:
    runtime = deps.runtime

    @app.get("/internal/judge/cases/{case_id}/alerts")
    async def list_judge_job_alerts(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.build_case_alerts_payload(
            case_id=case_id,
            status=status,
            limit=limit,
            list_audit_alerts=deps.list_audit_alerts,
            serialize_alert_item=deps.serialize_alert_item,
        )

    @app.post("/internal/judge/cases/{case_id}/alerts/{alert_id}/ack")
    async def ack_judge_job_alert(
        case_id: int,
        alert_id: str,
        x_ai_internal_key: str | None = Header(default=None),
        actor: str | None = Query(default=None),
        reason: str | None = Query(default=None),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.transition_judge_alert_status(
            case_id=case_id,
            alert_id=alert_id,
            to_status="acked",
            actor=actor,
            reason=reason,
        )

    @app.post("/internal/judge/cases/{case_id}/alerts/{alert_id}/resolve")
    async def resolve_judge_job_alert(
        case_id: int,
        alert_id: str,
        x_ai_internal_key: str | None = Header(default=None),
        actor: str | None = Query(default=None),
        reason: str | None = Query(default=None),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.transition_judge_alert_status(
            case_id=case_id,
            alert_id=alert_id,
            to_status="resolved",
            actor=actor,
            reason=reason,
        )

    @app.get("/internal/judge/alerts/ops-view")
    async def list_judge_alert_ops_view(
        x_ai_internal_key: str | None = Header(default=None),
        alert_type: str | None = Query(default=None),
        status: str | None = Query(default=None),
        delivery_status: str | None = Query(default=None),
        registry_type: str | None = Query(default=None),
        policy_version: str | None = Query(default=None),
        gate_code: str | None = Query(default=None),
        gate_actor: str | None = Query(default=None),
        override_applied: bool | None = Query(default=None),
        fields_mode: str = Query(default="full"),
        include_trend: bool = Query(default=True),
        trend_window_minutes: int = Query(default=1440, ge=10, le=43200),
        trend_bucket_minutes: int = Query(default=60, ge=5, le=1440),
        offset: int = Query(default=0, ge=0, le=5000),
        limit: int = Query(default=50, ge=1, le=500),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.await_payload_or_raise_http_422(
            self_awaitable=deps.build_alert_ops_view_payload(
                alert_type=alert_type,
                status=status,
                delivery_status=delivery_status,
                registry_type=registry_type,
                policy_version=policy_version,
                gate_code=gate_code,
                gate_actor=gate_actor,
                override_applied=override_applied,
                fields_mode=fields_mode,
                include_trend=include_trend,
                trend_window_minutes=trend_window_minutes,
                trend_bucket_minutes=trend_bucket_minutes,
                offset=offset,
                limit=limit,
                list_audit_alerts=deps.list_audit_alerts,
                list_alert_outbox=deps.list_alert_outbox,
            ),
        )

    @app.get("/internal/judge/alerts/outbox")
    async def list_judge_alert_outbox(
        x_ai_internal_key: str | None = Header(default=None),
        delivery_status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return deps.build_alert_outbox_payload(
            delivery_status=delivery_status,
            limit=limit,
            list_alert_outbox=deps.list_alert_outbox,
            serialize_outbox_event=deps.serialize_outbox_event,
        )

    @app.post("/internal/judge/alerts/outbox/{event_id}/delivery")
    async def mark_judge_alert_outbox_delivery(
        event_id: str,
        x_ai_internal_key: str | None = Header(default=None),
        delivery_status: str = Query(default="sent"),
        error_message: str | None = Query(default=None),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        item = deps.mark_alert_outbox_delivery(
            event_id=event_id,
            delivery_status=delivery_status,
            error_message=error_message,
        )
        return deps.build_payload_or_raise_http_404(
            builder=build_alert_outbox_delivery_payload_v3,
            item=item,
            serialize_outbox_event=deps.serialize_outbox_event,
        )

    @app.get("/internal/judge/rag/diagnostics")
    async def get_rag_diagnostics(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return deps.build_payload_or_raise_http_404(
            builder=build_rag_diagnostics_payload_v3,
            case_id=case_id,
            get_trace=deps.get_trace,
        )

    return AlertOpsRouteHandles(
        list_judge_job_alerts=list_judge_job_alerts,
        ack_judge_job_alert=ack_judge_job_alert,
        resolve_judge_job_alert=resolve_judge_job_alert,
        list_judge_alert_ops_view=list_judge_alert_ops_view,
        list_judge_alert_outbox=list_judge_alert_outbox,
        mark_judge_alert_outbox_delivery=mark_judge_alert_outbox_delivery,
        get_rag_diagnostics=get_rag_diagnostics,
    )
