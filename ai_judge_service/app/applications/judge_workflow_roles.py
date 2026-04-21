from __future__ import annotations

from typing import Any

from ..models import FinalDispatchRequest, PhaseDispatchRequest
from .judge_app_domain import (
    build_judge_role_domain_state,
    validate_judge_app_domain_payload,
)


def _normalize_winner(value: Any) -> str | None:
    token = str(value or "").strip().lower()
    if token in {"pro", "con", "draw"}:
        return token
    return None


def _derive_winner_from_weighted_score(payload: dict[str, Any]) -> str | None:
    weighted = payload.get("agent3WeightedScore")
    if not isinstance(weighted, dict):
        return None
    try:
        pro_score = float(weighted.get("pro"))
        con_score = float(weighted.get("con"))
    except (TypeError, ValueError):
        return None
    if pro_score > con_score:
        return "pro"
    if con_score > pro_score:
        return "con"
    return "draw"


def _phase_claim_graph(payload: dict[str, Any]) -> dict[str, Any]:
    agent2 = payload.get("agent2Score")
    if not isinstance(agent2, dict):
        return {"stats": {}, "items": [], "unansweredClaimIds": []}
    hit_items = agent2.get("hitItems") if isinstance(agent2.get("hitItems"), list) else []
    miss_items = agent2.get("missItems") if isinstance(agent2.get("missItems"), list) else []
    items = [
        {"claimId": str(item), "status": "hit"}
        for item in hit_items
        if str(item or "").strip()
    ] + [
        {"claimId": str(item), "status": "miss"}
        for item in miss_items
        if str(item or "").strip()
    ]
    unanswered = [str(item) for item in miss_items if str(item or "").strip()]
    return {
        "stats": {
            "hitItems": len(hit_items),
            "missItems": len(miss_items),
            "totalClaims": len(items),
            "unansweredClaims": len(unanswered),
        },
        "items": items,
        "unansweredClaimIds": unanswered,
    }


def _phase_evidence_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    pro_bundle = payload.get("proRetrievalBundle")
    con_bundle = payload.get("conRetrievalBundle")
    pro_items = pro_bundle.get("items") if isinstance(pro_bundle, dict) else []
    con_items = con_bundle.get("items") if isinstance(con_bundle, dict) else []
    entries = [
        item
        for item in [*(pro_items if isinstance(pro_items, list) else []), *(con_items if isinstance(con_items, list) else [])]
        if isinstance(item, dict)
    ]
    return {
        "entries": entries,
        "sourceCitations": [],
        "conflictSources": [],
        "stats": {
            "entryCount": len(entries),
        },
    }


def _phase_panel_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    weighted = payload.get("agent3WeightedScore")
    pro_score = weighted.get("pro") if isinstance(weighted, dict) else None
    con_score = weighted.get("con") if isinstance(weighted, dict) else None
    winner = _derive_winner_from_weighted_score(payload)
    judges = {
        "phasePanel": {
            "winner": winner,
            "proScore": pro_score,
            "conScore": con_score,
            "reason": "phase_weighted_score",
        }
    }
    return {
        "topWinner": winner,
        "disagreementRatio": 0.0,
        "judges": judges,
    }


def _extract_final_panel_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    verdict_ledger = payload.get("verdictLedger")
    if not isinstance(verdict_ledger, dict):
        return {
            "topWinner": _normalize_winner(payload.get("winner")),
            "disagreementRatio": 0.0,
            "judges": {},
        }
    panel_decisions = verdict_ledger.get("panelDecisions")
    if not isinstance(panel_decisions, dict):
        return {
            "topWinner": _normalize_winner(payload.get("winner")),
            "disagreementRatio": 0.0,
            "judges": {},
        }
    return {
        "topWinner": _normalize_winner(
            panel_decisions.get("topWinner") or payload.get("winner")
        ),
        "disagreementRatio": float(panel_decisions.get("panelDisagreementRatio") or 0.0),
        "judges": (
            panel_decisions.get("judges")
            if isinstance(panel_decisions.get("judges"), dict)
            else {}
        ),
    }


def _extract_final_fairness_gate(payload: dict[str, Any]) -> dict[str, Any]:
    verdict_ledger = payload.get("verdictLedger")
    arbitration = (
        verdict_ledger.get("arbitration")
        if isinstance(verdict_ledger, dict) and isinstance(verdict_ledger.get("arbitration"), dict)
        else {}
    )
    gate_decision = str(arbitration.get("gateDecision") or "").strip().lower()
    review_required = bool(payload.get("reviewRequired"))
    if gate_decision not in {"pass_through", "blocked_to_draw"}:
        gate_decision = "blocked_to_draw" if review_required else "pass_through"

    audit_alert_ids = [
        str(item.get("alertId"))
        for item in (payload.get("auditAlerts") if isinstance(payload.get("auditAlerts"), list) else [])
        if isinstance(item, dict) and str(item.get("alertId") or "").strip()
    ]
    fairness_summary = payload.get("fairnessSummary")
    reasons = (
        fairness_summary.get("reviewReasons")
        if isinstance(fairness_summary, dict)
        and isinstance(fairness_summary.get("reviewReasons"), list)
        else []
    )
    if not reasons and review_required:
        reasons = (
            payload.get("errorCodes")
            if isinstance(payload.get("errorCodes"), list)
            else []
        )
    return {
        "decision": gate_decision,
        "reviewRequired": review_required,
        "reasons": [str(item) for item in reasons if str(item or "").strip()],
        "auditAlertIds": audit_alert_ids,
    }


def _extract_final_verdict(payload: dict[str, Any]) -> dict[str, Any]:
    verdict_ledger = payload.get("verdictLedger")
    arbitration = (
        verdict_ledger.get("arbitration")
        if isinstance(verdict_ledger, dict) and isinstance(verdict_ledger.get("arbitration"), dict)
        else {}
    )
    decision_path = arbitration.get("decisionPath")
    if not isinstance(decision_path, list) or not decision_path:
        decision_path = ["judge_panel", "fairness_sentinel", "chief_arbiter"]
    return {
        "winner": _normalize_winner(payload.get("winner")),
        "needsDrawVote": bool(payload.get("needsDrawVote")),
        "reviewRequired": bool(payload.get("reviewRequired")),
        "decisionPath": [str(item) for item in decision_path if str(item or "").strip()],
    }


def _extract_final_message_count(payload: dict[str, Any]) -> int:
    rows = payload.get("phaseRollupSummary")
    if not isinstance(rows, list):
        return 0
    total = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            total += max(0, int(row.get("messageCount") or 0))
        except (TypeError, ValueError):
            continue
    return total


def build_phase_judge_workflow_payload(
    *,
    request: PhaseDispatchRequest,
    report_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = report_payload if isinstance(report_payload, dict) else {}
    winner = _normalize_winner(payload.get("winner")) or _derive_winner_from_weighted_score(payload)
    review_required = bool(payload.get("reviewRequired"))
    state = build_judge_role_domain_state(
        case_id=request.case_id,
        dispatch_type="phase",
        trace_id=request.trace_id,
        scope_id=request.scope_id,
        session_id=request.session_id,
        phase_start_no=request.phase_no,
        phase_end_no=request.phase_no,
        message_count=request.message_count,
        judge_policy_version=request.judge_policy_version,
        rubric_version=request.rubric_version,
        topic_domain=request.topic_domain,
        claim_graph=_phase_claim_graph(payload),
        evidence_bundle=_phase_evidence_bundle(payload),
        panel_bundle=_phase_panel_bundle(payload),
        fairness_gate={
            "decision": "blocked_to_draw" if review_required else "pass_through",
            "reviewRequired": review_required,
        },
        verdict={
            "winner": winner,
            "needsDrawVote": bool(payload.get("needsDrawVote")),
            "reviewRequired": review_required,
        },
        opinion={
            "debateSummary": payload.get("debateSummary"),
            "sideAnalysis": (
                payload.get("sideAnalysis")
                if isinstance(payload.get("sideAnalysis"), dict)
                else {}
            ),
            "verdictReason": payload.get("verdictReason"),
        },
    )
    judge_payload = state.to_payload()
    validate_judge_app_domain_payload(judge_payload)
    return judge_payload


def build_final_judge_workflow_payload(
    *,
    request: FinalDispatchRequest,
    report_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = report_payload if isinstance(report_payload, dict) else {}
    phase_start_no = int(request.phase_start_no)
    phase_end_no = int(request.phase_end_no)
    state = build_judge_role_domain_state(
        case_id=request.case_id,
        dispatch_type="final",
        trace_id=request.trace_id,
        scope_id=request.scope_id,
        session_id=request.session_id,
        phase_start_no=phase_start_no,
        phase_end_no=phase_end_no,
        message_count=_extract_final_message_count(payload),
        judge_policy_version=request.judge_policy_version,
        rubric_version=request.rubric_version,
        topic_domain=request.topic_domain,
        claim_graph=(
            payload.get("claimGraph")
            if isinstance(payload.get("claimGraph"), dict)
            else {}
        ),
        evidence_bundle=(
            payload.get("evidenceLedger")
            if isinstance(payload.get("evidenceLedger"), dict)
            else {}
        ),
        panel_bundle=_extract_final_panel_bundle(payload),
        fairness_gate=_extract_final_fairness_gate(payload),
        verdict=_extract_final_verdict(payload),
        opinion={
            "debateSummary": payload.get("debateSummary"),
            "sideAnalysis": (
                payload.get("sideAnalysis")
                if isinstance(payload.get("sideAnalysis"), dict)
                else {}
            ),
            "verdictReason": payload.get("verdictReason"),
        },
    )
    judge_payload = state.to_payload()
    validate_judge_app_domain_payload(judge_payload)
    return judge_payload
