from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from app.domain.trust import TRUST_REGISTRY_VERSION, TrustRegistrySnapshot

from .trust_phasea_bundle import build_trust_phasea_bundle
from .trust_public_verify_contract import build_trust_public_verify_visibility_contract

TRUST_READ_DISPATCH_TYPES: frozenset[str] = frozenset({"auto", "phase", "final"})


@dataclass(frozen=True)
class TrustReadRouteError(Exception):
    status_code: int
    detail: Any


def normalize_trust_read_dispatch_type(dispatch_type: str) -> str:
    normalized = str(dispatch_type or "auto").strip().lower()
    if normalized not in TRUST_READ_DISPATCH_TYPES:
        raise ValueError("invalid_dispatch_type")
    return normalized


def choose_trust_read_dispatch_receipt(
    *,
    dispatch_type: str,
    final_receipt: Any | None = None,
    phase_receipt: Any | None = None,
    explicit_receipt: Any | None = None,
) -> tuple[str, Any | None]:
    if dispatch_type == "auto":
        if final_receipt is not None:
            return "final", final_receipt
        if phase_receipt is not None:
            return "phase", phase_receipt
        return "auto", None
    return dispatch_type, explicit_receipt


async def choose_trust_read_registry_snapshot(
    *,
    dispatch_type: str,
    case_id: int,
    get_trust_registry_snapshot: Any,
) -> tuple[str, TrustRegistrySnapshot | None]:
    if get_trust_registry_snapshot is None:
        return dispatch_type, None
    if dispatch_type == "auto":
        final_snapshot = await get_trust_registry_snapshot(
            case_id=case_id,
            dispatch_type="final",
        )
        if final_snapshot is not None:
            return "final", final_snapshot
        phase_snapshot = await get_trust_registry_snapshot(
            case_id=case_id,
            dispatch_type="phase",
        )
        if phase_snapshot is not None:
            return "phase", phase_snapshot
        return "auto", None
    snapshot = await get_trust_registry_snapshot(
        case_id=case_id,
        dispatch_type=dispatch_type,
    )
    return dispatch_type, snapshot


def build_trust_phasea_bundle_from_registry_snapshot(
    *,
    snapshot: TrustRegistrySnapshot,
) -> dict[str, Any]:
    normalized = snapshot.normalized()
    return {
        "context": {
            "dispatchType": normalized.dispatch_type,
            "traceId": normalized.trace_id,
            "source": "trust_registry",
            "registryVersion": normalized.registry_version,
        },
        "verifyResult": {
            "verified": bool(normalized.verdict_attestation.get("verified")),
            "reason": normalized.verdict_attestation.get("reason"),
            "mismatchComponents": (
                list(normalized.verdict_attestation.get("mismatchComponents"))
                if isinstance(normalized.verdict_attestation.get("mismatchComponents"), list)
                else []
            ),
        },
        "commitment": dict(normalized.case_commitment),
        "verdictAttestation": dict(normalized.verdict_attestation),
        "challengeReview": dict(normalized.challenge_review),
        "kernelVersion": dict(normalized.kernel_version),
        "auditAnchor": dict(normalized.audit_anchor),
        "publicVerify": dict(normalized.public_verify),
        "componentHashes": dict(normalized.component_hashes),
    }


def build_trust_report_context_from_receipt(
    *,
    dispatch_type: str,
    receipt: Any,
) -> dict[str, Any]:
    response_payload = (
        receipt.response if isinstance(getattr(receipt, "response", None), dict) else {}
    )
    request_snapshot = (
        receipt.request if isinstance(getattr(receipt, "request", None), dict) else {}
    )
    report_payload = (
        response_payload.get("reportPayload")
        if isinstance(response_payload.get("reportPayload"), dict)
        else None
    )
    if report_payload is None:
        raise ValueError("trust_report_payload_missing")
    judge_trace = (
        report_payload.get("judgeTrace")
        if isinstance(report_payload.get("judgeTrace"), dict)
        else {}
    )
    trace_id = str(
        getattr(receipt, "trace_id", None)
        or response_payload.get("traceId")
        or request_snapshot.get("traceId")
        or judge_trace.get("traceId")
        or ""
    ).strip()
    return {
        "dispatchType": dispatch_type,
        "receipt": receipt,
        "traceId": trace_id,
        "requestSnapshot": request_snapshot,
        "responsePayload": response_payload,
        "reportPayload": report_payload,
    }


async def resolve_trust_report_context_for_case(
    *,
    case_id: int,
    dispatch_type: str,
    get_dispatch_receipt: Any,
    not_found_detail: str,
    missing_report_detail: str,
) -> dict[str, Any]:
    try:
        dispatch_type_normalized = normalize_trust_read_dispatch_type(dispatch_type)
    except ValueError as err:
        raise TrustReadRouteError(status_code=422, detail="invalid_dispatch_type") from err

    if dispatch_type_normalized == "auto":
        final_receipt = await get_dispatch_receipt(dispatch_type="final", job_id=case_id)
        phase_receipt = await get_dispatch_receipt(dispatch_type="phase", job_id=case_id)
        chosen_dispatch_type, chosen_receipt = choose_trust_read_dispatch_receipt(
            dispatch_type=dispatch_type_normalized,
            final_receipt=final_receipt,
            phase_receipt=phase_receipt,
        )
    else:
        explicit_receipt = await get_dispatch_receipt(
            dispatch_type=dispatch_type_normalized,
            job_id=case_id,
        )
        chosen_dispatch_type, chosen_receipt = choose_trust_read_dispatch_receipt(
            dispatch_type=dispatch_type_normalized,
            explicit_receipt=explicit_receipt,
        )

    if chosen_receipt is None:
        raise TrustReadRouteError(status_code=404, detail=not_found_detail)
    try:
        return build_trust_report_context_from_receipt(
            dispatch_type=chosen_dispatch_type,
            receipt=chosen_receipt,
        )
    except ValueError as err:
        if str(err) == "trust_report_payload_missing":
            raise TrustReadRouteError(status_code=409, detail=missing_report_detail) from err
        raise


async def build_trust_phasea_bundle_for_case(
    *,
    case_id: int,
    dispatch_type: str,
    get_dispatch_receipt: Any,
    get_workflow_job: Any,
    list_workflow_events: Any,
    list_audit_alerts: Any,
    serialize_workflow_job: Any,
    provider: str,
    get_trust_registry_snapshot: Any | None = None,
) -> dict[str, Any]:
    try:
        dispatch_type_normalized = normalize_trust_read_dispatch_type(dispatch_type)
    except ValueError as err:
        raise TrustReadRouteError(status_code=422, detail="invalid_dispatch_type") from err

    registry_dispatch_type, registry_snapshot = await choose_trust_read_registry_snapshot(
        dispatch_type=dispatch_type_normalized,
        case_id=case_id,
        get_trust_registry_snapshot=get_trust_registry_snapshot,
    )
    if registry_snapshot is not None:
        del registry_dispatch_type
        return build_trust_phasea_bundle_from_registry_snapshot(snapshot=registry_snapshot)

    context = await resolve_trust_report_context_for_case(
        case_id=case_id,
        dispatch_type=dispatch_type_normalized,
        get_dispatch_receipt=get_dispatch_receipt,
        not_found_detail="trust_receipt_not_found",
        missing_report_detail="trust_report_payload_missing",
    )
    workflow_job = await get_workflow_job(job_id=case_id)
    workflow_events = list(await list_workflow_events(job_id=case_id))
    alerts = await list_audit_alerts(job_id=case_id, status=None, limit=200)
    workflow_snapshot = (
        serialize_workflow_job(workflow_job) if workflow_job is not None else None
    )
    bundle_payload = build_trust_phasea_bundle(
        case_id=case_id,
        dispatch_type=context["dispatchType"],
        trace_id=context["traceId"],
        request_snapshot=context["requestSnapshot"],
        report_payload=context["reportPayload"],
        workflow_snapshot=workflow_snapshot,
        workflow_status=workflow_job.status if workflow_job is not None else None,
        workflow_events=workflow_events,
        alerts=alerts,
        provider=provider,
    )
    return {"context": {**context, "source": "derived_from_receipt"}, **bundle_payload}


def _coerce_audit_alerts(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    out: list[Any] = []
    for item in value:
        if isinstance(item, dict):
            out.append(SimpleNamespace(**item))
        else:
            out.append(item)
    return out


def _component_hashes_from_anchor(audit_anchor: dict[str, Any]) -> dict[str, Any]:
    component_hashes = (
        dict(audit_anchor.get("componentHashes"))
        if isinstance(audit_anchor.get("componentHashes"), dict)
        else {}
    )
    anchor_hash = str(audit_anchor.get("anchorHash") or "").strip()
    if anchor_hash:
        component_hashes["auditAnchorHash"] = anchor_hash
    return component_hashes


def build_trust_registry_snapshot_from_bundle(
    *,
    case_id: int,
    bundle: dict[str, Any],
    build_audit_anchor_export: Any,
    build_public_verify_payload: Any,
    registry_version: str = TRUST_REGISTRY_VERSION,
) -> TrustRegistrySnapshot:
    context = bundle["context"] if isinstance(bundle.get("context"), dict) else {}
    dispatch_type = str(context.get("dispatchType") or "").strip().lower()
    trace_id = str(context.get("traceId") or "").strip()
    commitment = dict(bundle["commitment"]) if isinstance(bundle.get("commitment"), dict) else {}
    verdict_attestation = (
        dict(bundle["verdictAttestation"])
        if isinstance(bundle.get("verdictAttestation"), dict)
        else {}
    )
    challenge_review = (
        dict(bundle["challengeReview"])
        if isinstance(bundle.get("challengeReview"), dict)
        else {}
    )
    kernel_version = dict(bundle["kernelVersion"]) if isinstance(bundle.get("kernelVersion"), dict) else {}
    audit_anchor = build_audit_anchor_export(
        case_id=case_id,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        case_commitment=commitment,
        verdict_attestation=verdict_attestation,
        challenge_review=challenge_review,
        kernel_version=kernel_version,
        include_payload=False,
    )
    public_verify = build_trust_public_verify_route_payload(
        case_id=case_id,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        verify_payload=build_public_verify_payload(
            commitment=commitment,
            verdict_attestation=verdict_attestation,
            challenge_review=challenge_review,
            kernel_version=kernel_version,
            audit_anchor=audit_anchor,
        ),
    )
    return TrustRegistrySnapshot(
        case_id=int(case_id),
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        registry_version=registry_version,
        case_commitment=commitment,
        verdict_attestation=verdict_attestation,
        challenge_review=challenge_review,
        kernel_version=kernel_version,
        audit_anchor=dict(audit_anchor),
        public_verify=public_verify,
        component_hashes=_component_hashes_from_anchor(audit_anchor),
    )


async def write_trust_registry_snapshot_for_report(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    request_snapshot: dict[str, Any] | None,
    report_payload: dict[str, Any] | None,
    workflow_snapshot: dict[str, Any] | None,
    workflow_status: str | None,
    workflow_events: list[Any] | None,
    alerts: list[Any] | None,
    provider: str,
    upsert_trust_registry_snapshot: Any,
    build_audit_anchor_export: Any,
    build_public_verify_payload: Any,
    registry_version: str = TRUST_REGISTRY_VERSION,
) -> TrustRegistrySnapshot:
    bundle = build_trust_phasea_bundle(
        case_id=case_id,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        request_snapshot=request_snapshot,
        report_payload=report_payload,
        workflow_snapshot=workflow_snapshot,
        workflow_status=workflow_status,
        workflow_events=list(workflow_events or []),
        alerts=_coerce_audit_alerts(alerts),
        provider=provider,
    )
    bundle["context"] = {
        "dispatchType": str(dispatch_type or "").strip().lower(),
        "traceId": str(trace_id or "").strip(),
        "source": "write_through_report",
        "registryVersion": registry_version,
    }
    snapshot = build_trust_registry_snapshot_from_bundle(
        case_id=case_id,
        bundle=bundle,
        build_audit_anchor_export=build_audit_anchor_export,
        build_public_verify_payload=build_public_verify_payload,
        registry_version=registry_version,
    )
    # Trust Registry 是裁决事实的制度化承诺层；写入失败必须显式暴露，不能伪装成功。
    return await upsert_trust_registry_snapshot(snapshot=snapshot)


async def build_trust_attestation_verify_payload(
    *,
    case_id: int,
    dispatch_type: str,
    get_dispatch_receipt: Any,
    verify_report_attestation: Any,
) -> dict[str, Any]:
    context = await resolve_trust_report_context_for_case(
        case_id=case_id,
        dispatch_type=dispatch_type,
        get_dispatch_receipt=get_dispatch_receipt,
        not_found_detail="attestation_receipt_not_found",
        missing_report_detail="attestation_report_payload_missing",
    )
    verify_result = verify_report_attestation(
        report_payload=context["reportPayload"],
        dispatch_type=context["dispatchType"],
    )
    verify_result_payload = (
        dict(verify_result) if isinstance(verify_result, dict) else {}
    )
    return {
        "caseId": int(case_id),
        "dispatchType": str(context["dispatchType"]),
        "traceId": str(context["traceId"]),
        **verify_result_payload,
    }


def build_trust_item_route_payload(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    item: dict[str, Any] | Any,
) -> dict[str, Any]:
    item_payload = dict(item) if isinstance(item, dict) else item
    return {
        "caseId": int(case_id),
        "dispatchType": str(dispatch_type),
        "traceId": str(trace_id),
        "item": item_payload,
    }


def build_trust_public_verify_route_payload(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    verify_payload: dict[str, Any] | Any,
) -> dict[str, Any]:
    verify_payload_dict = (
        dict(verify_payload) if isinstance(verify_payload, dict) else verify_payload
    )
    return {
        "caseId": int(case_id),
        "dispatchType": str(dispatch_type),
        "traceId": str(trace_id),
        "verifyPayload": verify_payload_dict,
        "visibilityContract": build_trust_public_verify_visibility_contract(),
    }


def validate_trust_route_contract_payload(
    *,
    payload: dict[str, Any],
    validate_contract: Any,
    violation_code: str,
) -> dict[str, Any]:
    try:
        validate_contract(payload)
    except ValueError as err:
        raise TrustReadRouteError(
            status_code=500,
            detail={
                "code": str(violation_code),
                "message": str(err),
            },
        ) from err
    return payload


def build_validated_trust_item_route_payload(
    *,
    case_id: int,
    bundle: dict[str, Any],
    item_key: str,
    validate_contract: Any,
    violation_code: str,
) -> dict[str, Any]:
    context = bundle["context"] if isinstance(bundle.get("context"), dict) else {}
    payload = build_trust_item_route_payload(
        case_id=case_id,
        dispatch_type=str(context.get("dispatchType") or ""),
        trace_id=str(context.get("traceId") or ""),
        item=bundle[item_key],
    )
    return validate_trust_route_contract_payload(
        payload=payload,
        validate_contract=validate_contract,
        violation_code=violation_code,
    )


def build_trust_audit_anchor_route_payload(
    *,
    case_id: int,
    bundle: dict[str, Any],
    include_payload: bool,
    build_audit_anchor_export: Any,
    validate_contract: Any,
    violation_code: str,
) -> dict[str, Any]:
    context = bundle["context"] if isinstance(bundle.get("context"), dict) else {}
    commitment = dict(bundle["commitment"]) if isinstance(bundle.get("commitment"), dict) else {}
    verdict_attestation = (
        dict(bundle["verdictAttestation"])
        if isinstance(bundle.get("verdictAttestation"), dict)
        else {}
    )
    challenge_review = (
        dict(bundle["challengeReview"])
        if isinstance(bundle.get("challengeReview"), dict)
        else {}
    )
    kernel_version = dict(bundle["kernelVersion"]) if isinstance(bundle.get("kernelVersion"), dict) else {}
    anchor = build_audit_anchor_export(
        case_id=case_id,
        dispatch_type=context.get("dispatchType"),
        trace_id=context.get("traceId"),
        case_commitment=commitment,
        verdict_attestation=verdict_attestation,
        challenge_review=challenge_review,
        kernel_version=kernel_version,
        include_payload=bool(include_payload),
    )
    payload = build_trust_item_route_payload(
        case_id=case_id,
        dispatch_type=str(context.get("dispatchType") or ""),
        trace_id=str(context.get("traceId") or ""),
        item=anchor,
    )
    return validate_trust_route_contract_payload(
        payload=payload,
        validate_contract=validate_contract,
        violation_code=violation_code,
    )


def build_trust_public_verify_bundle_payload(
    *,
    case_id: int,
    bundle: dict[str, Any],
    build_audit_anchor_export: Any,
    build_public_verify_payload: Any,
    validate_contract: Any,
    violation_code: str,
) -> dict[str, Any]:
    context = bundle["context"] if isinstance(bundle.get("context"), dict) else {}
    commitment = dict(bundle["commitment"]) if isinstance(bundle.get("commitment"), dict) else {}
    verdict_attestation = (
        dict(bundle["verdictAttestation"])
        if isinstance(bundle.get("verdictAttestation"), dict)
        else {}
    )
    challenge_review = (
        dict(bundle["challengeReview"])
        if isinstance(bundle.get("challengeReview"), dict)
        else {}
    )
    kernel_version = dict(bundle["kernelVersion"]) if isinstance(bundle.get("kernelVersion"), dict) else {}
    audit_anchor = build_audit_anchor_export(
        case_id=case_id,
        dispatch_type=context.get("dispatchType"),
        trace_id=context.get("traceId"),
        case_commitment=commitment,
        verdict_attestation=verdict_attestation,
        challenge_review=challenge_review,
        kernel_version=kernel_version,
        include_payload=False,
    )
    payload = build_trust_public_verify_route_payload(
        case_id=case_id,
        dispatch_type=str(context.get("dispatchType") or ""),
        trace_id=str(context.get("traceId") or ""),
        verify_payload=build_public_verify_payload(
            commitment=commitment,
            verdict_attestation=verdict_attestation,
            challenge_review=challenge_review,
            kernel_version=kernel_version,
            audit_anchor=audit_anchor,
        ),
    )
    return validate_trust_route_contract_payload(
        payload=payload,
        validate_contract=validate_contract,
        violation_code=violation_code,
    )
