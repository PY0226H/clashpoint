from __future__ import annotations

from typing import Any

RELEASE_GATE_READY_STATUSES = {
    "ready",
    "readiness_ready",
    "local_reference_ready",
    "pass",
    "passed",
    "accepted",
    "ok",
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
    "pending_real_env",
    "pending_real_samples",
    "missing_real_env",
    "missing_real_samples",
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
        "evidenceRef": (
            str(payload.get("evidenceRef") or payload.get("evidence_ref") or "").strip()
            or None
        ),
    }


def _build_fairness_benchmark_release_component(
    fairness_gate: dict[str, Any] | None,
) -> dict[str, Any]:
    gate = fairness_gate if isinstance(fairness_gate, dict) else {}
    if bool(gate.get("benchmarkGatePassed")):
        return {
            "name": "fairnessBenchmark",
            "status": "ready",
            "code": "registry_release_gate_fairness_benchmark_ready",
            "message": "fairness benchmark gate passed",
            "sourceStatus": str(gate.get("thresholdDecision") or "").strip() or None,
            "evidenceRef": None,
        }
    code = (
        str(gate.get("code") or "").strip()
        or "registry_release_gate_fairness_benchmark_missing"
    )
    status = "env_blocked" if code == "registry_fairness_gate_no_benchmark" else "blocked"
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
    if bool(gate.get("shadowGateApplied")):
        if bool(gate.get("shadowGatePassed")):
            return {
                "name": "panelShadowDrift",
                "status": "ready",
                "code": "registry_release_gate_panel_shadow_ready",
                "message": "panel shadow gate passed",
                "sourceStatus": str(gate.get("thresholdDecision") or "").strip() or None,
                "evidenceRef": None,
            }
        return {
            "name": "panelShadowDrift",
            "status": "blocked",
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
        _build_fairness_benchmark_release_component(fairness_gate),
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
    return {
        "version": "policy-release-gate-v1",
        "allowed": decision == "allowed",
        "decision": decision,
        "status": decision,
        "code": f"registry_release_gate_{decision}",
        "message": (
            "all release gate components passed"
            if decision == "allowed"
            else f"release gate {decision}"
        ),
        "components": components,
        "statusCounts": status_counts,
        "reasons": reasons,
        "metadataInputPresent": bool(release_inputs),
    }
