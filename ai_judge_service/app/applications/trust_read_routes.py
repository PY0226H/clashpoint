from __future__ import annotations

from typing import Any

TRUST_READ_DISPATCH_TYPES: frozenset[str] = frozenset({"auto", "phase", "final"})


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
    }
