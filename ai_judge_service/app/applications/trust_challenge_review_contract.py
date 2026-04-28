from __future__ import annotations

from typing import Any

TRUST_CHALLENGE_REVIEW_DECISION_SYNC_VERSION = (
    "trust-challenge-review-decision-sync-v1"
)

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
    "reviewDecisionSync",
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

TRUST_CHALLENGE_REVIEW_CHALLENGE_STATES: frozenset[str] = frozenset(
    {
        "not_challenged",
        "challenge_requested",
        "challenge_accepted",
        "under_internal_review",
        "verdict_upheld",
        "verdict_overturned",
        "draw_after_review",
        "review_retained",
        "challenge_closed",
    }
)

TRUST_CHALLENGE_REVIEW_OPEN_STATES: frozenset[str] = frozenset(
    {
        "challenge_requested",
        "challenge_accepted",
        "under_internal_review",
    }
)

TRUST_CHALLENGE_REVIEW_DECISION_SYNC_KEYS: tuple[str, ...] = (
    "version",
    "syncState",
    "result",
    "userVisibleStatus",
    "source",
    "verdictEffect",
    "nextStep",
)

TRUST_CHALLENGE_REVIEW_DECISION_SYNC_SOURCE_KEYS: tuple[str, ...] = (
    "originalCaseId",
    "originalVerdictVersion",
    "challengeId",
    "reviewDecisionId",
    "reviewDecisionEventSeq",
    "reviewDecidedAt",
    "decisionSource",
)

TRUST_CHALLENGE_REVIEW_DECISION_SYNC_EFFECT_KEYS: tuple[str, ...] = (
    "ledgerAction",
    "directWinnerWriteAllowed",
    "requiresVerdictLedgerSource",
    "drawVoteRequired",
    "reviewRequired",
)

TRUST_CHALLENGE_REVIEW_DECISION_RESULTS: frozenset[str] = frozenset(
    {
        "none",
        "verdict_upheld",
        "verdict_overturned",
        "draw_after_review",
        "review_retained",
    }
)

TRUST_CHALLENGE_REVIEW_SYNC_STATES: frozenset[str] = frozenset(
    {
        "not_available",
        "pending_review",
        "completed",
        "awaiting_verdict_source",
        "draw_pending_vote",
        "review_retained",
    }
)

TRUST_CHALLENGE_REVIEW_USER_VISIBLE_STATUSES: frozenset[str] = frozenset(
    {
        "not_available",
        "review_required",
        "completed",
        "draw_pending_vote",
    }
)

TRUST_CHALLENGE_REVIEW_LEDGER_ACTIONS: frozenset[str] = frozenset(
    {
        "none",
        "retain_original_verdict",
        "await_revised_verdict_ledger",
        "open_draw_vote",
        "retain_review_required",
    }
)


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _token(value: Any) -> str | None:
    token = str(value or "").strip()
    return token or None


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


def _extract_original_verdict_version(report_payload: dict[str, Any] | None) -> str:
    report = _dict_or_empty(report_payload)
    verdict_ledger = _dict_or_empty(
        report.get("verdictLedger") or report.get("verdict_ledger")
    )
    return (
        _token(verdict_ledger.get("version"))
        or _token(verdict_ledger.get("chainVersion"))
        or "unknown"
    )


def build_trust_challenge_review_decision_sync(
    *,
    case_id: int,
    challenge_state: str | None,
    review_state: str | None,
    workflow_status: str | None,
    latest_challenge: dict[str, Any] | None,
    report_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    challenge = _dict_or_empty(latest_challenge)
    result = str(challenge.get("decision") or "").strip().lower() or "none"
    if result not in TRUST_CHALLENGE_REVIEW_DECISION_RESULTS:
        result = "none"
    normalized_workflow_status = str(workflow_status or "").strip().lower()
    normalized_challenge_state = str(challenge_state or "").strip().lower()
    normalized_review_state = str(review_state or "").strip().lower()

    challenge_id = _token(challenge.get("challengeId"))
    event_seq = _non_negative_int(
        challenge.get("decisionEventSeq") or challenge.get("latestEventSeq"),
        default=0,
    )
    decided_at = _token(challenge.get("decisionAt"))
    if result == "none":
        review_decision_id = None
        review_decision_event_seq: int | None = None
        decision_source = "none"
    else:
        review_decision_event_seq = event_seq if event_seq > 0 else None
        review_decision_id = (
            f"review-decision:{int(case_id)}:{challenge_id}:{review_decision_event_seq}"
            if challenge_id and review_decision_event_seq is not None
            else None
        )
        decision_source = "trust_challenge_timeline"

    if result == "verdict_upheld":
        sync_state = "completed"
        user_visible_status = "completed"
        ledger_action = "retain_original_verdict"
        requires_verdict_ledger_source = False
        draw_vote_required = False
        review_required = False
        next_step = "show_original_verdict_with_review_upheld"
    elif result == "verdict_overturned":
        sync_state = "awaiting_verdict_source"
        user_visible_status = "review_required"
        ledger_action = "await_revised_verdict_ledger"
        requires_verdict_ledger_source = True
        draw_vote_required = False
        review_required = True
        next_step = "await_revised_verdict_artifact"
    elif result == "draw_after_review":
        sync_state = "draw_pending_vote"
        user_visible_status = "draw_pending_vote"
        ledger_action = "open_draw_vote"
        requires_verdict_ledger_source = False
        draw_vote_required = True
        review_required = False
        next_step = "open_or_continue_draw_vote"
    elif result == "review_retained":
        sync_state = "review_retained"
        user_visible_status = "review_required"
        ledger_action = "retain_review_required"
        requires_verdict_ledger_source = False
        draw_vote_required = False
        review_required = True
        next_step = "continue_internal_review"
    elif (
        normalized_workflow_status == "review_required"
        or normalized_review_state == "pending_review"
        or normalized_challenge_state in TRUST_CHALLENGE_REVIEW_OPEN_STATES
    ):
        sync_state = "pending_review"
        user_visible_status = "review_required"
        ledger_action = "none"
        requires_verdict_ledger_source = False
        draw_vote_required = False
        review_required = True
        next_step = "await_review_decision"
    else:
        sync_state = "not_available"
        user_visible_status = "not_available"
        ledger_action = "none"
        requires_verdict_ledger_source = False
        draw_vote_required = False
        review_required = False
        next_step = "none"

    payload = {
        "version": TRUST_CHALLENGE_REVIEW_DECISION_SYNC_VERSION,
        "syncState": sync_state,
        "result": result,
        "userVisibleStatus": user_visible_status,
        "source": {
            "originalCaseId": int(case_id),
            "originalVerdictVersion": _extract_original_verdict_version(report_payload),
            "challengeId": challenge_id,
            "reviewDecisionId": review_decision_id,
            "reviewDecisionEventSeq": review_decision_event_seq,
            "reviewDecidedAt": decided_at,
            "decisionSource": decision_source,
        },
        "verdictEffect": {
            "ledgerAction": ledger_action,
            "directWinnerWriteAllowed": False,
            "requiresVerdictLedgerSource": requires_verdict_ledger_source,
            "drawVoteRequired": draw_vote_required,
            "reviewRequired": review_required,
        },
        "nextStep": next_step,
    }
    validate_trust_challenge_review_decision_sync_contract(payload)
    return payload


def validate_trust_challenge_review_decision_sync_contract(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("trust_challenge_review_decision_sync_not_dict")
    _assert_required_keys(
        section="trust_challenge_review_decision_sync",
        payload=payload,
        keys=TRUST_CHALLENGE_REVIEW_DECISION_SYNC_KEYS,
    )
    if payload.get("version") != TRUST_CHALLENGE_REVIEW_DECISION_SYNC_VERSION:
        raise ValueError("trust_challenge_review_decision_sync_version_invalid")
    result = str(payload.get("result") or "").strip().lower()
    if result not in TRUST_CHALLENGE_REVIEW_DECISION_RESULTS:
        raise ValueError("trust_challenge_review_decision_sync_result_invalid")
    sync_state = str(payload.get("syncState") or "").strip().lower()
    if sync_state not in TRUST_CHALLENGE_REVIEW_SYNC_STATES:
        raise ValueError("trust_challenge_review_decision_sync_state_invalid")
    user_visible_status = str(payload.get("userVisibleStatus") or "").strip().lower()
    if user_visible_status not in TRUST_CHALLENGE_REVIEW_USER_VISIBLE_STATUSES:
        raise ValueError("trust_challenge_review_decision_sync_visible_status_invalid")

    source = payload.get("source")
    if not isinstance(source, dict):
        raise ValueError("trust_challenge_review_decision_sync_source_not_dict")
    _assert_required_keys(
        section="trust_challenge_review_decision_sync_source",
        payload=source,
        keys=TRUST_CHALLENGE_REVIEW_DECISION_SYNC_SOURCE_KEYS,
    )
    if _non_negative_int(source.get("originalCaseId"), default=0) <= 0:
        raise ValueError("trust_challenge_review_decision_sync_source_case_id_invalid")
    _assert_non_empty_string(
        "trust_challenge_review_decision_sync_source_original_verdict_version",
        source.get("originalVerdictVersion"),
    )
    decision_source = str(source.get("decisionSource") or "").strip().lower()
    if decision_source not in {"none", "trust_challenge_timeline"}:
        raise ValueError("trust_challenge_review_decision_sync_source_invalid")
    if result == "none":
        if source.get("reviewDecisionId") is not None:
            raise ValueError(
                "trust_challenge_review_decision_sync_source_decision_id_unexpected"
            )
    else:
        _assert_non_empty_string(
            "trust_challenge_review_decision_sync_source_challenge_id",
            source.get("challengeId"),
        )
        _assert_non_empty_string(
            "trust_challenge_review_decision_sync_source_decision_id",
            source.get("reviewDecisionId"),
        )
        if _non_negative_int(source.get("reviewDecisionEventSeq"), default=0) <= 0:
            raise ValueError(
                "trust_challenge_review_decision_sync_source_event_seq_invalid"
            )
        _assert_non_empty_string(
            "trust_challenge_review_decision_sync_source_decided_at",
            source.get("reviewDecidedAt"),
        )

    effect = payload.get("verdictEffect")
    if not isinstance(effect, dict):
        raise ValueError("trust_challenge_review_decision_sync_effect_not_dict")
    _assert_required_keys(
        section="trust_challenge_review_decision_sync_effect",
        payload=effect,
        keys=TRUST_CHALLENGE_REVIEW_DECISION_SYNC_EFFECT_KEYS,
    )
    if effect.get("ledgerAction") not in TRUST_CHALLENGE_REVIEW_LEDGER_ACTIONS:
        raise ValueError("trust_challenge_review_decision_sync_ledger_action_invalid")
    if effect.get("directWinnerWriteAllowed") is not False:
        raise ValueError("trust_challenge_review_decision_sync_direct_write_invalid")
    for key in (
        "requiresVerdictLedgerSource",
        "drawVoteRequired",
        "reviewRequired",
    ):
        if not isinstance(effect.get(key), bool):
            raise ValueError(f"trust_challenge_review_decision_sync_{key}_not_bool")

    expected_by_result = {
        "verdict_upheld": ("completed", "completed", "retain_original_verdict"),
        "verdict_overturned": (
            "awaiting_verdict_source",
            "review_required",
            "await_revised_verdict_ledger",
        ),
        "draw_after_review": (
            "draw_pending_vote",
            "draw_pending_vote",
            "open_draw_vote",
        ),
        "review_retained": (
            "review_retained",
            "review_required",
            "retain_review_required",
        ),
    }
    expected = expected_by_result.get(result)
    if expected is not None and (
        sync_state,
        user_visible_status,
        effect.get("ledgerAction"),
    ) != expected:
        raise ValueError("trust_challenge_review_decision_sync_result_mapping_invalid")
    _assert_non_empty_string(
        "trust_challenge_review_decision_sync_next_step",
        payload.get("nextStep"),
    )


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
    challenge_state = str(item.get("challengeState") or "").strip().lower()
    if challenge_state not in TRUST_CHALLENGE_REVIEW_CHALLENGE_STATES:
        raise ValueError("trust_challenge_review_item_challenge_state_invalid")
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
    review_decision_sync = item.get("reviewDecisionSync")
    if not isinstance(review_decision_sync, dict):
        raise ValueError("trust_challenge_review_item_decision_sync_not_dict")
    validate_trust_challenge_review_decision_sync_contract(review_decision_sync)
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
    active_challenge_id = str(item.get("activeChallengeId") or "").strip() or None
    if challenge_state in TRUST_CHALLENGE_REVIEW_OPEN_STATES and not active_challenge_id:
        raise ValueError("trust_challenge_review_item_active_challenge_id_required")
    if challenge_state not in TRUST_CHALLENGE_REVIEW_OPEN_STATES and active_challenge_id:
        raise ValueError("trust_challenge_review_item_active_challenge_id_unexpected")
    for row in challenges:
        if not isinstance(row, dict):
            raise ValueError("trust_challenge_review_item_challenge_not_dict")
        row_state = str(row.get("currentState") or "").strip().lower()
        if row_state not in TRUST_CHALLENGE_REVIEW_CHALLENGE_STATES:
            raise ValueError("trust_challenge_review_item_challenge_state_invalid")
    for row in timeline:
        if not isinstance(row, dict):
            raise ValueError("trust_challenge_review_item_timeline_item_not_dict")
        row_state = str(row.get("state") or "").strip().lower()
        if row_state and row_state not in TRUST_CHALLENGE_REVIEW_CHALLENGE_STATES:
            raise ValueError("trust_challenge_review_item_timeline_state_invalid")

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
