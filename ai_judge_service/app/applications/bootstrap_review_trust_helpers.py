from __future__ import annotations

from datetime import datetime
from typing import Any, Callable
from uuid import uuid4

from .review_alert_routes import (
    build_review_case_risk_profile as build_review_case_risk_profile_v3,
)
from .trust_ops_views import (
    build_review_trust_unified_priority_profile as build_review_trust_unified_priority_profile_v3,
)
from .trust_ops_views import (
    build_trust_challenge_action_hints as build_trust_challenge_action_hints_v3,
)
from .trust_ops_views import (
    build_trust_challenge_priority_profile as build_trust_challenge_priority_profile_v3,
)


def build_review_case_risk_profile_for_runtime(
    *,
    workflow: Any,
    report_payload: dict[str, Any] | None,
    report_summary: dict[str, Any] | None,
    now: datetime | str | None,
    normalize_query_datetime: Callable[[datetime | None], datetime | None],
) -> dict[str, Any]:
    return build_review_case_risk_profile_v3(
        workflow=workflow,
        report_payload=report_payload,
        report_summary=report_summary,
        now=now,
        normalize_query_datetime=normalize_query_datetime,
    )


def build_trust_challenge_priority_profile_for_runtime(
    *,
    workflow: Any,
    challenge_review: dict[str, Any] | None,
    report_payload: dict[str, Any] | None,
    report_summary: dict[str, Any] | None,
    now: datetime | str | None,
    normalize_query_datetime: Callable[[datetime | None], datetime | None],
    trust_challenge_open_states: set[str] | frozenset[str],
) -> dict[str, Any]:
    return build_trust_challenge_priority_profile_v3(
        workflow=workflow,
        challenge_review=challenge_review,
        report_payload=report_payload,
        report_summary=report_summary,
        now=now,
        normalize_query_datetime=normalize_query_datetime,
        trust_challenge_open_states=trust_challenge_open_states,
    )


def build_trust_challenge_action_hints_for_runtime(
    *,
    challenge_review: dict[str, Any] | None,
    priority_profile: dict[str, Any] | None,
    trust_challenge_open_states: set[str] | frozenset[str],
) -> list[str]:
    return build_trust_challenge_action_hints_v3(
        challenge_review=challenge_review,
        priority_profile=priority_profile,
        trust_challenge_open_states=trust_challenge_open_states,
    )


def build_review_trust_unified_priority_profile_for_runtime(
    *,
    risk_profile: dict[str, Any] | None,
    trust_priority_profile: dict[str, Any] | None,
    challenge_review: dict[str, Any] | None,
    trust_challenge_open_states: set[str] | frozenset[str],
) -> dict[str, Any]:
    return build_review_trust_unified_priority_profile_v3(
        risk_profile=risk_profile,
        trust_priority_profile=trust_priority_profile,
        challenge_review=challenge_review,
        trust_challenge_open_states=trust_challenge_open_states,
    )


def build_trust_challenge_id_for_runtime(*, case_id: int) -> str:
    return f"chlg-{max(0, int(case_id))}-{uuid4().hex[:12]}"
