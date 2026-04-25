from __future__ import annotations

from typing import Any

FAIRNESS_PANEL_EVIDENCE_VERSION = "fairness-panel-evidence-normalized-v1"

_READY_STATUSES = {"ready", "pass", "passed", "accepted", "completed", "success", "ok"}
_LOCAL_REFERENCE_STATUSES = {"local_reference_ready", "local_reference_frozen"}
_LOCAL_REFERENCE_ENVIRONMENTS = {"local", "local_reference", "local-reference"}
_REAL_ENVIRONMENTS = {"real", "prod", "production", "staging"}
_BLOCKED_STATUSES = {
    "blocked",
    "failed",
    "fail",
    "error",
    "threshold_violation",
    "violation",
    "not_ready",
}


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_of_tokens(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _token(value: Any) -> str | None:
    token = str(value or "").strip()
    return token or None


def _lower_token(value: Any) -> str | None:
    token = _token(value)
    return token.lower() if token is not None else None


def _canonical_environment(value: Any) -> str | None:
    token = _lower_token(value)
    if token in _LOCAL_REFERENCE_ENVIRONMENTS:
        return "local_reference"
    return token


def _to_int(value: Any, *, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return default
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _explicit_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _release_input_component_status(
    *,
    release_inputs: dict[str, Any],
    camel_key: str,
    snake_key: str,
) -> str | None:
    raw = (
        release_inputs.get(camel_key)
        if release_inputs.get(camel_key) is not None
        else release_inputs.get(snake_key)
    )
    payload = _dict_or_empty(raw)
    return _lower_token(payload.get("status") or payload.get("decision"))


def _is_local_reference_run(run: dict[str, Any]) -> bool:
    return (_lower_token(run.get("status")) or "") in _LOCAL_REFERENCE_STATUSES or (
        _canonical_environment(run.get("environmentMode") or run.get("environment_mode")) or ""
    ) in {"local_reference"}


def _is_real_environment(value: Any) -> bool:
    return (_canonical_environment(value) or "") in _REAL_ENVIRONMENTS


def _run_needs_remediation(run: dict[str, Any]) -> bool | None:
    value = run.get("needsRemediation")
    if value is None:
        value = run.get("needs_remediation")
    return bool(value) if value is not None else None


def _benchmark_status(
    *,
    gate: dict[str, Any],
    latest_run: dict[str, Any],
) -> str:
    if not latest_run:
        return "pending_real_samples"
    if _is_local_reference_run(latest_run):
        return "env_blocked"

    threshold_decision = _lower_token(
        latest_run.get("thresholdDecision")
        or latest_run.get("threshold_decision")
        or gate.get("thresholdDecision")
    )
    run_status = _lower_token(latest_run.get("status"))
    needs_remediation = _run_needs_remediation(latest_run)
    benchmark_gate_passed = bool(gate.get("benchmarkGatePassed"))

    if (
        benchmark_gate_passed
        and threshold_decision == "accepted"
        and needs_remediation is not True
        and (run_status in _READY_STATUSES or run_status is None)
    ):
        return "ready"
    if (
        threshold_decision in {"violated", "blocked", "fail", "failed"}
        or needs_remediation is True
        or run_status in _BLOCKED_STATUSES
    ):
        return "blocked"
    return "pending"


def _real_sample_manifest_status(latest_run: dict[str, Any]) -> str:
    if not latest_run:
        return "pending_real_samples"
    if _is_real_environment(latest_run.get("environmentMode") or latest_run.get("environment_mode")):
        return "ready"
    if _is_local_reference_run(latest_run):
        return "env_blocked"
    return "pending_real_samples"


def _shadow_status(
    *,
    gate: dict[str, Any],
    latest_shadow_run: dict[str, Any],
    drift_breach_count: int,
) -> str:
    if not bool(gate.get("shadowGateApplied")):
        return "missing"
    if not latest_shadow_run:
        return "missing"
    if _is_local_reference_run(latest_shadow_run):
        return "env_blocked"
    shadow_gate_passed = _explicit_bool(gate.get("shadowGatePassed"))
    threshold_decision = _lower_token(
        latest_shadow_run.get("thresholdDecision")
        or latest_shadow_run.get("threshold_decision")
        or gate.get("thresholdDecision")
    )
    run_status = _lower_token(latest_shadow_run.get("status"))
    needs_remediation = _run_needs_remediation(latest_shadow_run)
    if shadow_gate_passed is True and threshold_decision == "accepted" and needs_remediation is not True:
        return "ready"
    if (
        shadow_gate_passed is False
        or threshold_decision in {"violated", "blocked", "fail", "failed"}
        or needs_remediation is True
        or run_status in _BLOCKED_STATUSES
    ):
        return "blocked"
    if drift_breach_count > 0:
        return "watch"
    return "pending"


def _release_gate_input_status(
    *,
    benchmark_status: str,
    real_sample_status: str,
    shadow_status: str,
    release_inputs: dict[str, Any],
) -> str:
    explicit_real_env = _release_input_component_status(
        release_inputs=release_inputs,
        camel_key="realEnvEvidenceStatus",
        snake_key="real_env_evidence_status",
    )
    explicit_shadow = _release_input_component_status(
        release_inputs=release_inputs,
        camel_key="panelShadowDrift",
        snake_key="panel_shadow_drift",
    )
    explicit = explicit_real_env or explicit_shadow
    if benchmark_status == "blocked" or shadow_status == "blocked":
        return "blocked"
    if benchmark_status == "env_blocked" or real_sample_status in {
        "env_blocked",
        "pending_real_samples",
    } or shadow_status == "env_blocked":
        return "env_blocked"
    if explicit in {"ready", "env_blocked", "blocked", "needs_review", "pending", "missing"}:
        return explicit
    if shadow_status in {"missing", "watch", "pending"}:
        return "needs_review"
    if benchmark_status == "ready" and real_sample_status == "ready" and shadow_status == "ready":
        return "ready"
    return "pending"


def build_fairness_panel_evidence_normalization(
    *,
    fairness_gate: dict[str, Any] | None = None,
    release_inputs: dict[str, Any] | None = None,
    fairness_calibration_advisor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    advisor = _dict_or_empty(fairness_calibration_advisor)
    gate = _dict_or_empty(fairness_gate) or _dict_or_empty(advisor.get("releaseGate"))
    inputs = _dict_or_empty(release_inputs)
    overview = _dict_or_empty(advisor.get("overview"))
    drift_summary = _dict_or_empty(advisor.get("driftSummary"))
    latest_run = _dict_or_empty(gate.get("latestRun"))
    latest_shadow_run = _dict_or_empty(gate.get("latestShadowRun"))
    drift_payload = _dict_or_empty(drift_summary.get("benchmark"))
    shadow_payload = _dict_or_empty(drift_summary.get("shadow"))
    drift_breach_count = max(
        _to_int(overview.get("driftBreachCount")),
        len(_list_of_tokens(drift_payload.get("driftBreaches"))),
        _to_int(overview.get("shadowThresholdViolationCount")),
        len(_list_of_tokens(shadow_payload.get("breaches"))),
    )

    benchmark_status = _benchmark_status(gate=gate, latest_run=latest_run)
    real_sample_status = _real_sample_manifest_status(latest_run)
    shadow_status = _shadow_status(
        gate=gate,
        latest_shadow_run=latest_shadow_run,
        drift_breach_count=drift_breach_count,
    )
    return {
        "evidenceVersion": FAIRNESS_PANEL_EVIDENCE_VERSION,
        "benchmarkEvidenceStatus": benchmark_status,
        "realSampleManifestStatus": real_sample_status,
        "shadowEvidenceStatus": shadow_status,
        "thresholdDecision": _lower_token(
            gate.get("thresholdDecision")
            or latest_run.get("thresholdDecision")
            or latest_run.get("threshold_decision")
        ),
        "shadowGateApplied": bool(gate.get("shadowGateApplied")),
        "shadowGatePassed": _explicit_bool(gate.get("shadowGatePassed")),
        "driftBreachCount": drift_breach_count,
        "latestRunEnvironmentMode": _canonical_environment(
            latest_run.get("environmentMode") or latest_run.get("environment_mode")
        ),
        "latestRunStatus": _lower_token(latest_run.get("status")),
        "latestRunId": _token(latest_run.get("runId") or latest_run.get("run_id")),
        "latestShadowRunEnvironmentMode": _canonical_environment(
            latest_shadow_run.get("environmentMode")
            or latest_shadow_run.get("environment_mode")
        ),
        "latestShadowRunStatus": _lower_token(latest_shadow_run.get("status")),
        "latestShadowRunId": _token(
            latest_shadow_run.get("runId") or latest_shadow_run.get("run_id")
        ),
        "releaseGateInputStatus": _release_gate_input_status(
            benchmark_status=benchmark_status,
            real_sample_status=real_sample_status,
            shadow_status=shadow_status,
            release_inputs=inputs,
        ),
        "advisoryOnly": True,
        "officialWinnerMutationAllowed": False,
    }
