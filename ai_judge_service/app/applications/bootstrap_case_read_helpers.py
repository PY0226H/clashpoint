from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from .case_courtroom_views import (
    build_courtroom_drilldown_bundle_view as build_courtroom_drilldown_bundle_view_v3,
)
from .case_courtroom_views import (
    build_courtroom_read_model_light_summary as build_courtroom_read_model_light_summary_v3,
)
from .case_courtroom_views import (
    build_courtroom_read_model_view as build_courtroom_read_model_view_v3,
)
from .judge_command_routes import (
    extract_optional_datetime as extract_optional_datetime_v3,
)


def build_courtroom_read_model_view_for_runtime(
    *,
    report_payload: dict[str, Any],
    case_evidence: dict[str, Any],
    normalize_fairness_gate_decision: Callable[..., str],
) -> dict[str, Any]:
    return build_courtroom_read_model_view_v3(
        report_payload=report_payload,
        case_evidence=case_evidence,
        normalize_fairness_gate_decision=normalize_fairness_gate_decision,
    )


def build_courtroom_read_model_light_summary_for_runtime(
    *,
    courtroom_view: dict[str, Any],
    normalize_fairness_gate_decision: Callable[..., str],
) -> dict[str, Any]:
    return build_courtroom_read_model_light_summary_v3(
        courtroom_view=courtroom_view,
        normalize_fairness_gate_decision=normalize_fairness_gate_decision,
    )


def build_courtroom_drilldown_bundle_view_for_runtime(
    *,
    courtroom_view: dict[str, Any],
    claim_preview_limit: int,
    evidence_preview_limit: int,
    panel_preview_limit: int,
    normalize_fairness_gate_decision: Callable[..., str],
) -> dict[str, Any]:
    return build_courtroom_drilldown_bundle_view_v3(
        courtroom_view=courtroom_view,
        claim_preview_limit=claim_preview_limit,
        evidence_preview_limit=evidence_preview_limit,
        panel_preview_limit=panel_preview_limit,
        normalize_fairness_gate_decision=normalize_fairness_gate_decision,
    )


def extract_optional_datetime_for_runtime(
    payload: dict[str, Any],
    *keys: str,
    normalize_query_datetime: Callable[[datetime | None], datetime | None],
) -> datetime | None:
    return extract_optional_datetime_v3(
        payload,
        *keys,
        normalize_query_datetime=normalize_query_datetime,
    )
