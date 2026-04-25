from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

TRUST_REGISTRY_VERSION = "trust-registry-v1"
PUBLIC_VERIFY_FORBIDDEN_KEYS = frozenset(
    {
        "email",
        "auditalerts",
        "content",
        "debatesummary",
        "fairnessdetails",
        "fairnessreport",
        "fairnesssummary",
        "historyreputation",
        "internalaudit",
        "internalfairnessdetails",
        "judgetrace",
        "messagecontent",
        "messages",
        "nickname",
        "phone",
        "prompt",
        "prompttext",
        "rawprompt",
        "rawtrace",
        "rawtranscript",
        "sideanalysis",
        "speakertag",
        "spend",
        "spending",
        "sourcemessages",
        "traceevents",
        "transcript",
        "transcriptsnapshot",
        "userid",
        "useridentity",
        "verdictreason",
        "wallet",
    }
)


def normalize_trust_dispatch_type(value: Any) -> str:
    token = str(value or "").strip().lower()
    if token in {"phase", "final"}:
        return token
    return "unknown"


def _normalize_key(value: Any) -> str:
    return str(value or "").strip().replace("_", "").replace("-", "").lower()


def _dict_payload(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _copy_public_payload(value: Any) -> dict[str, Any]:
    payload = _dict_payload(value)
    violations = sorted(find_public_verify_forbidden_keys(payload))
    if violations:
        raise ValueError(f"trust_registry_public_verify_forbidden_keys:{','.join(violations)}")
    return payload


def find_public_verify_forbidden_keys(payload: Any) -> set[str]:
    violations: set[str] = set()

    def _walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                normalized_key = _normalize_key(key)
                if normalized_key in PUBLIC_VERIFY_FORBIDDEN_KEYS:
                    violations.add(str(key))
                _walk(child)
        elif isinstance(value, list):
            for child in value:
                _walk(child)

    _walk(payload)
    return violations


@dataclass(frozen=True)
class TrustRegistrySnapshot:
    case_id: int
    dispatch_type: str
    trace_id: str
    case_commitment: dict[str, Any]
    verdict_attestation: dict[str, Any]
    challenge_review: dict[str, Any]
    kernel_version: dict[str, Any]
    audit_anchor: dict[str, Any]
    public_verify: dict[str, Any]
    component_hashes: dict[str, Any]
    registry_version: str = TRUST_REGISTRY_VERSION
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def normalized(self) -> TrustRegistrySnapshot:
        return TrustRegistrySnapshot(
            case_id=int(self.case_id),
            dispatch_type=normalize_trust_dispatch_type(self.dispatch_type),
            trace_id=str(self.trace_id or "").strip(),
            registry_version=str(self.registry_version or "").strip() or TRUST_REGISTRY_VERSION,
            case_commitment=_dict_payload(self.case_commitment),
            verdict_attestation=_dict_payload(self.verdict_attestation),
            challenge_review=_dict_payload(self.challenge_review),
            kernel_version=_dict_payload(self.kernel_version),
            audit_anchor=_dict_payload(self.audit_anchor),
            public_verify=_copy_public_payload(self.public_verify),
            component_hashes=_dict_payload(self.component_hashes),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def to_payload(self) -> dict[str, Any]:
        normalized = self.normalized()
        return {
            "caseId": normalized.case_id,
            "dispatchType": normalized.dispatch_type,
            "traceId": normalized.trace_id,
            "registryVersion": normalized.registry_version,
            "caseCommitment": dict(normalized.case_commitment),
            "verdictAttestation": dict(normalized.verdict_attestation),
            "challengeReview": dict(normalized.challenge_review),
            "kernelVersion": dict(normalized.kernel_version),
            "auditAnchor": dict(normalized.audit_anchor),
            "publicVerify": dict(normalized.public_verify),
            "componentHashes": dict(normalized.component_hashes),
        }


@dataclass(frozen=True)
class TrustChallengeEvent:
    event_type: str
    challenge_id: str
    state: str
    actor: str | None = None
    reason_code: str | None = None
    reason: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "eventType": str(self.event_type or "").strip(),
            "challengeId": str(self.challenge_id or "").strip(),
            "state": str(self.state or "").strip().lower(),
            "actor": str(self.actor or "").strip() or None,
            "reasonCode": str(self.reason_code or "").strip() or None,
            "reason": str(self.reason or "").strip() or None,
            "payload": dict(self.payload),
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


def validate_trust_registry_snapshot(snapshot: TrustRegistrySnapshot) -> list[str]:
    errors: list[str] = []
    try:
        normalized = snapshot.normalized()
    except ValueError as err:
        return [str(err)]

    if normalized.case_id <= 0:
        errors.append("case_id_invalid")
    if normalized.dispatch_type not in {"phase", "final"}:
        errors.append("dispatch_type_invalid")
    if not normalized.trace_id:
        errors.append("trace_id_required")
    if not normalized.registry_version:
        errors.append("registry_version_required")

    components = {
        "case_commitment": normalized.case_commitment,
        "verdict_attestation": normalized.verdict_attestation,
        "challenge_review": normalized.challenge_review,
        "kernel_version": normalized.kernel_version,
        "audit_anchor": normalized.audit_anchor,
        "public_verify": normalized.public_verify,
    }
    for component_name, component in components.items():
        if not component:
            errors.append(f"{component_name}_required")
            continue
        component_case_id = component.get("caseId")
        if component_case_id is not None:
            parsed_case_id = _safe_int(component_case_id)
            if parsed_case_id is None:
                errors.append(f"{component_name}_case_id_invalid")
            elif parsed_case_id != normalized.case_id:
                errors.append(f"{component_name}_case_id_mismatch")
        component_dispatch = component.get("dispatchType")
        if (
            component_dispatch is not None
            and normalize_trust_dispatch_type(component_dispatch) != normalized.dispatch_type
        ):
            errors.append(f"{component_name}_dispatch_type_mismatch")
        component_trace_id = str(component.get("traceId") or "").strip()
        if component_trace_id and component_trace_id != normalized.trace_id:
            errors.append(f"{component_name}_trace_id_mismatch")

    if not normalized.component_hashes:
        errors.append("component_hashes_required")
    else:
        for key, value in normalized.component_hashes.items():
            if not str(key or "").strip():
                errors.append("component_hashes_key_required")
            if not str(value or "").strip():
                errors.append(f"component_hashes_{key}_required")

    forbidden_keys = sorted(find_public_verify_forbidden_keys(normalized.public_verify))
    if forbidden_keys:
        errors.append(f"public_verify_forbidden_keys:{','.join(forbidden_keys)}")

    return errors
