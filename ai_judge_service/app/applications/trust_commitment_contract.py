from __future__ import annotations

from typing import Any

TRUST_COMMITMENT_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "caseId",
    "dispatchType",
    "traceId",
    "item",
)

TRUST_COMMITMENT_ITEM_KEYS: tuple[str, ...] = (
    "version",
    "caseId",
    "dispatchType",
    "traceId",
    "requestHash",
    "workflowHash",
    "reportHash",
    "attestationCommitmentHash",
    "commitmentHash",
)


def _required_keys_missing(payload: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    return [key for key in keys if key not in payload]


def _assert_required_keys(
    *,
    section: str,
    payload: dict[str, Any],
    keys: tuple[str, ...],
) -> None:
    missing = _required_keys_missing(payload, keys)
    if missing:
        raise ValueError(f"{section}_missing_keys:{','.join(sorted(missing))}")


def _non_negative_int(value: Any, *, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return default
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, parsed)


def _assert_non_empty_string(section: str, value: Any) -> None:
    if not str(value or "").strip():
        raise ValueError(f"{section}_empty")


def validate_trust_commitment_contract(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("trust_commitment_payload_not_dict")
    _assert_required_keys(
        section="trust_commitment",
        payload=payload,
        keys=TRUST_COMMITMENT_TOP_LEVEL_KEYS,
    )
    case_id = _non_negative_int(payload.get("caseId"), default=0)
    if case_id <= 0:
        raise ValueError("trust_commitment_case_id_invalid")
    dispatch_type = str(payload.get("dispatchType") or "").strip().lower()
    if dispatch_type not in {"phase", "final"}:
        raise ValueError("trust_commitment_dispatch_type_invalid")
    _assert_non_empty_string("trust_commitment_trace_id", payload.get("traceId"))

    item = payload.get("item")
    if not isinstance(item, dict):
        raise ValueError("trust_commitment_item_not_dict")
    _assert_required_keys(
        section="trust_commitment_item",
        payload=item,
        keys=TRUST_COMMITMENT_ITEM_KEYS,
    )
    if _non_negative_int(item.get("caseId"), default=0) != case_id:
        raise ValueError("trust_commitment_item_case_id_mismatch")
    if str(item.get("dispatchType") or "").strip().lower() != dispatch_type:
        raise ValueError("trust_commitment_item_dispatch_type_mismatch")
    if str(item.get("traceId") or "").strip() != str(payload.get("traceId") or "").strip():
        raise ValueError("trust_commitment_item_trace_id_mismatch")
    _assert_non_empty_string("trust_commitment_item_version", item.get("version"))
    _assert_non_empty_string("trust_commitment_item_request_hash", item.get("requestHash"))
    _assert_non_empty_string("trust_commitment_item_workflow_hash", item.get("workflowHash"))
    _assert_non_empty_string("trust_commitment_item_report_hash", item.get("reportHash"))
    _assert_non_empty_string("trust_commitment_item_commitment_hash", item.get("commitmentHash"))

    attestation_commitment_hash = item.get("attestationCommitmentHash")
    if attestation_commitment_hash is None:
        return
    _assert_non_empty_string(
        "trust_commitment_item_attestation_commitment_hash",
        attestation_commitment_hash,
    )
