from __future__ import annotations

from typing import Any

TRUST_VERDICT_ATTESTATION_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "caseId",
    "dispatchType",
    "traceId",
    "item",
)

TRUST_VERDICT_ATTESTATION_ITEM_KEYS: tuple[str, ...] = (
    "version",
    "caseId",
    "dispatchType",
    "traceId",
    "attestation",
    "verified",
    "reason",
    "mismatchComponents",
    "registryHash",
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


def validate_trust_verdict_attestation_contract(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("trust_verdict_attestation_payload_not_dict")
    _assert_required_keys(
        section="trust_verdict_attestation",
        payload=payload,
        keys=TRUST_VERDICT_ATTESTATION_TOP_LEVEL_KEYS,
    )
    case_id = _non_negative_int(payload.get("caseId"), default=0)
    if case_id <= 0:
        raise ValueError("trust_verdict_attestation_case_id_invalid")
    dispatch_type = str(payload.get("dispatchType") or "").strip().lower()
    if dispatch_type not in {"phase", "final"}:
        raise ValueError("trust_verdict_attestation_dispatch_type_invalid")
    _assert_non_empty_string("trust_verdict_attestation_trace_id", payload.get("traceId"))

    item = payload.get("item")
    if not isinstance(item, dict):
        raise ValueError("trust_verdict_attestation_item_not_dict")
    _assert_required_keys(
        section="trust_verdict_attestation_item",
        payload=item,
        keys=TRUST_VERDICT_ATTESTATION_ITEM_KEYS,
    )
    if _non_negative_int(item.get("caseId"), default=0) != case_id:
        raise ValueError("trust_verdict_attestation_item_case_id_mismatch")
    if str(item.get("dispatchType") or "").strip().lower() != dispatch_type:
        raise ValueError("trust_verdict_attestation_item_dispatch_type_mismatch")
    if str(item.get("traceId") or "").strip() != str(payload.get("traceId") or "").strip():
        raise ValueError("trust_verdict_attestation_item_trace_id_mismatch")
    _assert_non_empty_string("trust_verdict_attestation_item_version", item.get("version"))
    _assert_non_empty_string(
        "trust_verdict_attestation_item_registry_hash",
        item.get("registryHash"),
    )

    if not isinstance(item.get("attestation"), dict):
        raise ValueError("trust_verdict_attestation_item_attestation_not_dict")
    if not isinstance(item.get("verified"), bool):
        raise ValueError("trust_verdict_attestation_item_verified_not_bool")
    mismatch_components = item.get("mismatchComponents")
    if not isinstance(mismatch_components, list):
        raise ValueError("trust_verdict_attestation_item_mismatch_components_not_list")
    for component in mismatch_components:
        if not str(component or "").strip():
            raise ValueError("trust_verdict_attestation_item_mismatch_component_empty")

    reason = item.get("reason")
    if reason is not None and not str(reason).strip():
        raise ValueError("trust_verdict_attestation_item_reason_empty")
