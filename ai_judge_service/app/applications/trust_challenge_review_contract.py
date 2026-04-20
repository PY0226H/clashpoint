from __future__ import annotations

from typing import Any

TRUST_CHALLENGE_REVIEW_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "caseId",
    "dispatchType",
    "traceId",
    "item",
)

TRUST_CHALLENGE_REVIEW_ITEM_KEYS: tuple[str, ...] = (
    "version",
    "caseId",
    "traceId",
    "challengeState",
    "activeChallengeId",
    "totalChallenges",
    "challenges",
    "timeline",
    "reviewState",
    "reviewRequired",
    "reviewDecisions",
    "challengeReasons",
    "alertSummary",
    "openAlertIds",
    "registryHash",
)

TRUST_CHALLENGE_REVIEW_ALERT_SUMMARY_KEYS: tuple[str, ...] = (
    "total",
    "raised",
    "acked",
    "resolved",
    "critical",
    "warning",
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


def validate_trust_challenge_review_contract(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("trust_challenge_review_payload_not_dict")
    _assert_required_keys(
        section="trust_challenge_review",
        payload=payload,
        keys=TRUST_CHALLENGE_REVIEW_TOP_LEVEL_KEYS,
    )
    case_id = _non_negative_int(payload.get("caseId"), default=0)
    if case_id <= 0:
        raise ValueError("trust_challenge_review_case_id_invalid")
    dispatch_type = str(payload.get("dispatchType") or "").strip().lower()
    if dispatch_type not in {"phase", "final"}:
        raise ValueError("trust_challenge_review_dispatch_type_invalid")
    _assert_non_empty_string("trust_challenge_review_trace_id", payload.get("traceId"))

    item = payload.get("item")
    if not isinstance(item, dict):
        raise ValueError("trust_challenge_review_item_not_dict")
    _assert_required_keys(
        section="trust_challenge_review_item",
        payload=item,
        keys=TRUST_CHALLENGE_REVIEW_ITEM_KEYS,
    )
    if _non_negative_int(item.get("caseId"), default=0) != case_id:
        raise ValueError("trust_challenge_review_item_case_id_mismatch")
    if str(item.get("traceId") or "").strip() != str(payload.get("traceId") or "").strip():
        raise ValueError("trust_challenge_review_item_trace_id_mismatch")
    _assert_non_empty_string("trust_challenge_review_item_version", item.get("version"))
    _assert_non_empty_string(
        "trust_challenge_review_item_registry_hash",
        item.get("registryHash"),
    )

    _assert_non_empty_string(
        "trust_challenge_review_item_challenge_state",
        item.get("challengeState"),
    )
    review_state = str(item.get("reviewState") or "").strip().lower()
    if review_state not in {"not_required", "pending_review", "approved", "rejected"}:
        raise ValueError("trust_challenge_review_item_review_state_invalid")
    if not isinstance(item.get("reviewRequired"), bool):
        raise ValueError("trust_challenge_review_item_review_required_not_bool")

    challenges = item.get("challenges")
    if not isinstance(challenges, list):
        raise ValueError("trust_challenge_review_item_challenges_not_list")
    timeline = item.get("timeline")
    if not isinstance(timeline, list):
        raise ValueError("trust_challenge_review_item_timeline_not_list")
    review_decisions = item.get("reviewDecisions")
    if not isinstance(review_decisions, list):
        raise ValueError("trust_challenge_review_item_review_decisions_not_list")
    challenge_reasons = item.get("challengeReasons")
    if not isinstance(challenge_reasons, list):
        raise ValueError("trust_challenge_review_item_challenge_reasons_not_list")
    open_alert_ids = item.get("openAlertIds")
    if not isinstance(open_alert_ids, list):
        raise ValueError("trust_challenge_review_item_open_alert_ids_not_list")

    total_challenges = _non_negative_int(item.get("totalChallenges"), default=-1)
    if total_challenges < 0:
        raise ValueError("trust_challenge_review_item_total_challenges_invalid")
    if total_challenges != len(challenges):
        raise ValueError("trust_challenge_review_item_total_challenges_mismatch")

    alert_summary = item.get("alertSummary")
    if not isinstance(alert_summary, dict):
        raise ValueError("trust_challenge_review_item_alert_summary_not_dict")
    _assert_required_keys(
        section="trust_challenge_review_item_alert_summary",
        payload=alert_summary,
        keys=TRUST_CHALLENGE_REVIEW_ALERT_SUMMARY_KEYS,
    )
    for key in TRUST_CHALLENGE_REVIEW_ALERT_SUMMARY_KEYS:
        if _non_negative_int(alert_summary.get(key), default=-1) < 0:
            raise ValueError(f"trust_challenge_review_item_alert_summary_{key}_invalid")
