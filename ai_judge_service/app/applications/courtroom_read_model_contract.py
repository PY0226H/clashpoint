from __future__ import annotations

from typing import Any

COURTROOM_READ_MODEL_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "caseId",
    "dispatchType",
    "traceId",
    "generatedAt",
    "workflow",
    "judgeCore",
    "callback",
    "report",
    "courtroom",
    "events",
    "eventCount",
    "alerts",
    "filters",
)

COURTROOM_READ_MODEL_CALLBACK_KEYS: tuple[str, ...] = (
    "status",
    "error",
)

COURTROOM_READ_MODEL_REPORT_KEYS: tuple[str, ...] = (
    "winner",
    "reviewRequired",
    "needsDrawVote",
    "debateSummary",
    "sideAnalysis",
    "verdictReason",
)

COURTROOM_READ_MODEL_FILTER_KEYS: tuple[str, ...] = (
    "dispatchType",
    "includeEvents",
    "includeAlerts",
    "alertLimit",
)

COURTROOM_READ_MODEL_COURTROOM_KEYS: tuple[str, ...] = (
    "recorder",
    "claim",
    "evidence",
    "panel",
    "fairness",
    "opinion",
    "governance",
)

COURTROOM_RECORDER_KEYS: tuple[str, ...] = ("caseDossier",)
COURTROOM_CLAIM_KEYS: tuple[str, ...] = ("claimGraph",)
COURTROOM_EVIDENCE_KEYS: tuple[str, ...] = ("evidenceLedger",)
COURTROOM_PANEL_KEYS: tuple[str, ...] = ("panelDecisions",)
COURTROOM_FAIRNESS_KEYS: tuple[str, ...] = ("summary",)
COURTROOM_OPINION_KEYS: tuple[str, ...] = ("sideAnalysis",)


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


def _assert_optional_dict(section: str, value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError(f"{section}_not_dict")


def _assert_optional_string(section: str, value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise ValueError(f"{section}_not_string")


def validate_courtroom_read_model_contract(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("courtroom_read_model_payload_not_dict")
    _assert_required_keys(
        section="courtroom_read_model",
        payload=payload,
        keys=COURTROOM_READ_MODEL_TOP_LEVEL_KEYS,
    )
    case_id = _non_negative_int(payload.get("caseId"), default=0)
    if case_id <= 0:
        raise ValueError("courtroom_read_model_case_id_invalid")

    dispatch_type = str(payload.get("dispatchType") or "").strip().lower()
    if dispatch_type not in {"phase", "final"}:
        raise ValueError("courtroom_read_model_dispatch_type_invalid")
    trace_id = payload.get("traceId")
    if trace_id is not None and not isinstance(trace_id, str):
        raise ValueError("courtroom_read_model_trace_id_not_string")
    if not str(payload.get("generatedAt") or "").strip():
        raise ValueError("courtroom_read_model_generated_at_empty")

    _assert_optional_dict("courtroom_read_model_workflow", payload.get("workflow"))
    _assert_optional_dict("courtroom_read_model_judge_core", payload.get("judgeCore"))

    callback = payload.get("callback")
    if not isinstance(callback, dict):
        raise ValueError("courtroom_read_model_callback_not_dict")
    _assert_required_keys(
        section="courtroom_read_model_callback",
        payload=callback,
        keys=COURTROOM_READ_MODEL_CALLBACK_KEYS,
    )
    _assert_optional_string("courtroom_read_model_callback_status", callback.get("status"))
    _assert_optional_string("courtroom_read_model_callback_error", callback.get("error"))

    report = payload.get("report")
    if not isinstance(report, dict):
        raise ValueError("courtroom_read_model_report_not_dict")
    _assert_required_keys(
        section="courtroom_read_model_report",
        payload=report,
        keys=COURTROOM_READ_MODEL_REPORT_KEYS,
    )
    winner = report.get("winner")
    if winner is not None:
        token = str(winner).strip().lower()
        if token not in {"pro", "con", "draw"}:
            raise ValueError("courtroom_read_model_report_winner_invalid")
    if not isinstance(report.get("reviewRequired"), bool):
        raise ValueError("courtroom_read_model_report_review_required_not_bool")
    if not isinstance(report.get("needsDrawVote"), bool):
        raise ValueError("courtroom_read_model_report_needs_draw_vote_not_bool")
    _assert_optional_string(
        "courtroom_read_model_report_debate_summary",
        report.get("debateSummary"),
    )
    if not isinstance(report.get("sideAnalysis"), dict):
        raise ValueError("courtroom_read_model_report_side_analysis_not_dict")
    _assert_optional_string(
        "courtroom_read_model_report_verdict_reason",
        report.get("verdictReason"),
    )

    courtroom = payload.get("courtroom")
    if not isinstance(courtroom, dict):
        raise ValueError("courtroom_read_model_courtroom_not_dict")
    _assert_required_keys(
        section="courtroom_read_model_courtroom",
        payload=courtroom,
        keys=COURTROOM_READ_MODEL_COURTROOM_KEYS,
    )
    for section, key, required_keys in (
        (
            "courtroom_read_model_courtroom_recorder",
            "recorder",
            COURTROOM_RECORDER_KEYS,
        ),
        ("courtroom_read_model_courtroom_claim", "claim", COURTROOM_CLAIM_KEYS),
        (
            "courtroom_read_model_courtroom_evidence",
            "evidence",
            COURTROOM_EVIDENCE_KEYS,
        ),
        ("courtroom_read_model_courtroom_panel", "panel", COURTROOM_PANEL_KEYS),
        (
            "courtroom_read_model_courtroom_fairness",
            "fairness",
            COURTROOM_FAIRNESS_KEYS,
        ),
        (
            "courtroom_read_model_courtroom_opinion",
            "opinion",
            COURTROOM_OPINION_KEYS,
        ),
    ):
        item = courtroom.get(key)
        if not isinstance(item, dict):
            raise ValueError(f"{section}_not_dict")
        _assert_required_keys(
            section=section,
            payload=item,
            keys=required_keys,
        )
    governance = courtroom.get("governance")
    if not isinstance(governance, dict):
        raise ValueError("courtroom_read_model_courtroom_governance_not_dict")

    events = payload.get("events")
    if not isinstance(events, list):
        raise ValueError("courtroom_read_model_events_not_list")
    alerts = payload.get("alerts")
    if not isinstance(alerts, list):
        raise ValueError("courtroom_read_model_alerts_not_list")
    event_count = _non_negative_int(payload.get("eventCount"), default=-1)
    if event_count < 0:
        raise ValueError("courtroom_read_model_event_count_invalid")

    filters = payload.get("filters")
    if not isinstance(filters, dict):
        raise ValueError("courtroom_read_model_filters_not_dict")
    _assert_required_keys(
        section="courtroom_read_model_filters",
        payload=filters,
        keys=COURTROOM_READ_MODEL_FILTER_KEYS,
    )
    filter_dispatch_type = str(filters.get("dispatchType") or "").strip().lower()
    if filter_dispatch_type not in {"phase", "final"}:
        raise ValueError("courtroom_read_model_filters_dispatch_type_invalid")
    if not isinstance(filters.get("includeEvents"), bool):
        raise ValueError("courtroom_read_model_filters_include_events_not_bool")
    if not isinstance(filters.get("includeAlerts"), bool):
        raise ValueError("courtroom_read_model_filters_include_alerts_not_bool")
    if _non_negative_int(filters.get("alertLimit"), default=-1) <= 0:
        raise ValueError("courtroom_read_model_filters_alert_limit_invalid")
