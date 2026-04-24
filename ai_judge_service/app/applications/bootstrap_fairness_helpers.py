from __future__ import annotations

from typing import Any, Callable

from .fairness_runtime_routes import (
    build_case_fairness_aggregations as build_case_fairness_aggregations_v3,
)
from .fairness_runtime_routes import (
    build_case_fairness_item as build_case_fairness_item_v3,
)


def build_case_fairness_item_for_runtime(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str,
    workflow_job: Any | None,
    workflow_events: list[Any],
    report_payload: dict[str, Any] | None,
    latest_run: Any | None,
    latest_shadow_run: Any | None,
    normalize_fairness_gate_decision: Callable[..., str],
    serialize_fairness_benchmark_run: Callable[[Any], dict[str, Any]],
    serialize_fairness_shadow_run: Callable[[Any], dict[str, Any]],
    trust_challenge_event_type: str,
) -> dict[str, Any]:
    return build_case_fairness_item_v3(
        case_id=case_id,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        workflow_job=workflow_job,
        workflow_events=workflow_events,
        report_payload=report_payload,
        latest_run=latest_run,
        latest_shadow_run=latest_shadow_run,
        normalize_fairness_gate_decision=normalize_fairness_gate_decision,
        serialize_fairness_benchmark_run=serialize_fairness_benchmark_run,
        serialize_fairness_shadow_run=serialize_fairness_shadow_run,
        trust_challenge_event_type=trust_challenge_event_type,
    )


def build_case_fairness_aggregations_for_runtime(
    items: list[dict[str, Any]],
    *,
    case_fairness_gate_conclusions: set[str] | frozenset[str],
) -> dict[str, Any]:
    return build_case_fairness_aggregations_v3(
        items,
        case_fairness_gate_conclusions=case_fairness_gate_conclusions,
    )
