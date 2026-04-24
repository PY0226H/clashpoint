from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Header, Query

from .trust_read_routes import (
    build_trust_attestation_verify_payload as build_trust_attestation_verify_payload_v3,
)

AsyncPayloadFn = Callable[..., Awaitable[dict[str, Any]]]
TrustRouteGuardFn = Callable[[Awaitable[dict[str, Any]]], Awaitable[dict[str, Any]]]
RequireInternalKeyFn = Callable[[Any, str | None], None]
ValidateContractFn = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class TrustRouteHandles:
    get_judge_trust_case_commitment: AsyncPayloadFn
    get_judge_trust_verdict_attestation: AsyncPayloadFn
    get_judge_trust_challenge_review: AsyncPayloadFn
    list_judge_trust_challenge_ops_queue: AsyncPayloadFn
    request_judge_trust_challenge: AsyncPayloadFn
    decide_judge_trust_challenge: AsyncPayloadFn
    get_judge_trust_kernel_version: AsyncPayloadFn
    get_judge_trust_audit_anchor: AsyncPayloadFn
    get_judge_trust_public_verify: AsyncPayloadFn
    verify_judge_report_attestation: AsyncPayloadFn


@dataclass(frozen=True)
class TrustRouteDependencies:
    runtime: Any
    require_internal_key_fn: RequireInternalKeyFn
    build_validated_trust_item_payload: AsyncPayloadFn
    build_trust_challenge_ops_queue_payload: AsyncPayloadFn
    build_trust_challenge_request_payload: AsyncPayloadFn
    build_trust_challenge_decision_payload: AsyncPayloadFn
    build_trust_audit_anchor_payload: AsyncPayloadFn
    build_trust_public_verify_payload: AsyncPayloadFn
    run_trust_read_guard: TrustRouteGuardFn
    build_trust_phasea_bundle: Callable[..., Awaitable[dict[str, Any]]]
    build_audit_anchor_export: Callable[..., dict[str, Any]]
    build_public_verify_payload: Callable[..., dict[str, Any]]
    verify_report_attestation: Callable[..., dict[str, Any]]
    get_dispatch_receipt: Callable[..., Awaitable[Any | None]]
    workflow_list_jobs: Callable[..., Awaitable[list[Any]]]
    get_trace: Callable[..., Any]
    build_trust_challenge_priority_profile: Callable[..., dict[str, Any]]
    serialize_workflow_job: Callable[[Any], dict[str, Any]]
    build_trust_challenge_action_hints: Callable[..., dict[str, Any]]
    run_trust_challenge_guard: TrustRouteGuardFn
    trust_challenge_common_dependencies: dict[str, Any]
    upsert_audit_alert: Callable[..., Any]
    sync_audit_alert_to_facts: Callable[..., Awaitable[Any]]
    workflow_mark_completed: Callable[..., Awaitable[None]]
    workflow_mark_draw_pending_vote: Callable[..., Awaitable[Any]]
    resolve_open_alerts_for_review: Callable[..., Awaitable[list[Any]]]
    validate_trust_commitment_contract: ValidateContractFn
    validate_trust_verdict_attestation_contract: ValidateContractFn
    validate_trust_challenge_review_contract: ValidateContractFn
    validate_trust_kernel_version_contract: ValidateContractFn
    validate_trust_audit_anchor_contract: ValidateContractFn
    validate_trust_public_verify_contract: ValidateContractFn


def register_trust_routes(
    *,
    app: FastAPI,
    deps: TrustRouteDependencies,
) -> TrustRouteHandles:
    runtime = deps.runtime

    @app.get("/internal/judge/cases/{case_id}/trust/commitment")
    async def get_judge_trust_case_commitment(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.build_validated_trust_item_payload(
            case_id=case_id,
            dispatch_type=dispatch_type,
            item_key="commitment",
            validate_contract=deps.validate_trust_commitment_contract,
            violation_code="trust_commitment_contract_violation",
            build_trust_phasea_bundle=deps.build_trust_phasea_bundle,
        )

    @app.get("/internal/judge/cases/{case_id}/trust/verdict-attestation")
    async def get_judge_trust_verdict_attestation(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.build_validated_trust_item_payload(
            case_id=case_id,
            dispatch_type=dispatch_type,
            item_key="verdictAttestation",
            validate_contract=deps.validate_trust_verdict_attestation_contract,
            violation_code="trust_verdict_attestation_contract_violation",
            build_trust_phasea_bundle=deps.build_trust_phasea_bundle,
        )

    @app.get("/internal/judge/cases/{case_id}/trust/challenges")
    async def get_judge_trust_challenge_review(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.build_validated_trust_item_payload(
            case_id=case_id,
            dispatch_type=dispatch_type,
            item_key="challengeReview",
            validate_contract=deps.validate_trust_challenge_review_contract,
            violation_code="trust_challenge_review_contract_violation",
            build_trust_phasea_bundle=deps.build_trust_phasea_bundle,
        )

    @app.get("/internal/judge/trust/challenges/ops-queue")
    async def list_judge_trust_challenge_ops_queue(
        x_ai_internal_key: str | None = Header(default=None),
        status: str | None = Query(default=None),
        dispatch_type: str = Query(default="auto"),
        challenge_state: str | None = Query(default="open"),
        review_state: str | None = Query(default=None),
        priority_level: str | None = Query(default=None),
        sla_bucket: str | None = Query(default=None),
        has_open_alert: bool | None = Query(default=None),
        sort_by: str = Query(default="priority_score"),
        sort_order: str = Query(default="desc"),
        scan_limit: int = Query(default=500, ge=20, le=2000),
        offset: int = Query(default=0, ge=0, le=5000),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.build_trust_challenge_ops_queue_payload(
            status=status,
            dispatch_type=dispatch_type,
            challenge_state=challenge_state,
            review_state=review_state,
            priority_level=priority_level,
            sla_bucket=sla_bucket,
            has_open_alert=has_open_alert,
            sort_by=sort_by,
            sort_order=sort_order,
            scan_limit=scan_limit,
            offset=offset,
            limit=limit,
            workflow_list_jobs=deps.workflow_list_jobs,
            build_trust_phasea_bundle=deps.build_trust_phasea_bundle,
            get_trace=deps.get_trace,
            build_trust_challenge_priority_profile=(
                deps.build_trust_challenge_priority_profile
            ),
            serialize_workflow_job=deps.serialize_workflow_job,
            build_trust_challenge_action_hints=deps.build_trust_challenge_action_hints,
            run_trust_challenge_guard=deps.run_trust_challenge_guard,
        )

    @app.post("/internal/judge/cases/{case_id}/trust/challenges/request")
    async def request_judge_trust_challenge(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
        reason_code: str = Query(default="manual_challenge"),
        reason: str | None = Query(default=None),
        requested_by: str | None = Query(default=None),
        auto_accept: bool = Query(default=True),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.build_trust_challenge_request_payload(
            case_id=case_id,
            dispatch_type=dispatch_type,
            reason_code=reason_code,
            reason=reason,
            requested_by=requested_by,
            auto_accept=auto_accept,
            trust_challenge_common_dependencies=(
                deps.trust_challenge_common_dependencies
            ),
            upsert_audit_alert=deps.upsert_audit_alert,
            sync_audit_alert_to_facts=deps.sync_audit_alert_to_facts,
            run_trust_challenge_guard=deps.run_trust_challenge_guard,
        )

    @app.post(
        "/internal/judge/cases/{case_id}/trust/challenges/{challenge_id}/decision"
    )
    async def decide_judge_trust_challenge(
        case_id: int,
        challenge_id: str,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
        decision: str = Query(default="uphold"),
        actor: str | None = Query(default=None),
        reason: str | None = Query(default=None),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.build_trust_challenge_decision_payload(
            case_id=case_id,
            challenge_id=challenge_id,
            dispatch_type=dispatch_type,
            decision=decision,
            actor=actor,
            reason=reason,
            trust_challenge_common_dependencies=(
                deps.trust_challenge_common_dependencies
            ),
            workflow_mark_completed=deps.workflow_mark_completed,
            workflow_mark_draw_pending_vote=deps.workflow_mark_draw_pending_vote,
            resolve_open_alerts_for_review=deps.resolve_open_alerts_for_review,
            run_trust_challenge_guard=deps.run_trust_challenge_guard,
        )

    @app.get("/internal/judge/cases/{case_id}/trust/kernel-version")
    async def get_judge_trust_kernel_version(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.build_validated_trust_item_payload(
            case_id=case_id,
            dispatch_type=dispatch_type,
            item_key="kernelVersion",
            validate_contract=deps.validate_trust_kernel_version_contract,
            violation_code="trust_kernel_version_contract_violation",
            build_trust_phasea_bundle=deps.build_trust_phasea_bundle,
        )

    @app.get("/internal/judge/cases/{case_id}/trust/audit-anchor")
    async def get_judge_trust_audit_anchor(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
        include_payload: bool = Query(default=False),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.build_trust_audit_anchor_payload(
            case_id=case_id,
            dispatch_type=dispatch_type,
            include_payload=include_payload,
            build_trust_phasea_bundle=deps.build_trust_phasea_bundle,
            build_audit_anchor_export=deps.build_audit_anchor_export,
            validate_contract=deps.validate_trust_audit_anchor_contract,
            violation_code="trust_audit_anchor_contract_violation",
        )

    @app.get("/internal/judge/cases/{case_id}/trust/public-verify")
    async def get_judge_trust_public_verify(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.build_trust_public_verify_payload(
            case_id=case_id,
            dispatch_type=dispatch_type,
            build_trust_phasea_bundle=deps.build_trust_phasea_bundle,
            build_audit_anchor_export=deps.build_audit_anchor_export,
            build_public_verify_payload=deps.build_public_verify_payload,
            validate_contract=deps.validate_trust_public_verify_contract,
            violation_code="trust_public_verify_contract_violation",
        )

    @app.post("/internal/judge/cases/{case_id}/attestation/verify")
    async def verify_judge_report_attestation(
        case_id: int,
        x_ai_internal_key: str | None = Header(default=None),
        dispatch_type: str = Query(default="auto"),
    ) -> dict[str, Any]:
        deps.require_internal_key_fn(runtime.settings, x_ai_internal_key)
        return await deps.run_trust_read_guard(
            build_trust_attestation_verify_payload_v3(
                case_id=case_id,
                dispatch_type=dispatch_type,
                get_dispatch_receipt=deps.get_dispatch_receipt,
                verify_report_attestation=deps.verify_report_attestation,
            )
        )

    return TrustRouteHandles(
        get_judge_trust_case_commitment=get_judge_trust_case_commitment,
        get_judge_trust_verdict_attestation=get_judge_trust_verdict_attestation,
        get_judge_trust_challenge_review=get_judge_trust_challenge_review,
        list_judge_trust_challenge_ops_queue=list_judge_trust_challenge_ops_queue,
        request_judge_trust_challenge=request_judge_trust_challenge,
        decide_judge_trust_challenge=decide_judge_trust_challenge,
        get_judge_trust_kernel_version=get_judge_trust_kernel_version,
        get_judge_trust_audit_anchor=get_judge_trust_audit_anchor,
        get_judge_trust_public_verify=get_judge_trust_public_verify,
        verify_judge_report_attestation=verify_judge_report_attestation,
    )
