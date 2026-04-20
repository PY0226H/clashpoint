from __future__ import annotations

from typing import Any

TRUST_KERNEL_VERSION_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "caseId",
    "dispatchType",
    "traceId",
    "item",
)

TRUST_KERNEL_VERSION_ITEM_KEYS: tuple[str, ...] = (
    "version",
    "caseId",
    "traceId",
    "kernelVector",
    "kernelHash",
    "registryHash",
)

TRUST_KERNEL_VERSION_VECTOR_KEYS: tuple[str, ...] = (
    "dispatchType",
    "provider",
    "judgeCoreVersion",
    "pipelineVersion",
    "policyVersion",
    "promptVersion",
    "toolsetVersion",
    "agentRuntimeVersion",
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


def validate_trust_kernel_version_contract(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("trust_kernel_version_payload_not_dict")
    _assert_required_keys(
        section="trust_kernel_version",
        payload=payload,
        keys=TRUST_KERNEL_VERSION_TOP_LEVEL_KEYS,
    )
    case_id = _non_negative_int(payload.get("caseId"), default=0)
    if case_id <= 0:
        raise ValueError("trust_kernel_version_case_id_invalid")
    dispatch_type = str(payload.get("dispatchType") or "").strip().lower()
    if dispatch_type not in {"phase", "final"}:
        raise ValueError("trust_kernel_version_dispatch_type_invalid")
    _assert_non_empty_string("trust_kernel_version_trace_id", payload.get("traceId"))

    item = payload.get("item")
    if not isinstance(item, dict):
        raise ValueError("trust_kernel_version_item_not_dict")
    _assert_required_keys(
        section="trust_kernel_version_item",
        payload=item,
        keys=TRUST_KERNEL_VERSION_ITEM_KEYS,
    )
    if _non_negative_int(item.get("caseId"), default=0) != case_id:
        raise ValueError("trust_kernel_version_item_case_id_mismatch")
    if str(item.get("traceId") or "").strip() != str(payload.get("traceId") or "").strip():
        raise ValueError("trust_kernel_version_item_trace_id_mismatch")
    _assert_non_empty_string("trust_kernel_version_item_version", item.get("version"))
    _assert_non_empty_string("trust_kernel_version_item_kernel_hash", item.get("kernelHash"))
    _assert_non_empty_string("trust_kernel_version_item_registry_hash", item.get("registryHash"))

    kernel_vector = item.get("kernelVector")
    if not isinstance(kernel_vector, dict):
        raise ValueError("trust_kernel_version_kernel_vector_not_dict")
    _assert_required_keys(
        section="trust_kernel_version_kernel_vector",
        payload=kernel_vector,
        keys=TRUST_KERNEL_VERSION_VECTOR_KEYS,
    )
    vector_dispatch_type = str(kernel_vector.get("dispatchType") or "").strip().lower()
    if vector_dispatch_type not in {"phase", "final"}:
        raise ValueError("trust_kernel_version_vector_dispatch_type_invalid")
    _assert_non_empty_string("trust_kernel_version_vector_provider", kernel_vector.get("provider"))
