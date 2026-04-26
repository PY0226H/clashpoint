from __future__ import annotations

from typing import Any

from app.applications.fairness_panel_evidence import (
    build_fairness_panel_evidence_normalization,
)
from app.domain.judge.evidence_ledger import CITATION_VERIFICATION_VERSION

RELEASE_READINESS_EVIDENCE_VERSION = "policy-release-readiness-evidence-v1"

RELEASE_GATE_READY_STATUSES = {
    "ready",
    "readiness_ready",
    "pass",
    "passed",
    "accepted",
    "ok",
}
RELEASE_GATE_LOCAL_REFERENCE_STATUSES = {
    "local_reference_ready",
    "local_reference_frozen",
}
RELEASE_GATE_LOCAL_REFERENCE_ENVIRONMENTS = {
    "local",
    "local_reference",
    "local-reference",
}
RELEASE_GATE_BLOCKED_STATUSES = {
    "blocked",
    "failed",
    "fail",
    "error",
    "threshold_violation",
    "violation",
    "not_ready",
}
RELEASE_GATE_ENV_BLOCKED_STATUSES = {
    "env_blocked",
    "local_reference_ready",
    "pending_real_env",
    "pending_real_samples",
    "missing_real_env",
    "missing_real_samples",
}
RELEASE_GATE_EVIDENCE_STATUSES = {
    "allowed",
    "blocked",
    "env_blocked",
    "needs_review",
    "ready",
    "pending",
    "missing",
    "local_reference_ready",
    "local_reference_frozen",
    "warning",
}


def _extract_policy_metadata(dependency_health: dict[str, Any] | None) -> dict[str, Any]:
    payload = dependency_health if isinstance(dependency_health, dict) else {}
    profile = (
        payload.get("policyProfile")
        if isinstance(payload.get("policyProfile"), dict)
        else {}
    )
    return profile.get("metadata") if isinstance(profile.get("metadata"), dict) else {}


def _extract_release_readiness_section(metadata: dict[str, Any]) -> dict[str, Any]:
    for key in (
        "releaseGateInputs",
        "releaseReadiness",
        "release_gate_inputs",
        "release_readiness",
        "p37ReleaseReadiness",
    ):
        value = metadata.get(key)
        if isinstance(value, dict):
            return dict(value)
    return {}


def _safe_token(value: Any) -> str | None:
    token = str(value or "").strip()
    return token or None


def _lower_token(value: Any) -> str | None:
    token = _safe_token(value)
    return token.lower() if token is not None else None


def _is_local_reference_status(value: Any) -> bool:
    return (_lower_token(value) or "") in RELEASE_GATE_LOCAL_REFERENCE_STATUSES


def _is_local_reference_environment(value: Any) -> bool:
    return (_lower_token(value) or "") in RELEASE_GATE_LOCAL_REFERENCE_ENVIRONMENTS


def _is_local_reference_payload(payload: dict[str, Any]) -> bool:
    return _is_local_reference_status(
        payload.get("status") or payload.get("decision")
    ) or _is_local_reference_environment(
        payload.get("environmentMode") or payload.get("environment_mode")
    )


def _artifact_ref_from_payload(payload: dict[str, Any]) -> str | None:
    for key in ("evidenceRef", "evidence_ref", "artifactRef", "artifact_ref", "ref"):
        token = _safe_token(payload.get(key))
        if token:
            return token
    return None


def _coerce_release_component(
    *,
    name: str,
    raw: Any,
    missing_code: str,
    ready_message: str,
) -> dict[str, Any]:
    payload = raw if isinstance(raw, dict) else {}
    raw_status = str(payload.get("status") or payload.get("decision") or "").strip().lower()
    if not raw_status:
        raw_status = "missing"

    if raw_status in RELEASE_GATE_READY_STATUSES:
        status = "ready"
        code = f"registry_release_gate_{name}_ready"
        message = str(payload.get("message") or "").strip() or ready_message
    elif raw_status in RELEASE_GATE_LOCAL_REFERENCE_STATUSES:
        status = "env_blocked"
        code = (
            str(payload.get("code") or "").strip()
            or f"registry_release_gate_{name}_local_reference_only"
        )
        message = (
            str(payload.get("message") or "").strip()
            or f"{name} only has local reference evidence"
        )
    elif raw_status in RELEASE_GATE_BLOCKED_STATUSES:
        status = "blocked"
        code = (
            str(payload.get("code") or "").strip()
            or f"registry_release_gate_{name}_blocked"
        )
        message = str(payload.get("message") or "").strip() or f"{name} is blocked"
    elif raw_status in RELEASE_GATE_ENV_BLOCKED_STATUSES:
        status = "env_blocked"
        code = (
            str(payload.get("code") or "").strip()
            or f"registry_release_gate_{name}_env_blocked"
        )
        message = (
            str(payload.get("message") or "").strip()
            or f"{name} is blocked by missing real environment evidence"
        )
    else:
        status = "needs_review"
        code = str(payload.get("code") or "").strip() or missing_code
        message = (
            str(payload.get("message") or "").strip()
            or f"{name} requires review before release"
        )

    return {
        "name": name,
        "status": status,
        "code": code,
        "message": message,
        "sourceStatus": raw_status,
        "evidenceRef": _artifact_ref_from_payload(payload),
    }


def _fairness_run_is_local_reference(run: Any) -> bool:
    payload = run if isinstance(run, dict) else {}
    return _is_local_reference_payload(payload)


def _build_fairness_benchmark_release_component(
    *,
    fairness_gate: dict[str, Any] | None,
    release_inputs: dict[str, Any],
) -> dict[str, Any]:
    gate = fairness_gate if isinstance(fairness_gate, dict) else {}
    normalized = build_fairness_panel_evidence_normalization(
        fairness_gate=gate,
        release_inputs=release_inputs,
    )
    evidence_status = str(normalized.get("benchmarkEvidenceStatus") or "").strip().lower()
    if evidence_status == "ready":
        return {
            "name": "fairnessBenchmark",
            "status": "ready",
            "code": "registry_release_gate_fairness_benchmark_ready",
            "message": "fairness benchmark gate passed",
            "sourceStatus": str(gate.get("thresholdDecision") or "").strip() or None,
            "evidenceRef": None,
        }
    if evidence_status == "env_blocked":
        if _fairness_run_is_local_reference(gate.get("latestRun")):
            latest_run = gate.get("latestRun") if isinstance(gate.get("latestRun"), dict) else {}
            return {
                "name": "fairnessBenchmark",
                "status": "env_blocked",
                "code": "registry_release_gate_fairness_benchmark_local_reference_only",
                "message": "fairness benchmark only has local reference evidence",
                "sourceStatus": str(
                    latest_run.get("status") or gate.get("thresholdDecision") or ""
                ).strip()
                or None,
                "evidenceRef": _artifact_ref_from_payload(latest_run),
            }
    if evidence_status == "pending_real_samples":
        code = (
            str(gate.get("code") or "").strip()
            or "registry_release_gate_fairness_benchmark_pending_real_samples"
        )
        return {
            "name": "fairnessBenchmark",
            "status": "env_blocked",
            "code": code,
            "message": str(gate.get("message") or "").strip()
            or "fairness benchmark is waiting for real sample evidence",
            "sourceStatus": str(gate.get("thresholdDecision") or "").strip() or None,
            "evidenceRef": None,
        }
    code = (
        str(gate.get("code") or "").strip()
        or "registry_release_gate_fairness_benchmark_missing"
    )
    if code == "registry_fairness_gate_no_benchmark":
        status = "env_blocked"
    elif evidence_status == "blocked":
        status = "blocked"
    else:
        status = "needs_review"
    return {
        "name": "fairnessBenchmark",
        "status": status,
        "code": code,
        "message": str(gate.get("message") or "").strip()
        or "fairness benchmark gate did not pass",
        "sourceStatus": str(gate.get("thresholdDecision") or "").strip() or None,
        "evidenceRef": None,
    }


def _build_panel_shadow_release_component(
    *,
    fairness_gate: dict[str, Any] | None,
    release_inputs: dict[str, Any],
) -> dict[str, Any]:
    gate = fairness_gate if isinstance(fairness_gate, dict) else {}
    normalized = build_fairness_panel_evidence_normalization(
        fairness_gate=gate,
        release_inputs=release_inputs,
    )
    evidence_status = str(normalized.get("shadowEvidenceStatus") or "").strip().lower()
    if bool(gate.get("shadowGateApplied")):
        if evidence_status == "ready":
            return {
                "name": "panelShadowDrift",
                "status": "ready",
                "code": "registry_release_gate_panel_shadow_ready",
                "message": "panel shadow gate passed",
                "sourceStatus": str(gate.get("thresholdDecision") or "").strip() or None,
                "evidenceRef": None,
            }
        if evidence_status == "env_blocked":
            if _fairness_run_is_local_reference(gate.get("latestShadowRun")):
                latest_shadow_run = (
                    gate.get("latestShadowRun")
                    if isinstance(gate.get("latestShadowRun"), dict)
                    else {}
                )
                return {
                    "name": "panelShadowDrift",
                    "status": "env_blocked",
                    "code": "registry_release_gate_panel_shadow_local_reference_only",
                    "message": "panel shadow gate only has local reference evidence",
                    "sourceStatus": str(
                        latest_shadow_run.get("status")
                        or gate.get("thresholdDecision")
                        or ""
                    ).strip()
                    or None,
                    "evidenceRef": _artifact_ref_from_payload(latest_shadow_run),
                }
        return {
            "name": "panelShadowDrift",
            "status": "blocked" if evidence_status == "blocked" else "needs_review",
            "code": str(gate.get("code") or "").strip()
            or "registry_release_gate_panel_shadow_blocked",
            "message": str(gate.get("message") or "").strip()
            or "panel shadow drift gate did not pass",
            "sourceStatus": str(gate.get("thresholdDecision") or "").strip() or None,
            "evidenceRef": None,
        }

    raw = (
        release_inputs.get("panelShadowDrift")
        if release_inputs.get("panelShadowDrift") is not None
        else release_inputs.get("panel_shadow_drift")
    )
    return _coerce_release_component(
        name="panelShadowDrift",
        raw=raw,
        missing_code="registry_release_gate_panel_shadow_missing",
        ready_message="panel shadow drift readiness is marked ready",
    )


def _component_evidence(component: dict[str, Any]) -> dict[str, Any]:
    return {
        "component": _safe_token(component.get("name")),
        "status": _lower_token(component.get("status")) or "needs_review",
        "code": _safe_token(component.get("code")),
        "sourceStatus": _lower_token(component.get("sourceStatus")),
        "evidenceRef": _safe_token(component.get("evidenceRef")),
        "reasonCodes": _list_of_tokens(component.get("reasonCodes")),
    }


def _collect_artifact_refs(
    *,
    release_inputs: dict[str, Any],
    components: list[dict[str, Any]],
) -> list[str]:
    refs: list[str] = []
    for component in components:
        ref = _safe_token(component.get("evidenceRef"))
        if ref:
            refs.append(ref)
    raw_refs = (
        release_inputs.get("artifactRefs")
        if release_inputs.get("artifactRefs") is not None
        else release_inputs.get("artifact_refs")
    )
    if isinstance(raw_refs, list):
        for row in raw_refs:
            if isinstance(row, dict):
                ref = _artifact_ref_from_payload(row)
                if ref:
                    refs.append(ref)
            else:
                ref = _safe_token(row)
                if ref:
                    refs.append(ref)
    return list(dict.fromkeys(refs))


def _release_input_component(
    *,
    release_inputs: dict[str, Any],
    camel_key: str,
    snake_key: str,
) -> dict[str, Any]:
    raw = (
        release_inputs.get(camel_key)
        if release_inputs.get(camel_key) is not None
        else release_inputs.get(snake_key)
    )
    return raw if isinstance(raw, dict) else {}


def _list_of_tokens(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        token = str(item or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _to_int(value: Any, *, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return default
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _citation_verification_input(release_inputs: dict[str, Any]) -> dict[str, Any]:
    for key in (
        "citationVerification",
        "citation_verification",
        "citationVerifierEvidence",
        "citation_verifier_evidence",
        "evidenceCitationVerification",
        "evidence_citation_verification",
    ):
        value = release_inputs.get(key)
        if isinstance(value, dict):
            return dict(value)
    return {}


def _release_readiness_artifact_summary_input(
    release_inputs: dict[str, Any],
) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    for key in (
        "releaseReadinessArtifactSummary",
        "release_readiness_artifact_summary",
        "releaseReadinessArtifact",
        "release_readiness_artifact",
    ):
        value = release_inputs.get(key)
        if isinstance(value, dict):
            raw = dict(value)
            break
    if not raw:
        return {}
    return {
        "version": _safe_token(raw.get("version")),
        "artifactRef": _safe_token(raw.get("artifactRef") or raw.get("artifact_ref")),
        "manifestHash": _safe_token(raw.get("manifestHash") or raw.get("manifest_hash")),
        "evidenceVersion": _safe_token(raw.get("evidenceVersion")),
        "policyVersion": _safe_token(raw.get("policyVersion")),
        "decision": _safe_token(raw.get("decision")),
        "storageMode": _safe_token(raw.get("storageMode") or raw.get("storage_mode")),
    }


def _build_citation_verifier_release_component(
    *,
    release_inputs: dict[str, Any],
) -> dict[str, Any]:
    raw = _citation_verification_input(release_inputs)
    source_status = _lower_token(raw.get("status"))
    reason_codes = _list_of_tokens(raw.get("reasonCodes") or raw.get("reason_codes"))
    if source_status in {"passed", "ready", "ok"}:
        status = "ready"
        code = "registry_release_gate_citation_verifier_ready"
        message = "citation verifier passed"
    elif source_status == "blocked":
        status = "blocked"
        code = reason_codes[0] if reason_codes else "registry_release_gate_citation_verifier_blocked"
        message = "citation verifier blocked release readiness"
    elif source_status in {"env_blocked", "local_reference_ready", "local_reference_frozen"}:
        status = "env_blocked"
        code = reason_codes[0] if reason_codes else "registry_release_gate_citation_verifier_env_blocked"
        message = "citation verifier is blocked by missing real environment evidence"
    elif source_status == "warning":
        status = "needs_review"
        code = reason_codes[0] if reason_codes else "registry_release_gate_citation_verifier_warning"
        message = "citation verifier requires release review"
    else:
        status = "needs_review"
        code = "registry_release_gate_citation_verifier_missing"
        message = "citation verifier evidence is missing"

    return {
        "name": "citationVerifier",
        "status": status,
        "code": code,
        "message": message,
        "sourceStatus": source_status,
        "evidenceRef": _artifact_ref_from_payload(raw),
        "reasonCodes": reason_codes,
        "missingCitationCount": _to_int(raw.get("missingCitationCount")),
        "weakCitationCount": _to_int(raw.get("weakCitationCount")),
        "forbiddenSourceCount": _to_int(raw.get("forbiddenSourceCount")),
    }


def _build_public_verification_readiness_evidence(
    *,
    release_inputs: dict[str, Any],
    components: list[dict[str, Any]],
) -> dict[str, Any]:
    component = next(
        (
            row
            for row in components
            if str(row.get("name") or "").strip() == "publicVerificationReadiness"
        ),
        {},
    )
    raw = _release_input_component(
        release_inputs=release_inputs,
        camel_key="publicVerificationReadiness",
        snake_key="public_verification_readiness",
    )
    externalizable = raw.get("externalizable")
    return {
        "status": _lower_token(component.get("status")) or "needs_review",
        "code": _safe_token(component.get("code")),
        "sourceStatus": _lower_token(component.get("sourceStatus")),
        "evidenceRef": _safe_token(component.get("evidenceRef")),
        "externalizable": bool(externalizable) if externalizable is not None else None,
        "errorCode": _safe_token(raw.get("errorCode") or raw.get("error_code")),
    }


def _build_citation_verification_evidence(
    *,
    release_inputs: dict[str, Any],
    components: list[dict[str, Any]],
) -> dict[str, Any]:
    component = next(
        (
            row
            for row in components
            if str(row.get("name") or "").strip() == "citationVerifier"
        ),
        {},
    )
    raw = _citation_verification_input(release_inputs)
    return {
        "version": _safe_token(raw.get("version")) or CITATION_VERIFICATION_VERSION,
        "status": _lower_token(component.get("status")) or "needs_review",
        "sourceStatus": _lower_token(component.get("sourceStatus")),
        "code": _safe_token(component.get("code")),
        "reasonCodes": _list_of_tokens(
            component.get("reasonCodes")
            if component.get("reasonCodes") is not None
            else raw.get("reasonCodes")
        ),
        "citationCount": _to_int(raw.get("citationCount")),
        "messageRefCount": _to_int(raw.get("messageRefCount")),
        "sourceRefCount": _to_int(raw.get("sourceRefCount")),
        "missingCitationCount": _to_int(raw.get("missingCitationCount")),
        "weakCitationCount": _to_int(raw.get("weakCitationCount")),
        "forbiddenSourceCount": _to_int(raw.get("forbiddenSourceCount")),
    }


def _build_real_env_evidence_status(
    *,
    release_inputs: dict[str, Any],
    decision: str,
    env_blocked_components: list[str],
) -> dict[str, Any]:
    raw = _release_input_component(
        release_inputs=release_inputs,
        camel_key="realEnvEvidenceStatus",
        snake_key="real_env_evidence_status",
    )
    explicit_status = _lower_token(raw.get("status") or raw.get("decision"))
    if explicit_status in RELEASE_GATE_EVIDENCE_STATUSES:
        status = explicit_status
        source = "release_inputs"
    elif env_blocked_components:
        status = "env_blocked"
        source = "release_gate"
    elif decision == "allowed":
        status = "ready"
        source = "release_gate"
    else:
        status = decision
        source = "release_gate"

    available = raw.get("realEnvEvidenceAvailable")
    if available is None:
        available = raw.get("real_env_evidence_available")
    return {
        "status": status,
        "source": source,
        "code": _safe_token(raw.get("code")),
        "evidenceRef": _artifact_ref_from_payload(raw),
        "realEnvEvidenceAvailable": (
            bool(available) if available is not None else status == "ready"
        ),
    }


def _build_release_readiness_evidence(
    *,
    dependency_health: dict[str, Any] | None,
    release_inputs: dict[str, Any],
    fairness_gate: dict[str, Any] | None,
    components: list[dict[str, Any]],
    decision: str,
    decision_code: str,
    reasons: list[dict[str, Any]],
) -> dict[str, Any]:
    dependency_payload = dependency_health if isinstance(dependency_health, dict) else {}
    reason_codes = [
        code
        for code in (
            _safe_token(reason.get("code"))
            for reason in reasons
            if isinstance(reason, dict)
        )
        if code
    ]
    for component in components:
        reason_codes.extend(_list_of_tokens(component.get("reasonCodes")))
    env_blocked_components = [
        str(component.get("name") or "").strip()
        for component in components
        if str(component.get("status") or "").strip().lower() == "env_blocked"
        and str(component.get("name") or "").strip()
    ]
    generated_at = (
        _safe_token(release_inputs.get("generatedAt"))
        or _safe_token(release_inputs.get("generated_at"))
        or _safe_token(release_inputs.get("evidenceGeneratedAt"))
        or _safe_token(release_inputs.get("evidence_generated_at"))
    )
    return {
        "evidenceVersion": RELEASE_READINESS_EVIDENCE_VERSION,
        "generatedAt": generated_at,
        "policyVersion": _safe_token(dependency_payload.get("policyVersion")),
        "decision": decision,
        "decisionCode": decision_code,
        "componentStatuses": [_component_evidence(component) for component in components],
        "reasonCodes": list(dict.fromkeys(reason_codes)),
        "envBlockedComponents": list(dict.fromkeys(env_blocked_components)),
        "artifactRefs": _collect_artifact_refs(
            release_inputs=release_inputs,
            components=components,
        ),
        "releaseReadinessArtifactSummary": _release_readiness_artifact_summary_input(
            release_inputs
        ),
        "publicVerificationReadiness": _build_public_verification_readiness_evidence(
            release_inputs=release_inputs,
            components=components,
        ),
        "citationVerification": _build_citation_verification_evidence(
            release_inputs=release_inputs,
            components=components,
        ),
        "fairnessPanelEvidence": build_fairness_panel_evidence_normalization(
            fairness_gate=fairness_gate if isinstance(fairness_gate, dict) else {},
            release_inputs=release_inputs,
        ),
        "realEnvEvidenceStatus": _build_real_env_evidence_status(
            release_inputs=release_inputs,
            decision=decision,
            env_blocked_components=env_blocked_components,
        ),
    }


def build_policy_release_gate_decision(
    *,
    dependency_health: dict[str, Any] | None,
    fairness_gate: dict[str, Any] | None,
) -> dict[str, Any]:
    metadata = _extract_policy_metadata(dependency_health)
    release_inputs = _extract_release_readiness_section(metadata)
    dependency_ok = bool(
        dependency_health.get("ok") if isinstance(dependency_health, dict) else False
    )
    components = [
        {
            "name": "dependencyHealth",
            "status": "ready" if dependency_ok else "blocked",
            "code": (
                "registry_release_gate_dependency_ready"
                if dependency_ok
                else "registry_policy_dependency_blocked"
            ),
            "message": (
                "policy dependency health passed"
                if dependency_ok
                else "policy dependency health is blocked"
            ),
            "sourceStatus": (
                str(dependency_health.get("code") or "").strip()
                if isinstance(dependency_health, dict)
                else None
            ),
            "evidenceRef": None,
        },
        _build_fairness_benchmark_release_component(
            fairness_gate=fairness_gate,
            release_inputs=release_inputs,
        ),
        _build_panel_shadow_release_component(
            fairness_gate=fairness_gate,
            release_inputs=release_inputs,
        ),
        _coerce_release_component(
            name="artifactStoreReadiness",
            raw=(
                release_inputs.get("artifactStoreReadiness")
                if release_inputs.get("artifactStoreReadiness") is not None
                else release_inputs.get("artifact_store_readiness")
            ),
            missing_code="registry_release_gate_artifact_store_missing",
            ready_message="artifact store readiness is marked ready",
        ),
        _coerce_release_component(
            name="publicVerificationReadiness",
            raw=(
                release_inputs.get("publicVerificationReadiness")
                if release_inputs.get("publicVerificationReadiness") is not None
                else release_inputs.get("public_verification_readiness")
            ),
            missing_code="registry_release_gate_public_verification_missing",
            ready_message="public verification readiness is marked ready",
        ),
        _build_citation_verifier_release_component(
            release_inputs=release_inputs,
        ),
        _coerce_release_component(
            name="trustRegistryWriteThrough",
            raw=(
                release_inputs.get("trustRegistryWriteThrough")
                if release_inputs.get("trustRegistryWriteThrough") is not None
                else release_inputs.get("trust_registry_write_through")
            ),
            missing_code="registry_release_gate_trust_registry_missing",
            ready_message="trust registry write-through readiness is marked ready",
        ),
    ]

    status_counts = {
        "ready": 0,
        "blocked": 0,
        "env_blocked": 0,
        "needs_review": 0,
    }
    for component in components:
        status = str(component.get("status") or "").strip().lower()
        if status in status_counts:
            status_counts[status] += 1
        else:
            status_counts["needs_review"] += 1

    if status_counts["blocked"] > 0:
        decision = "blocked"
    elif status_counts["env_blocked"] > 0:
        decision = "env_blocked"
    elif status_counts["needs_review"] > 0:
        decision = "needs_review"
    else:
        decision = "allowed"

    reasons = [
        {
            "component": str(component.get("name") or "").strip(),
            "status": str(component.get("status") or "").strip(),
            "code": str(component.get("code") or "").strip(),
            "message": str(component.get("message") or "").strip(),
        }
        for component in components
        if str(component.get("status") or "").strip() != "ready"
    ]
    decision_code = f"registry_release_gate_{decision}"
    evidence = _build_release_readiness_evidence(
        dependency_health=dependency_health,
        release_inputs=release_inputs,
        fairness_gate=fairness_gate,
        components=components,
        decision=decision,
        decision_code=decision_code,
        reasons=reasons,
    )
    return {
        "version": "policy-release-gate-v1",
        "allowed": decision == "allowed",
        "decision": decision,
        "status": decision,
        "code": decision_code,
        "message": (
            "all release gate components passed"
            if decision == "allowed"
            else f"release gate {decision}"
        ),
        "components": components,
        "statusCounts": status_counts,
        "reasons": reasons,
        "releaseReadinessEvidence": evidence,
        "metadataInputPresent": bool(release_inputs),
    }
