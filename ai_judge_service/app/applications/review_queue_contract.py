from __future__ import annotations

from typing import Any

REVIEW_QUEUE_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "count",
    "returned",
    "scanned",
    "skipped",
    "errorCount",
    "items",
    "errors",
    "aggregations",
    "filters",
)

COURTROOM_DRILLDOWN_ITEM_KEYS: tuple[str, ...] = (
    "caseId",
    "dispatchType",
    "traceId",
    "workflow",
    "winner",
    "reviewRequired",
    "needsDrawVote",
    "callbackStatus",
    "callbackError",
    "riskProfile",
    "drilldown",
    "actionHints",
    "detailPath",
)

COURTROOM_DRILLDOWN_AGGREGATION_KEYS: tuple[str, ...] = (
    "totalConflictPairCount",
    "totalUnansweredClaimCount",
    "totalDecisiveEvidenceCount",
    "totalPivotalMomentCount",
    "reviewRequiredCount",
    "highRiskCount",
)

COURTROOM_DRILLDOWN_FILTER_KEYS: tuple[str, ...] = (
    "status",
    "dispatchType",
    "winner",
    "reviewRequired",
    "riskLevel",
    "slaBucket",
    "updatedFrom",
    "updatedTo",
    "sortBy",
    "sortOrder",
    "scanLimit",
    "offset",
    "limit",
    "claimPreviewLimit",
    "evidencePreviewLimit",
    "panelPreviewLimit",
)

EVIDENCE_CLAIM_ITEM_KEYS: tuple[str, ...] = (
    "caseId",
    "dispatchType",
    "traceId",
    "workflow",
    "winner",
    "reviewRequired",
    "needsDrawVote",
    "callbackStatus",
    "callbackError",
    "riskProfile",
    "courtroomSummary",
    "claimEvidenceProfile",
    "actionHints",
    "detailPath",
)

EVIDENCE_CLAIM_AGGREGATION_KEYS: tuple[str, ...] = (
    "riskLevelCounts",
    "reliabilityLevelCounts",
    "conflictCaseCount",
    "unansweredCaseCount",
)

EVIDENCE_CLAIM_FILTER_KEYS: tuple[str, ...] = (
    "status",
    "dispatchType",
    "winner",
    "reviewRequired",
    "riskLevel",
    "slaBucket",
    "reliabilityLevel",
    "hasConflict",
    "hasUnansweredClaim",
    "updatedFrom",
    "updatedTo",
    "sortBy",
    "sortOrder",
    "scanLimit",
    "offset",
    "limit",
)

REVIEW_QUEUE_ERROR_KEYS: tuple[str, ...] = (
    "caseId",
    "statusCode",
    "errorCode",
)

COURTROOM_DRILLDOWN_KEYS: tuple[str, ...] = (
    "claim",
    "evidence",
    "panel",
    "fairness",
    "opinion",
    "governance",
)

COURTROOM_SUMMARY_KEYS: tuple[str, ...] = (
    "recorder",
    "claim",
    "evidence",
    "panel",
    "fairness",
    "opinion",
)


def _to_non_negative_int(value: Any, *, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return default
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, parsed)


def _require_keys(*, section: str, payload: dict[str, Any], keys: tuple[str, ...]) -> None:
    missing = [key for key in keys if key not in payload]
    if missing:
        raise ValueError(f"{section}_missing_keys:{','.join(sorted(missing))}")


def _validate_review_queue_common(
    *,
    section: str,
    payload: dict[str, Any],
    item_keys: tuple[str, ...],
    aggregation_keys: tuple[str, ...],
    filter_keys: tuple[str, ...],
) -> None:
    if not isinstance(payload, dict):
        raise ValueError(f"{section}_payload_not_dict")
    _require_keys(section=section, payload=payload, keys=REVIEW_QUEUE_TOP_LEVEL_KEYS)

    count = _to_non_negative_int(payload.get("count"), default=0)
    returned = _to_non_negative_int(payload.get("returned"), default=0)
    scanned = _to_non_negative_int(payload.get("scanned"), default=0)
    skipped = _to_non_negative_int(payload.get("skipped"), default=0)
    error_count = _to_non_negative_int(payload.get("errorCount"), default=0)

    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError(f"{section}_items_not_list")
    errors = payload.get("errors")
    if not isinstance(errors, list):
        raise ValueError(f"{section}_errors_not_list")
    aggregations = payload.get("aggregations")
    if not isinstance(aggregations, dict):
        raise ValueError(f"{section}_aggregations_not_dict")
    filters = payload.get("filters")
    if not isinstance(filters, dict):
        raise ValueError(f"{section}_filters_not_dict")

    if returned != len(items):
        raise ValueError(f"{section}_returned_count_mismatch")
    if error_count != len(errors):
        raise ValueError(f"{section}_error_count_mismatch")
    if count < returned:
        raise ValueError(f"{section}_count_less_than_returned")
    if scanned < count:
        raise ValueError(f"{section}_scanned_less_than_count")
    if skipped > scanned:
        raise ValueError(f"{section}_skipped_exceeds_scanned")

    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f"{section}_item_not_dict")
        _require_keys(section=f"{section}_item", payload=item, keys=item_keys)

    for row in errors:
        if not isinstance(row, dict):
            raise ValueError(f"{section}_error_item_not_dict")
        _require_keys(
            section=f"{section}_error_item",
            payload=row,
            keys=REVIEW_QUEUE_ERROR_KEYS,
        )

    _require_keys(
        section=f"{section}_aggregations",
        payload=aggregations,
        keys=aggregation_keys,
    )
    _require_keys(section=f"{section}_filters", payload=filters, keys=filter_keys)


def validate_courtroom_drilldown_bundle_contract(payload: dict[str, Any]) -> None:
    _validate_review_queue_common(
        section="courtroom_drilldown_bundle",
        payload=payload,
        item_keys=COURTROOM_DRILLDOWN_ITEM_KEYS,
        aggregation_keys=COURTROOM_DRILLDOWN_AGGREGATION_KEYS,
        filter_keys=COURTROOM_DRILLDOWN_FILTER_KEYS,
    )

    if "notes" not in payload:
        raise ValueError("courtroom_drilldown_bundle_missing_notes")
    notes = payload.get("notes")
    if not isinstance(notes, list):
        raise ValueError("courtroom_drilldown_bundle_notes_not_list")

    items = payload.get("items")
    assert isinstance(items, list)
    for idx, row in enumerate(items):
        assert isinstance(row, dict)
        drilldown = row.get("drilldown")
        if not isinstance(drilldown, dict):
            raise ValueError(f"courtroom_drilldown_bundle_drilldown_not_dict:{idx}")
        _require_keys(
            section=f"courtroom_drilldown_bundle_drilldown_{idx}",
            payload=drilldown,
            keys=COURTROOM_DRILLDOWN_KEYS,
        )

    aggregations = payload.get("aggregations")
    assert isinstance(aggregations, dict)
    for key in COURTROOM_DRILLDOWN_AGGREGATION_KEYS:
        if _to_non_negative_int(aggregations.get(key), default=-1) < 0:
            raise ValueError(f"courtroom_drilldown_bundle_{key}_invalid")


def validate_evidence_claim_ops_queue_contract(payload: dict[str, Any]) -> None:
    _validate_review_queue_common(
        section="evidence_claim_ops_queue",
        payload=payload,
        item_keys=EVIDENCE_CLAIM_ITEM_KEYS,
        aggregation_keys=EVIDENCE_CLAIM_AGGREGATION_KEYS,
        filter_keys=EVIDENCE_CLAIM_FILTER_KEYS,
    )

    aggregations = payload.get("aggregations")
    assert isinstance(aggregations, dict)
    risk_level_counts = aggregations.get("riskLevelCounts")
    if not isinstance(risk_level_counts, dict):
        raise ValueError("evidence_claim_ops_queue_risk_level_counts_not_dict")
    _require_keys(
        section="evidence_claim_ops_queue_risk_level_counts",
        payload=risk_level_counts,
        keys=("high", "medium", "low"),
    )
    reliability_level_counts = aggregations.get("reliabilityLevelCounts")
    if not isinstance(reliability_level_counts, dict):
        raise ValueError("evidence_claim_ops_queue_reliability_level_counts_not_dict")
    _require_keys(
        section="evidence_claim_ops_queue_reliability_level_counts",
        payload=reliability_level_counts,
        keys=("high", "medium", "low", "unknown"),
    )
    for key in ("conflictCaseCount", "unansweredCaseCount"):
        if _to_non_negative_int(aggregations.get(key), default=-1) < 0:
            raise ValueError(f"evidence_claim_ops_queue_{key}_invalid")

    items = payload.get("items")
    assert isinstance(items, list)
    for idx, row in enumerate(items):
        assert isinstance(row, dict)
        courtroom_summary = row.get("courtroomSummary")
        if not isinstance(courtroom_summary, dict):
            raise ValueError(f"evidence_claim_ops_queue_courtroom_summary_not_dict:{idx}")
        _require_keys(
            section=f"evidence_claim_ops_queue_courtroom_summary_{idx}",
            payload=courtroom_summary,
            keys=COURTROOM_SUMMARY_KEYS,
        )
