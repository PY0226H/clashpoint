from __future__ import annotations

from typing import Any

CASE_OVERVIEW_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "caseId",
    "workflow",
    "trace",
    "receipts",
    "latestDispatchType",
    "reportPayload",
    "verdictContract",
    "caseEvidence",
    "winner",
    "needsDrawVote",
    "reviewRequired",
    "callbackStatus",
    "callbackError",
    "judgeCore",
    "events",
    "alerts",
    "replays",
)

CASE_OVERVIEW_RECEIPTS_KEYS: tuple[str, ...] = (
    "phase",
    "final",
)

CASE_OVERVIEW_TRACE_KEYS: tuple[str, ...] = (
    "traceId",
    "status",
    "createdAt",
    "updatedAt",
)

CASE_OVERVIEW_JUDGE_CORE_KEYS: tuple[str, ...] = (
    "stage",
    "version",
    "eventSeq",
)

CASE_OVERVIEW_REPLAY_ITEM_KEYS: tuple[str, ...] = (
    "dispatchType",
    "traceId",
    "replayedAt",
    "winner",
    "needsDrawVote",
    "provider",
)

CASE_OVERVIEW_EVENT_ITEM_KEYS: tuple[str, ...] = (
    "eventSeq",
    "eventType",
    "payload",
    "createdAt",
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


def validate_case_overview_contract(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("case_overview_payload_not_dict")
    _assert_required_keys(
        section="case_overview",
        payload=payload,
        keys=CASE_OVERVIEW_TOP_LEVEL_KEYS,
    )
    case_id = _non_negative_int(payload.get("caseId"), default=0)
    if case_id <= 0:
        raise ValueError("case_overview_case_id_invalid")

    workflow = payload.get("workflow")
    _assert_optional_dict("case_overview_workflow", workflow)
    if isinstance(workflow, dict) and "status" not in workflow:
        raise ValueError("case_overview_workflow_missing_status")

    trace = payload.get("trace")
    _assert_optional_dict("case_overview_trace", trace)
    if isinstance(trace, dict):
        _assert_required_keys(
            section="case_overview_trace",
            payload=trace,
            keys=CASE_OVERVIEW_TRACE_KEYS,
        )

    receipts = payload.get("receipts")
    if not isinstance(receipts, dict):
        raise ValueError("case_overview_receipts_not_dict")
    _assert_required_keys(
        section="case_overview_receipts",
        payload=receipts,
        keys=CASE_OVERVIEW_RECEIPTS_KEYS,
    )
    _assert_optional_dict("case_overview_receipts_phase", receipts.get("phase"))
    _assert_optional_dict("case_overview_receipts_final", receipts.get("final"))

    latest_dispatch_type = payload.get("latestDispatchType")
    if latest_dispatch_type is not None:
        token = str(latest_dispatch_type).strip().lower()
        if token not in {"phase", "final"}:
            raise ValueError("case_overview_latest_dispatch_type_invalid")

    report_payload = payload.get("reportPayload")
    if not isinstance(report_payload, dict):
        raise ValueError("case_overview_report_payload_not_dict")
    verdict_contract = payload.get("verdictContract")
    if not isinstance(verdict_contract, dict):
        raise ValueError("case_overview_verdict_contract_not_dict")
    case_evidence = payload.get("caseEvidence")
    if not isinstance(case_evidence, dict):
        raise ValueError("case_overview_case_evidence_not_dict")

    winner = payload.get("winner")
    if winner is not None:
        winner_token = str(winner).strip().lower()
        if winner_token not in {"pro", "con", "draw"}:
            raise ValueError("case_overview_winner_invalid")

    needs_draw_vote = payload.get("needsDrawVote")
    if needs_draw_vote is not None and not isinstance(needs_draw_vote, bool):
        raise ValueError("case_overview_needs_draw_vote_not_bool")
    if not isinstance(payload.get("reviewRequired"), bool):
        raise ValueError("case_overview_review_required_not_bool")

    _assert_optional_string("case_overview_callback_status", payload.get("callbackStatus"))
    _assert_optional_string("case_overview_callback_error", payload.get("callbackError"))

    judge_core = payload.get("judgeCore")
    _assert_optional_dict("case_overview_judge_core", judge_core)
    if isinstance(judge_core, dict):
        _assert_required_keys(
            section="case_overview_judge_core",
            payload=judge_core,
            keys=CASE_OVERVIEW_JUDGE_CORE_KEYS,
        )

    events = payload.get("events")
    if not isinstance(events, list):
        raise ValueError("case_overview_events_not_list")
    for idx, row in enumerate(events):
        if not isinstance(row, dict):
            raise ValueError(f"case_overview_event_item_not_dict:{idx}")
        _assert_required_keys(
            section=f"case_overview_event_item_{idx}",
            payload=row,
            keys=CASE_OVERVIEW_EVENT_ITEM_KEYS,
        )

    alerts = payload.get("alerts")
    if not isinstance(alerts, list):
        raise ValueError("case_overview_alerts_not_list")
    replays = payload.get("replays")
    if not isinstance(replays, list):
        raise ValueError("case_overview_replays_not_list")
    for idx, row in enumerate(replays):
        if not isinstance(row, dict):
            raise ValueError(f"case_overview_replay_item_not_dict:{idx}")
        _assert_required_keys(
            section=f"case_overview_replay_item_{idx}",
            payload=row,
            keys=CASE_OVERVIEW_REPLAY_ITEM_KEYS,
        )
