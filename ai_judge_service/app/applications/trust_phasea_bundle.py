from __future__ import annotations

from typing import Any

from .trust_attestation import verify_report_attestation
from .trust_phasea import (
    build_case_commitment_registry,
    build_challenge_review_registry,
    build_judge_kernel_registry,
    build_verdict_attestation_registry,
)


def build_trust_phasea_bundle(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    request_snapshot: dict[str, Any] | None,
    report_payload: dict[str, Any] | None,
    workflow_snapshot: dict[str, Any] | None,
    workflow_status: str | None,
    workflow_events: list[Any],
    alerts: list[Any],
    provider: str,
) -> dict[str, Any]:
    verify_result = verify_report_attestation(
        report_payload=report_payload if isinstance(report_payload, dict) else {},
        dispatch_type=dispatch_type,
    )
    commitment = build_case_commitment_registry(
        case_id=case_id,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        request_snapshot=request_snapshot,
        workflow_snapshot=workflow_snapshot,
        report_payload=report_payload,
    )
    verdict_attestation = build_verdict_attestation_registry(
        case_id=case_id,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        report_payload=report_payload,
        verify_result=verify_result,
    )
    challenge_review = build_challenge_review_registry(
        case_id=case_id,
        trace_id=trace_id,
        workflow_status=workflow_status,
        workflow_events=workflow_events,
        alerts=alerts,
        report_payload=report_payload,
    )
    kernel_version = build_judge_kernel_registry(
        case_id=case_id,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        report_payload=report_payload,
        workflow_events=workflow_events,
        provider=provider,
    )
    return {
        "verifyResult": verify_result,
        "commitment": commitment,
        "verdictAttestation": verdict_attestation,
        "challengeReview": challenge_review,
        "kernelVersion": kernel_version,
    }
