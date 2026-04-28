from __future__ import annotations

from typing import Any

TRUST_CHALLENGE_QUEUE_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "count",
    "returned",
    "scanned",
    "skipped",
    "errorCount",
    "summary",
    "items",
    "errors",
    "filters",
)

TRUST_CHALLENGE_QUEUE_SUMMARY_KEYS: tuple[str, ...] = (
    "openCount",
    "urgentCount",
    "highPriorityCount",
    "oldestOpenAgeMinutes",
    "stateCounts",
    "reviewStateCounts",
    "priorityLevelCounts",
    "slaBucketCounts",
    "reasonCodeCounts",
    "actionHintCounts",
)

TRUST_CHALLENGE_QUEUE_ITEM_KEYS: tuple[str, ...] = (
    "caseId",
    "dispatchType",
    "traceId",
    "workflow",
    "trace",
    "challengeReview",
    "priorityProfile",
    "review",
    "actionHints",
    "actionPaths",
)

TRUST_CHALLENGE_QUEUE_WORKFLOW_KEYS: tuple[str, ...] = (
    "caseId",
    "dispatchType",
    "traceId",
    "status",
    "scopeId",
    "sessionId",
    "idempotencyKey",
    "rubricVersion",
    "judgePolicyVersion",
    "topicDomain",
    "retrievalProfile",
    "createdAt",
    "updatedAt",
)

TRUST_CHALLENGE_QUEUE_TRACE_KEYS: tuple[str, ...] = (
    "status",
    "callbackStatus",
    "callbackError",
    "updatedAt",
)

TRUST_CHALLENGE_QUEUE_CHALLENGE_REVIEW_KEYS: tuple[str, ...] = (
    "state",
    "activeChallengeId",
    "totalChallenges",
    "reviewState",
    "reviewRequired",
    "challengeReasons",
    "alertSummary",
    "openAlertIds",
    "timeline",
)

TRUST_CHALLENGE_QUEUE_PRIORITY_PROFILE_KEYS: tuple[str, ...] = (
    "score",
    "level",
    "tags",
    "ageMinutes",
    "slaBucket",
    "challengeState",
    "reviewState",
    "reviewRequired",
    "totalChallenges",
    "openAlertCount",
)

TRUST_CHALLENGE_QUEUE_REVIEW_KEYS: tuple[str, ...] = (
    "required",
    "state",
    "workflowStatus",
    "detailPath",
)

TRUST_CHALLENGE_QUEUE_ACTION_PATH_KEYS: tuple[str, ...] = (
    "requestChallengePath",
    "decisionPath",
    "reviewDetailPath",
)

TRUST_CHALLENGE_QUEUE_FILTER_KEYS: tuple[str, ...] = (
    "status",
    "dispatchType",
    "challengeState",
    "reviewState",
    "priorityLevel",
    "slaBucket",
    "hasOpenAlert",
    "sortBy",
    "sortOrder",
    "scanLimit",
    "offset",
    "limit",
)

TRUST_CHALLENGE_QUEUE_ERROR_KEYS: tuple[str, ...] = (
    "caseId",
    "statusCode",
    "errorCode",
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


def _assert_count_consistency(payload: dict[str, Any]) -> tuple[int, int, int, int, int]:
    count = _non_negative_int(payload.get("count"), default=0)
    returned = _non_negative_int(payload.get("returned"), default=0)
    scanned = _non_negative_int(payload.get("scanned"), default=0)
    skipped = _non_negative_int(payload.get("skipped"), default=0)
    error_count = _non_negative_int(payload.get("errorCount"), default=0)
    if returned > count:
        raise ValueError("trust_challenge_queue_returned_exceeds_count")
    if count > scanned:
        raise ValueError("trust_challenge_queue_count_exceeds_scanned")
    expected_skipped = max(0, scanned - count)
    if skipped != expected_skipped:
        raise ValueError("trust_challenge_queue_skipped_mismatch")
    return count, returned, scanned, skipped, error_count


def _validate_item(payload: dict[str, Any]) -> None:
    _assert_required_keys(
        section="trust_challenge_queue_item",
        payload=payload,
        keys=TRUST_CHALLENGE_QUEUE_ITEM_KEYS,
    )
    case_id = _non_negative_int(payload.get("caseId"), default=0)
    if case_id <= 0:
        raise ValueError("trust_challenge_queue_item_case_id_invalid")
    dispatch_type = str(payload.get("dispatchType") or "").strip().lower()
    if dispatch_type not in {"phase", "final"}:
        raise ValueError("trust_challenge_queue_item_dispatch_type_invalid")

    workflow = payload.get("workflow")
    if not isinstance(workflow, dict):
        raise ValueError("trust_challenge_queue_item_workflow_not_dict")
    _assert_required_keys(
        section="trust_challenge_queue_item_workflow",
        payload=workflow,
        keys=TRUST_CHALLENGE_QUEUE_WORKFLOW_KEYS,
    )
    if _non_negative_int(workflow.get("caseId"), default=0) != case_id:
        raise ValueError("trust_challenge_queue_item_workflow_case_id_mismatch")

    trace_payload = payload.get("trace")
    if not isinstance(trace_payload, dict):
        raise ValueError("trust_challenge_queue_item_trace_not_dict")
    _assert_required_keys(
        section="trust_challenge_queue_item_trace",
        payload=trace_payload,
        keys=TRUST_CHALLENGE_QUEUE_TRACE_KEYS,
    )

    challenge_review = payload.get("challengeReview")
    if not isinstance(challenge_review, dict):
        raise ValueError("trust_challenge_queue_item_challenge_review_not_dict")
    _assert_required_keys(
        section="trust_challenge_queue_item_challenge_review",
        payload=challenge_review,
        keys=TRUST_CHALLENGE_QUEUE_CHALLENGE_REVIEW_KEYS,
    )
    if not isinstance(challenge_review.get("reviewRequired"), bool):
        raise ValueError("trust_challenge_queue_item_review_required_not_bool")
    if not isinstance(challenge_review.get("challengeReasons"), list):
        raise ValueError("trust_challenge_queue_item_challenge_reasons_not_list")
    if not isinstance(challenge_review.get("alertSummary"), dict):
        raise ValueError("trust_challenge_queue_item_alert_summary_not_dict")
    if not isinstance(challenge_review.get("openAlertIds"), list):
        raise ValueError("trust_challenge_queue_item_open_alert_ids_not_list")
    if not isinstance(challenge_review.get("timeline"), list):
        raise ValueError("trust_challenge_queue_item_timeline_not_list")

    priority_profile = payload.get("priorityProfile")
    if not isinstance(priority_profile, dict):
        raise ValueError("trust_challenge_queue_item_priority_profile_not_dict")
    _assert_required_keys(
        section="trust_challenge_queue_item_priority_profile",
        payload=priority_profile,
        keys=TRUST_CHALLENGE_QUEUE_PRIORITY_PROFILE_KEYS,
    )
    score = _non_negative_int(priority_profile.get("score"), default=-1)
    if score < 0 or score > 100:
        raise ValueError("trust_challenge_queue_item_priority_score_invalid")
    if not isinstance(priority_profile.get("tags"), list):
        raise ValueError("trust_challenge_queue_item_priority_tags_not_list")
    if not isinstance(priority_profile.get("reviewRequired"), bool):
        raise ValueError("trust_challenge_queue_item_priority_review_required_not_bool")

    review = payload.get("review")
    if not isinstance(review, dict):
        raise ValueError("trust_challenge_queue_item_review_not_dict")
    _assert_required_keys(
        section="trust_challenge_queue_item_review",
        payload=review,
        keys=TRUST_CHALLENGE_QUEUE_REVIEW_KEYS,
    )
    if not isinstance(review.get("required"), bool):
        raise ValueError("trust_challenge_queue_item_review_required_flag_not_bool")
    detail_path = str(review.get("detailPath") or "").strip()
    if not detail_path.startswith("/internal/judge/review/cases/"):
        raise ValueError("trust_challenge_queue_item_review_detail_path_invalid")

    action_hints = payload.get("actionHints")
    if not isinstance(action_hints, list):
        raise ValueError("trust_challenge_queue_item_action_hints_not_list")
    action_paths = payload.get("actionPaths")
    if not isinstance(action_paths, dict):
        raise ValueError("trust_challenge_queue_item_action_paths_not_dict")
    _assert_required_keys(
        section="trust_challenge_queue_item_action_paths",
        payload=action_paths,
        keys=TRUST_CHALLENGE_QUEUE_ACTION_PATH_KEYS,
    )
    request_path = str(action_paths.get("requestChallengePath") or "").strip()
    if not request_path.startswith("/internal/judge/cases/"):
        raise ValueError("trust_challenge_queue_item_request_path_invalid")
    review_detail_path = str(action_paths.get("reviewDetailPath") or "").strip()
    if not review_detail_path.startswith("/internal/judge/review/cases/"):
        raise ValueError("trust_challenge_queue_item_review_detail_path_invalid")


def validate_trust_challenge_queue_contract(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("trust_challenge_queue_payload_not_dict")
    _assert_required_keys(
        section="trust_challenge_queue",
        payload=payload,
        keys=TRUST_CHALLENGE_QUEUE_TOP_LEVEL_KEYS,
    )
    _, returned, _, _, error_count = _assert_count_consistency(payload)

    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("trust_challenge_queue_summary_not_dict")
    _assert_required_keys(
        section="trust_challenge_queue_summary",
        payload=summary,
        keys=TRUST_CHALLENGE_QUEUE_SUMMARY_KEYS,
    )
    for key in (
        "stateCounts",
        "reviewStateCounts",
        "priorityLevelCounts",
        "slaBucketCounts",
        "reasonCodeCounts",
        "actionHintCounts",
    ):
        if not isinstance(summary.get(key), dict):
            raise ValueError(f"trust_challenge_queue_summary_{key}_not_dict")
    for key in ("openCount", "urgentCount", "highPriorityCount"):
        _non_negative_int(summary.get(key), default=0)
    oldest_open_age = summary.get("oldestOpenAgeMinutes")
    if oldest_open_age is not None:
        _non_negative_int(oldest_open_age, default=0)

    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("trust_challenge_queue_items_not_list")
    if len(items) != returned:
        raise ValueError("trust_challenge_queue_returned_mismatch")
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("trust_challenge_queue_item_not_dict")
        _validate_item(item)

    errors = payload.get("errors")
    if not isinstance(errors, list):
        raise ValueError("trust_challenge_queue_errors_not_list")
    if len(errors) != error_count:
        raise ValueError("trust_challenge_queue_error_count_mismatch")
    for error_item in errors:
        if not isinstance(error_item, dict):
            raise ValueError("trust_challenge_queue_error_item_not_dict")
        _assert_required_keys(
            section="trust_challenge_queue_error_item",
            payload=error_item,
            keys=TRUST_CHALLENGE_QUEUE_ERROR_KEYS,
        )
        if _non_negative_int(error_item.get("caseId"), default=0) <= 0:
            raise ValueError("trust_challenge_queue_error_item_case_id_invalid")
        if _non_negative_int(error_item.get("statusCode"), default=0) < 400:
            raise ValueError("trust_challenge_queue_error_item_status_code_invalid")
        if not str(error_item.get("errorCode") or "").strip():
            raise ValueError("trust_challenge_queue_error_item_error_code_empty")

    filters = payload.get("filters")
    if not isinstance(filters, dict):
        raise ValueError("trust_challenge_queue_filters_not_dict")
    _assert_required_keys(
        section="trust_challenge_queue_filters",
        payload=filters,
        keys=TRUST_CHALLENGE_QUEUE_FILTER_KEYS,
    )
    if str(filters.get("dispatchType") or "").strip().lower() not in {"auto", "phase", "final"}:
        raise ValueError("trust_challenge_queue_filters_dispatch_type_invalid")
    if _non_negative_int(filters.get("scanLimit"), default=0) <= 0:
        raise ValueError("trust_challenge_queue_filters_scan_limit_invalid")
    if _non_negative_int(filters.get("limit"), default=0) <= 0:
        raise ValueError("trust_challenge_queue_filters_limit_invalid")
    if str(filters.get("sortOrder") or "").strip().lower() not in {"asc", "desc"}:
        raise ValueError("trust_challenge_queue_filters_sort_order_invalid")
