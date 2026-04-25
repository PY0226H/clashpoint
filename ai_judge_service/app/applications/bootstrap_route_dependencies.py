from __future__ import annotations

from typing import Any, Awaitable, Callable


def build_registry_release_gate_dependencies(
    *,
    policy_registry_type: str,
    evaluate_policy_registry_dependency_health: Callable[..., Awaitable[dict[str, Any]]],
    emit_registry_dependency_health_alert: Callable[..., Awaitable[dict[str, Any]]],
    resolve_registry_dependency_health_alerts: Callable[..., Awaitable[list[dict[str, Any]]]],
    evaluate_policy_release_fairness_gate: Callable[..., Awaitable[dict[str, Any]]],
    emit_registry_fairness_gate_alert: Callable[..., Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    return {
        "policy_registry_type": policy_registry_type,
        "evaluate_policy_registry_dependency_health": (
            evaluate_policy_registry_dependency_health
        ),
        "emit_registry_dependency_health_alert": emit_registry_dependency_health_alert,
        "resolve_registry_dependency_health_alerts": (
            resolve_registry_dependency_health_alerts
        ),
        "evaluate_policy_release_fairness_gate": evaluate_policy_release_fairness_gate,
        "emit_registry_fairness_gate_alert": emit_registry_fairness_gate_alert,
    }


def build_trust_challenge_common_dependencies(
    *,
    resolve_report_context_for_case: Callable[..., Awaitable[dict[str, Any]]],
    workflow_get_job: Callable[..., Awaitable[Any | None]],
    workflow_append_event: Callable[..., Awaitable[dict[str, Any]]],
    workflow_mark_review_required: Callable[..., Awaitable[None]],
    build_trust_phasea_bundle: Callable[..., Awaitable[dict[str, Any]]],
    serialize_workflow_job: Callable[[Any], dict[str, Any]],
    append_trust_challenge_event: Callable[..., Awaitable[Any | None]] | None,
    trust_challenge_event_type: str,
    trust_challenge_state_accepted: str,
    trust_challenge_state_under_review: str,
) -> dict[str, Any]:
    return {
        "resolve_report_context_for_case": resolve_report_context_for_case,
        "workflow_get_job": workflow_get_job,
        "workflow_append_event": workflow_append_event,
        "workflow_mark_review_required": workflow_mark_review_required,
        "build_trust_phasea_bundle": build_trust_phasea_bundle,
        "serialize_workflow_job": serialize_workflow_job,
        "append_trust_challenge_event": append_trust_challenge_event,
        "trust_challenge_event_type": trust_challenge_event_type,
        "trust_challenge_state_accepted": trust_challenge_state_accepted,
        "trust_challenge_state_under_review": trust_challenge_state_under_review,
    }
