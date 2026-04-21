from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ...models import FinalDispatchRequest
from ...style_mode import resolve_effective_style_mode
from .claim_graph import build_claim_graph_payload
from .evidence_ledger import EvidenceLedgerBuilder

PANEL_RUNTIME_PROFILE_DEFAULTS = {
    "judgeA": {
        "profileId": "panel-judgeA-weighted-v1",
        "modelStrategy": "deterministic_weighted",
        "strategySlot": "weighted_vote",
        "scoreSource": "agent3WeightedScore",
        "decisionMargin": 0.8,
        "domainSlot": "general",
        "runtimeStage": "bootstrap",
    },
    "judgeB": {
        "profileId": "panel-judgeB-path-alignment-v1",
        "modelStrategy": "deterministic_path_alignment",
        "strategySlot": "path_alignment",
        "scoreSource": "agent2Score",
        "decisionMargin": 0.8,
        "domainSlot": "general",
        "runtimeStage": "bootstrap",
    },
    "judgeC": {
        "profileId": "panel-judgeC-dimension-composite-v1",
        "modelStrategy": "deterministic_dimension_composite",
        "strategySlot": "dimension_composite",
        "scoreSource": "agent1Dimensions",
        "decisionMargin": 0.8,
        "domainSlot": "general",
        "runtimeStage": "bootstrap",
    },
}

_FINAL_ARBITRATION_GATE_DECISIONS = {"pass_through", "blocked_to_draw"}


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, *, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def _resolve_winner(pro_score: float, con_score: float, *, margin: float = 1.0) -> str:
    if pro_score - con_score >= margin:
        return "pro"
    if con_score - pro_score >= margin:
        return "con"
    return "draw"


def _extract_phase_report_payload_from_receipt(receipt: Any) -> tuple[int, dict[str, Any] | None]:
    phase_no = int(getattr(receipt, "phase_no", 0) or 0)
    response = getattr(receipt, "response", None)
    if not isinstance(response, dict):
        return phase_no, None
    report = (
        response.get("reportPayload")
        or response.get("phaseReport")
        or response.get("phase_report_payload")
    )
    if not isinstance(report, dict):
        return phase_no, None
    return phase_no, report


def _extract_agent1_dimensions(payload: dict[str, Any], *, side: str) -> dict[str, float]:
    agent1 = payload.get("agent1Score") if isinstance(payload.get("agent1Score"), dict) else {}
    dimensions = agent1.get("dimensions") if isinstance(agent1.get("dimensions"), dict) else {}
    side_dimensions = dimensions.get(side) if isinstance(dimensions.get(side), dict) else None
    if isinstance(side_dimensions, dict):
        return {
            "logic": _clamp_score(_safe_float(side_dimensions.get("logic"), default=50.0)),
            "evidence": _clamp_score(_safe_float(side_dimensions.get("evidence"), default=50.0)),
            "rebuttal": _clamp_score(_safe_float(side_dimensions.get("rebuttal"), default=50.0)),
            "clarity": _clamp_score(_safe_float(side_dimensions.get("expression"), default=50.0)),
        }
    return {
        "logic": 50.0,
        "evidence": 50.0,
        "rebuttal": 50.0,
        "clarity": 50.0,
    }


def _parse_agent2_ref_item(raw: Any) -> tuple[str, str]:
    text = str(raw or "").strip()
    if not text:
        return "unknown", ""
    if ":" in text:
        prefix, rest = text.split(":", 1)
        side = prefix.strip().lower()
        if side in {"pro", "con"}:
            return side, rest.strip()
    return "unknown", text


def _winner_label(winner: str) -> str:
    mapping = {
        "pro": "pro side",
        "con": "con side",
        "draw": "draw",
    }
    return mapping.get(str(winner or "").strip().lower(), "unknown")


def _build_style_probe_winners(*, pro_score: float, con_score: float) -> dict[str, str]:
    return {
        "rational": _resolve_winner(pro_score, con_score, margin=0.8),
        "neutral": _resolve_winner(pro_score, con_score, margin=1.0),
        "strict": _resolve_winner(pro_score, con_score, margin=1.3),
    }


def _score_gap(pro_score: float, con_score: float) -> float:
    return round(abs(_clamp_score(pro_score) - _clamp_score(con_score)), 2)


def _score_confidence(*, score_gap: float, cap: float = 12.0) -> float:
    normalized = max(0.0, min(1.0, float(score_gap) / max(1.0, float(cap))))
    return round(normalized, 4)


def _build_panel_judge_item(
    *,
    judge_id: str,
    name: str,
    source: str,
    winner: str,
    pro_score: float,
    con_score: float,
    reason: str,
    runtime_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gap = _score_gap(pro_score, con_score)
    return {
        "judgeId": judge_id,
        "name": name,
        "source": source,
        "winner": winner,
        "proScore": round(_clamp_score(pro_score), 2),
        "conScore": round(_clamp_score(con_score), 2),
        "scoreGap": gap,
        "confidence": _score_confidence(score_gap=gap),
        "reason": str(reason or "").strip(),
        "runtimeProfile": (
            dict(runtime_profile)
            if isinstance(runtime_profile, dict)
            else {}
        ),
    }


def _normalize_panel_runtime_profiles(
    raw_profiles: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    def _normalize_text_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        out: list[str] = []
        seen: set[str] = set()
        for item in value:
            token = str(item or "").strip()
            if not token or token in seen:
                continue
            seen.add(token)
            out.append(token)
        return out

    def _to_bool(value: Any, *, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value or "").strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return True
        if text in {"0", "false", "no", "n", "off"}:
            return False
        return default

    source = raw_profiles if isinstance(raw_profiles, dict) else {}
    out: dict[str, dict[str, Any]] = {}
    for judge_id, defaults in PANEL_RUNTIME_PROFILE_DEFAULTS.items():
        row = source.get(judge_id) if isinstance(source.get(judge_id), dict) else {}
        out[judge_id] = {
            "judgeId": judge_id,
            "profileId": str(
                row.get("profileId")
                or row.get("profile_id")
                or defaults["profileId"]
            ).strip()
            or defaults["profileId"],
            "modelStrategy": str(
                row.get("modelStrategy")
                or row.get("model_strategy")
                or defaults["modelStrategy"]
            ).strip()
            or defaults["modelStrategy"],
            "strategySlot": str(
                row.get("strategySlot")
                or row.get("strategy_slot")
                or defaults["strategySlot"]
            ).strip()
            or defaults["strategySlot"],
            "scoreSource": str(
                row.get("scoreSource")
                or row.get("score_source")
                or defaults["scoreSource"]
            ).strip()
            or defaults["scoreSource"],
            "decisionMargin": max(
                0.0,
                _safe_float(
                    row.get("decisionMargin") or row.get("decision_margin"),
                    default=float(defaults["decisionMargin"]),
                ),
            ),
            "promptVersion": (
                str(row.get("promptVersion") or row.get("prompt_version") or "").strip()
                or None
            ),
            "toolsetVersion": (
                str(row.get("toolsetVersion") or row.get("toolset_version") or "").strip()
                or None
            ),
            "policyVersion": (
                str(row.get("policyVersion") or row.get("policy_version") or "").strip()
                or None
            ),
            "domainSlot": str(
                row.get("domainSlot")
                or row.get("domain_slot")
                or defaults["domainSlot"]
            ).strip()
            or defaults["domainSlot"],
            "runtimeStage": str(
                row.get("runtimeStage")
                or row.get("runtime_stage")
                or defaults["runtimeStage"]
            ).strip()
            or defaults["runtimeStage"],
            "adaptiveEnabled": _to_bool(
                row.get("adaptiveEnabled")
                if row.get("adaptiveEnabled") is not None
                else row.get("adaptive_enabled"),
                default=False,
            ),
            "candidateModels": _normalize_text_list(
                row.get("candidateModels")
                if row.get("candidateModels") is not None
                else row.get("candidate_models")
            ),
            "strategyMetadata": (
                dict(row.get("strategyMetadata"))
                if isinstance(row.get("strategyMetadata"), dict)
                else (
                    dict(row.get("strategy_metadata"))
                    if isinstance(row.get("strategy_metadata"), dict)
                    else {}
                )
            ),
            "profileSource": str(
                row.get("profileSource")
                or row.get("profile_source")
                or "builtin_default"
            ).strip()
            or "builtin_default",
        }
    return out


def _index_retrieval_items(payload: dict[str, Any], *, side: str) -> dict[str, dict[str, Any]]:
    bundle_key = "proRetrievalBundle" if side == "pro" else "conRetrievalBundle"
    bundle = payload.get(bundle_key) if isinstance(payload.get(bundle_key), dict) else {}
    rows = bundle.get("items") if isinstance(bundle.get("items"), list) else []
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        chunk_id = str(row.get("chunkId") or row.get("chunk_id") or "").strip()
        if not chunk_id or chunk_id in out:
            continue
        out[chunk_id] = row
    return out


def _collect_pivotal_moments(phase_rollup_summary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked: list[tuple[float, int, dict[str, Any]]] = []
    for row in phase_rollup_summary:
        if not isinstance(row, dict):
            continue
        try:
            phase_no = int(row.get("phaseNo"))
        except (TypeError, ValueError):
            continue
        pro_score = _safe_float(row.get("proScore"), default=50.0)
        con_score = _safe_float(row.get("conScore"), default=50.0)
        gap = round(abs(pro_score - con_score), 2)
        ranked.append((gap, phase_no, row))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    out: list[dict[str, Any]] = []
    for gap, _, row in ranked[:5]:
        out.append(
            {
                "phaseNo": row.get("phaseNo"),
                "winnerHint": row.get("winnerHint"),
                "scoreGap": gap,
                "messageStartId": row.get("messageStartId"),
                "messageEndId": row.get("messageEndId"),
                "messageCount": row.get("messageCount"),
                "errorCodes": [
                    str(item).strip()
                    for item in (row.get("errorCodes") or [])
                    if str(item).strip()
                ],
            }
        )
    return out


def _build_user_phase_timeline(phase_rollup_summary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in phase_rollup_summary:
        if not isinstance(row, dict):
            continue
        phase_no = _safe_int(row.get("phaseNo"), default=0)
        if phase_no <= 0:
            continue
        pro_score = round(_clamp_score(_safe_float(row.get("proScore"), default=50.0)), 2)
        con_score = round(_clamp_score(_safe_float(row.get("conScore"), default=50.0)), 2)
        winner_hint = str(row.get("winnerHint") or "").strip().lower()
        if winner_hint not in {"pro", "con", "draw"}:
            winner_hint = _resolve_winner(pro_score, con_score, margin=0.6)
        error_codes = (
            [
                str(item).strip()
                for item in (row.get("errorCodes") or [])
                if str(item).strip()
            ]
            if isinstance(row.get("errorCodes"), list)
            else []
        )
        message_start_id = _safe_int(row.get("messageStartId"), default=0)
        message_end_id = _safe_int(row.get("messageEndId"), default=0)
        rows.append(
            {
                "phaseNo": phase_no,
                "winnerHint": winner_hint,
                "scoreCard": {
                    "proScore": pro_score,
                    "conScore": con_score,
                    "scoreGap": round(abs(pro_score - con_score), 2),
                },
                "messageRange": {
                    "startId": message_start_id if message_start_id > 0 else None,
                    "endId": message_end_id if message_end_id > 0 else None,
                    "count": max(0, _safe_int(row.get("messageCount"), default=0)),
                },
                "degradationLevel": max(0, _safe_int(row.get("degradationLevel"), default=0)),
                "errorCodes": error_codes,
            }
        )
    rows.sort(key=lambda item: int(item.get("phaseNo") or 0))
    return rows[:24]


def _collect_claim_hits_by_evidence(
    claim_graph: dict[str, Any],
) -> tuple[dict[str, int], dict[str, list[str]]]:
    hit_counts: dict[str, int] = {}
    claim_ids_by_evidence: dict[str, list[str]] = {}
    nodes = claim_graph.get("nodes") if isinstance(claim_graph.get("nodes"), list) else []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        claim_id = str(node.get("claimId") or "").strip()
        ref_ids = node.get("evidenceRefIds") if isinstance(node.get("evidenceRefIds"), list) else []
        seen_ref_ids: set[str] = set()
        for raw_ref_id in ref_ids:
            evidence_id = str(raw_ref_id or "").strip()
            if not evidence_id or evidence_id in seen_ref_ids:
                continue
            seen_ref_ids.add(evidence_id)
            hit_counts[evidence_id] = int(hit_counts.get(evidence_id, 0)) + 1
            if claim_id:
                claim_ids = claim_ids_by_evidence.setdefault(evidence_id, [])
                if claim_id not in claim_ids and len(claim_ids) < 5:
                    claim_ids.append(claim_id)
    return hit_counts, claim_ids_by_evidence


def _build_user_evidence_cards(
    *,
    verdict_evidence_refs: list[dict[str, Any]],
    evidence_ledger: dict[str, Any],
    claim_graph: dict[str, Any],
) -> list[dict[str, Any]]:
    entries = evidence_ledger.get("entries") if isinstance(evidence_ledger.get("entries"), list) else []
    entry_by_id: dict[str, dict[str, Any]] = {}
    for row in entries:
        if not isinstance(row, dict):
            continue
        evidence_id = str(row.get("evidenceId") or "").strip()
        if evidence_id and evidence_id not in entry_by_id:
            entry_by_id[evidence_id] = row

    citations = (
        evidence_ledger.get("sourceCitations")
        if isinstance(evidence_ledger.get("sourceCitations"), list)
        else []
    )
    citation_by_evidence_id: dict[str, dict[str, Any]] = {}
    for row in citations:
        if not isinstance(row, dict):
            continue
        evidence_id = str(row.get("evidenceId") or "").strip()
        if evidence_id and evidence_id not in citation_by_evidence_id:
            citation_by_evidence_id[evidence_id] = row

    claim_hit_counts, claim_ids_by_evidence = _collect_claim_hits_by_evidence(claim_graph)
    cards: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in verdict_evidence_refs:
        if not isinstance(row, dict):
            continue
        evidence_id = str(row.get("evidenceId") or "").strip()
        if not evidence_id or evidence_id in seen:
            continue
        seen.add(evidence_id)
        entry = entry_by_id.get(evidence_id, {})
        locator = entry.get("locator") if isinstance(entry.get("locator"), dict) else {}
        citation = citation_by_evidence_id.get(evidence_id, {})
        side = str(row.get("side") or entry.get("side") or "unknown").strip().lower()
        if side not in {"pro", "con"}:
            side = "unknown"
        phase_no = _safe_int(
            row.get("phaseNo"),
            default=_safe_int(entry.get("phaseNo"), default=0),
        )
        evidence_type = str(row.get("type") or entry.get("kind") or "").strip() or "unknown"
        reason = str(row.get("reason") or "").strip()
        if not reason:
            reason_hints = entry.get("reasonHints") if isinstance(entry.get("reasonHints"), list) else []
            reason = str(reason_hints[0]).strip() if reason_hints else ""
        reliability_label = str(entry.get("reliabilityLabel") or "").strip() or "unknown"
        conflict = bool(entry.get("conflict"))
        chunk_id = str(locator.get("chunkId") or row.get("chunkId") or "").strip() or None
        source_url = str(citation.get("sourceUrl") or locator.get("sourceUrl") or "").strip() or None
        source_title = str(citation.get("title") or locator.get("title") or "").strip() or None
        source_score_raw = citation.get("score") if isinstance(citation, dict) else locator.get("score")
        source_score = (
            round(_safe_float(source_score_raw, default=0.0), 4)
            if source_score_raw is not None
            else None
        )
        claim_hit_count = int(claim_hit_counts.get(evidence_id, 0))
        linked_claim_ids = list(claim_ids_by_evidence.get(evidence_id, []))
        cards.append(
            {
                "evidenceId": evidence_id,
                "phaseNo": phase_no if phase_no > 0 else None,
                "side": side,
                "evidenceType": evidence_type,
                "reason": reason or None,
                "reliabilityLabel": reliability_label,
                "conflict": conflict,
                "messageId": locator.get("messageId"),
                "chunkId": chunk_id,
                "sourceUrl": source_url,
                "sourceTitle": source_title,
                "sourceScore": source_score,
                "claimHitCount": claim_hit_count,
                "claimIds": linked_claim_ids,
                "explanation": (
                    f"phase={phase_no if phase_no > 0 else 'unknown'}, "
                    f"side={side}, type={evidence_type}, reliability={reliability_label}, "
                    f"conflict={str(conflict).lower()}, linkedClaims={claim_hit_count}"
                ),
            }
        )
        if len(cards) >= 12:
            break
    return cards


def _build_claim_verdict(
    *,
    winner: str,
    claim_graph_summary: dict[str, Any],
) -> dict[str, Any]:
    core_claims = (
        claim_graph_summary.get("coreClaims")
        if isinstance(claim_graph_summary.get("coreClaims"), dict)
        else {}
    )
    pro_claims = core_claims.get("pro") if isinstance(core_claims.get("pro"), list) else []
    con_claims = core_claims.get("con") if isinstance(core_claims.get("con"), list) else []

    def _normalize_claims(rows: list[Any], *, side: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in rows[:6]:
            if not isinstance(row, dict):
                continue
            out.append(
                {
                    "claimId": row.get("claimId"),
                    "side": side,
                    "text": row.get("text"),
                    "phaseFirstNo": row.get("phaseFirstNo"),
                    "supportCount": row.get("supportCount"),
                    "evidenceRefCount": row.get("evidenceRefCount"),
                }
            )
        return out

    if winner == "pro":
        accepted_claims = _normalize_claims(pro_claims, side="pro")
        rejected_claims = _normalize_claims(con_claims, side="con")
    elif winner == "con":
        accepted_claims = _normalize_claims(con_claims, side="con")
        rejected_claims = _normalize_claims(pro_claims, side="pro")
    else:
        # 平局场景下保留双方主张，避免强行给出“被否决”解释。
        accepted_claims = _normalize_claims(pro_claims[:3], side="pro") + _normalize_claims(
            con_claims[:3], side="con"
        )
        rejected_claims = []

    unresolved = (
        claim_graph_summary.get("unansweredClaims")
        if isinstance(claim_graph_summary.get("unansweredClaims"), list)
        else []
    )
    unresolved_claims: list[dict[str, Any]] = []
    for row in unresolved[:8]:
        if not isinstance(row, dict):
            continue
        unresolved_claims.append(
            {
                "claimId": row.get("claimId"),
                "side": row.get("side"),
                "text": row.get("text"),
                "phaseFirstNo": row.get("phaseFirstNo"),
            }
        )
    return {
        "acceptedClaims": accepted_claims,
        "rejectedClaims": rejected_claims,
        "unresolvedClaims": unresolved_claims,
    }


def _build_verdict_ledger(
    *,
    winner: str,
    pro_score: float,
    con_score: float,
    dimension_scores: dict[str, Any],
    panel_judges: dict[str, Any],
    panel_runtime_profiles: dict[str, Any],
    winner_first: str,
    winner_second: str,
    winner_third: str,
    winner_before_fairness_gate: str,
    review_required: bool,
    rejudge_triggered: bool,
    needs_draw_vote: bool,
    fairness_summary: dict[str, Any],
    fairness_error_codes: list[str],
    error_codes: list[str],
    claim_graph_summary: dict[str, Any],
    phase_rollup_summary: list[dict[str, Any]],
    verdict_evidence_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    panel_decisions_payload = (
        panel_judges if isinstance(panel_judges, dict) else {}
    )
    panel_disagreement = {
        "high": bool(fairness_summary.get("panelHighDisagreement")),
        "ratio": _safe_float(fairness_summary.get("panelDisagreementRatio"), default=0.0),
        "ratioMax": _safe_float(fairness_summary.get("panelDisagreementRatioMax"), default=0.2),
        "majorityWinner": str(fairness_summary.get("panelMajorityWinner") or "").strip().lower()
        or None,
        "reasons": [
            str(item).strip()
            for item in (fairness_summary.get("panelDisagreementReasons") or [])
            if str(item).strip()
        ],
    }
    panel_decisions = {
        "probeWinners": {
            "agent3Weighted": winner_first,
            "agent2Path": winner_second,
            "agent1Dimensions": winner_third,
        },
        "judges": panel_decisions_payload,
        "runtimeProfiles": (
            dict(panel_runtime_profiles)
            if isinstance(panel_runtime_profiles, dict)
            else {}
        ),
        "panelDisagreement": panel_disagreement,
        "panelHighDisagreement": panel_disagreement["high"],
        "scoreGap": _score_gap(pro_score, con_score),
        "phaseCountUsed": len(phase_rollup_summary),
    }
    arbitration = {
        "chainVersion": "v1-panel-fairness-arbiter",
        "decisionPath": [
            "judge_panel",
            "fairness_sentinel",
            "chief_arbiter",
        ],
        "fairnessGateApplied": True,
        "winnerBeforeFairnessGate": winner_before_fairness_gate,
        "winnerAfterArbitration": winner,
        "gateDecision": (
            "blocked_to_draw"
            if review_required and winner == "draw"
            else "pass_through"
        ),
        "reviewRequired": review_required,
        "fairnessReviewRequired": bool(fairness_summary.get("reviewRequired")),
        "gateLockedToDraw": bool(review_required and winner == "draw"),
        "rejudgeTriggered": rejudge_triggered,
        "needsDrawVote": needs_draw_vote,
        "fairnessErrorCodes": [
            str(code).strip()
            for code in fairness_error_codes
            if str(code).strip()
        ],
        "errorCodes": [str(code).strip() for code in error_codes if str(code).strip()],
    }
    return {
        "version": "v3-panel-independence",
        "winner": winner,
        "scoreCard": {
            "proScore": round(_clamp_score(pro_score), 2),
            "conScore": round(_clamp_score(con_score), 2),
            "dimensionScores": dict(dimension_scores),
        },
        "panelDecisions": panel_decisions,
        "arbitration": arbitration,
        "claimVerdict": _build_claim_verdict(winner=winner, claim_graph_summary=claim_graph_summary),
        "pivotalMoments": _collect_pivotal_moments(phase_rollup_summary),
        "decisiveEvidenceRefs": [
            dict(row) for row in verdict_evidence_refs[:8] if isinstance(row, dict)
        ],
        "fairnessSummary": fairness_summary if isinstance(fairness_summary, dict) else {},
    }


def _build_opinion_pack(
    *,
    winner: str,
    pro_score: float,
    con_score: float,
    debate_summary: str,
    side_analysis: dict[str, Any],
    verdict_reason: str,
    verdict_ledger: dict[str, Any],
    fairness_summary: dict[str, Any],
    audit_alerts: list[dict[str, Any]],
    error_codes: list[str],
    degradation_level: int,
    review_required: bool,
    needs_draw_vote: bool,
    trace_id: str,
    phase_rollup_summary: list[dict[str, Any]],
    verdict_evidence_refs: list[dict[str, Any]],
    claim_graph: dict[str, Any],
    claim_graph_summary: dict[str, Any],
    evidence_ledger: dict[str, Any],
    panel_judges: dict[str, Any],
) -> dict[str, Any]:
    alert_types: list[str] = []
    for row in audit_alerts:
        if not isinstance(row, dict):
            continue
        token = str(row.get("type") or "").strip()
        if token and token not in alert_types:
            alert_types.append(token)
    decisive_evidence_refs = (
        verdict_ledger.get("decisiveEvidenceRefs")
        if isinstance(verdict_ledger.get("decisiveEvidenceRefs"), list)
        else []
    )
    if not decisive_evidence_refs:
        decisive_evidence_refs = [
            dict(row) for row in verdict_evidence_refs if isinstance(row, dict)
        ]
    phase_debate_timeline = _build_user_phase_timeline(phase_rollup_summary)
    evidence_insight_cards = _build_user_evidence_cards(
        verdict_evidence_refs=[
            dict(row) for row in decisive_evidence_refs if isinstance(row, dict)
        ],
        evidence_ledger=evidence_ledger if isinstance(evidence_ledger, dict) else {},
        claim_graph=claim_graph if isinstance(claim_graph, dict) else {},
    )
    return {
        "version": "v3-opinion-pack",
        "userReport": {
            "winner": winner,
            "debateSummary": debate_summary,
            "sideAnalysis": side_analysis if isinstance(side_analysis, dict) else {},
            "verdictReason": verdict_reason,
            "scoreCard": {
                "proScore": round(_clamp_score(pro_score), 2),
                "conScore": round(_clamp_score(con_score), 2),
            },
            "phaseDebateTimeline": phase_debate_timeline,
            "evidenceInsightCards": evidence_insight_cards,
        },
        "opsSummary": {
            "reviewRequired": review_required,
            "needsDrawVote": needs_draw_vote,
            "degradationLevel": int(degradation_level),
            "errorCodes": [str(code).strip() for code in error_codes if str(code).strip()],
            "auditAlertTypes": alert_types,
        },
        "internalReview": {
            "traceId": trace_id,
            "fairnessSummary": fairness_summary if isinstance(fairness_summary, dict) else {},
            "panelJudges": panel_judges if isinstance(panel_judges, dict) else {},
            "claimStats": (
                claim_graph_summary.get("stats")
                if isinstance(claim_graph_summary.get("stats"), dict)
                else {}
            ),
            "evidenceStats": (
                evidence_ledger.get("stats") if isinstance(evidence_ledger.get("stats"), dict) else {}
            ),
        },
        "pivotalMoments": (
            verdict_ledger.get("pivotalMoments")
            if isinstance(verdict_ledger.get("pivotalMoments"), list)
            else []
        ),
        "decisiveEvidenceRefs": (
            [dict(row) for row in decisive_evidence_refs if isinstance(row, dict)]
        ),
    }


def _evaluate_fairness_gate(
    *,
    winner_first: str,
    winner_second: str,
    panel_judges: dict[str, Any],
    panel_runtime_profiles: dict[str, Any] | None,
    winner_before_gate: str,
    pro_score: float,
    con_score: float,
    phase_count_used: int,
    verdict_evidence_refs: list[dict[str, Any]],
    evidence_ledger: dict[str, Any],
    fairness_thresholds: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str], bool]:
    # phase2 继续复用轻量探针：双路裁决 + 风格探针 + 第三路 panel 分歧检查，保持实现可解释且可回放。
    swap_instability = (
        winner_first in {"pro", "con"}
        and winner_second in {"pro", "con"}
        and winner_first != winner_second
    )
    style_probe_winners = _build_style_probe_winners(pro_score=pro_score, con_score=con_score)
    style_shift_instability = (
        phase_count_used > 0
        and winner_before_gate in {"pro", "con"}
        and len(set(style_probe_winners.values())) > 1
    )
    score_gap = _score_gap(pro_score, con_score)
    normalized_panel_judges = panel_judges if isinstance(panel_judges, dict) else {}
    panel_probe_winners = {
        "agent3Weighted": str(
            (
                normalized_panel_judges.get("judgeA", {})
                if isinstance(normalized_panel_judges.get("judgeA"), dict)
                else {}
            ).get("winner")
            or winner_first
        ).strip().lower(),
        "agent2Path": str(
            (
                normalized_panel_judges.get("judgeB", {})
                if isinstance(normalized_panel_judges.get("judgeB"), dict)
                else {}
            ).get("winner")
            or winner_second
        ).strip().lower(),
        "agent1Dimensions": str(
            (
                normalized_panel_judges.get("judgeC", {})
                if isinstance(normalized_panel_judges.get("judgeC"), dict)
                else {}
            ).get("winner")
            or "draw"
        ).strip().lower(),
    }
    normalized_panel_runtime_profiles = (
        panel_runtime_profiles if isinstance(panel_runtime_profiles, dict) else {}
    )
    panel_vote_by_side = {
        "pro": 0,
        "con": 0,
    }
    for judge in normalized_panel_judges.values():
        if not isinstance(judge, dict):
            continue
        vote = str(judge.get("winner") or "").strip().lower()
        if vote in panel_vote_by_side:
            panel_vote_by_side[vote] += 1
    panel_vote_count = int(panel_vote_by_side["pro"] + panel_vote_by_side["con"])
    panel_majority_votes = max(panel_vote_by_side["pro"], panel_vote_by_side["con"])
    panel_majority_winner = (
        "pro"
        if panel_vote_by_side["pro"] > panel_vote_by_side["con"]
        else ("con" if panel_vote_by_side["con"] > panel_vote_by_side["pro"] else None)
    )
    panel_disagreement_ratio = (
        round(1.0 - (panel_majority_votes / float(panel_vote_count)), 4)
        if panel_vote_count > 0
        else 0.0
    )
    panel_disagreement_ratio_max = max(
        0.0,
        min(
            1.0,
            _safe_float(
                (fairness_thresholds or {}).get("panelDisagreementRatioMax")
                if isinstance(fairness_thresholds, dict)
                else None,
                default=0.2,
            ),
        ),
    )
    panel_high_disagreement = (
        phase_count_used > 0
        and panel_vote_count >= 2
        and panel_disagreement_ratio >= panel_disagreement_ratio_max
    )
    panel_disagreement_reasons: list[str] = []
    if panel_high_disagreement:
        panel_disagreement_reasons.append("panel_vote_split")
        if panel_majority_winner is None:
            panel_disagreement_reasons.append("no_majority_winner")
        if panel_vote_by_side["pro"] > 0 and panel_vote_by_side["con"] > 0:
            panel_disagreement_reasons.append("cross_side_conflict")

    def _normalize_reliability_counts(raw: Any) -> dict[str, int]:
        payload = raw if isinstance(raw, dict) else {}
        out: dict[str, int] = {}
        for key in ("high", "medium", "low", "unknown"):
            out[key] = max(0, _safe_int(payload.get(key), default=0))
        return out

    threshold_source = fairness_thresholds if isinstance(fairness_thresholds, dict) else {}
    evidence_min_total_refs = max(
        0,
        _safe_int(threshold_source.get("evidenceMinTotalRefs"), default=4),
    )
    evidence_min_decisive_refs = max(
        0,
        _safe_int(threshold_source.get("evidenceMinDecisiveRefs"), default=2),
    )
    evidence_min_winner_refs = max(
        0,
        _safe_int(threshold_source.get("evidenceMinWinnerSupportRefs"), default=1),
    )
    evidence_conflict_ratio_max = max(
        0.0,
        min(
            1.0,
            _safe_float(threshold_source.get("evidenceConflictRatioMax"), default=0.65),
        ),
    )
    evidence_max_low_reliability_ratio = max(
        0.0,
        min(
            1.0,
            _safe_float(
                threshold_source.get("evidenceMaxLowReliabilityRatio"),
                default=0.5,
            ),
        ),
    )
    evidence_stats = (
        evidence_ledger.get("stats") if isinstance(evidence_ledger.get("stats"), dict) else {}
    )
    evidence_total_entries = _safe_int(
        evidence_stats.get("totalEntries"),
        default=len(
            evidence_ledger.get("entries")
            if isinstance(evidence_ledger.get("entries"), list)
            else []
        ),
    )
    evidence_conflict_sources = _safe_int(
        evidence_stats.get("conflictSourceCount"),
        default=0,
    )
    reliability_counts = _normalize_reliability_counts(
        evidence_stats.get("reliabilityCounts")
    )
    verdict_reliability_counts = _normalize_reliability_counts(
        evidence_stats.get("verdictReferencedReliabilityCounts")
    )
    conflict_reason_counts = (
        {
            str(key).strip(): max(0, _safe_int(value, default=0))
            for key, value in evidence_stats.get("conflictReasonCounts").items()
            if str(key).strip()
        }
        if isinstance(evidence_stats.get("conflictReasonCounts"), dict)
        else {}
    )
    decisive_ref_count = len([row for row in verdict_evidence_refs if isinstance(row, dict)])
    verdict_referenced_count = max(
        0,
        _safe_int(evidence_stats.get("verdictReferencedCount"), default=decisive_ref_count),
    )
    if verdict_referenced_count <= 0 and decisive_ref_count > 0:
        verdict_referenced_count = decisive_ref_count
    low_reliability_ref_count = max(0, _safe_int(verdict_reliability_counts.get("low"), default=0))
    evidence_low_reliability_ratio = (
        round(low_reliability_ref_count / float(max(1, verdict_referenced_count)), 4)
        if verdict_referenced_count > 0
        else 0.0
    )
    winner_support_ref_count = len(
        [
            row
            for row in verdict_evidence_refs
            if isinstance(row, dict)
            and str(row.get("side") or "").strip().lower() == str(winner_before_gate or "").strip().lower()
        ]
    )
    evidence_conflict_ratio = (
        round(evidence_conflict_sources / float(max(1, evidence_total_entries)), 4)
        if evidence_total_entries > 0
        else 0.0
    )
    evidence_check_applied = phase_count_used > 0
    evidence_sufficiency_passed = (
        (not evidence_check_applied)
        or (
            evidence_total_entries >= evidence_min_total_refs
            and decisive_ref_count >= evidence_min_decisive_refs
            and (
                winner_before_gate not in {"pro", "con"}
                or winner_support_ref_count >= evidence_min_winner_refs
            )
            and evidence_conflict_ratio <= evidence_conflict_ratio_max
        )
    )
    evidence_conflict_ratio_high = (
        evidence_check_applied
        and evidence_total_entries > 0
        and evidence_conflict_ratio > evidence_conflict_ratio_max
    )
    evidence_low_reliability_ratio_high = (
        evidence_check_applied
        and verdict_referenced_count > 0
        and evidence_low_reliability_ratio > evidence_max_low_reliability_ratio
    )

    alerts: list[dict[str, Any]] = []
    error_codes: list[str] = []

    if swap_instability:
        error_codes.append("label_swap_instability")
        alerts.append(
            {
                "type": "label_swap_instability",
                "severity": "critical",
                "message": "first/second winner mismatch indicates potential label sensitivity",
                "details": {
                    "winnerFirst": winner_first,
                    "winnerSecond": winner_second,
                },
            }
        )
    if style_shift_instability:
        error_codes.append("style_shift_instability")
        alerts.append(
            {
                "type": "style_shift_instability",
                "severity": "warning",
                "message": "winner changes across style probes near score boundary",
                "details": {
                    "scoreGap": score_gap,
                    "styleProbeWinners": style_probe_winners,
                },
            }
        )
    if panel_high_disagreement:
        error_codes.append("judge_panel_high_disagreement")
        alerts.append(
            {
                "type": "judge_panel_high_disagreement",
                "severity": "critical",
                "message": "independent panel probes disagree on winner side",
                "details": {
                    "panelProbeWinners": panel_probe_winners,
                    "panelVoteBySide": panel_vote_by_side,
                    "panelDisagreementRatio": panel_disagreement_ratio,
                    "panelDisagreementRatioMax": panel_disagreement_ratio_max,
                    "panelDisagreementReasons": panel_disagreement_reasons,
                    "panelRuntimeProfiles": normalized_panel_runtime_profiles,
                },
            }
        )
    if not evidence_sufficiency_passed:
        error_codes.append("evidence_support_too_low")
        alerts.append(
            {
                "type": "evidence_support_too_low",
                "severity": "critical",
                "message": "evidence support is insufficient for reliable auto verdict",
                "details": {
                    "winnerBeforeGate": winner_before_gate,
                    "totalEntries": evidence_total_entries,
                    "decisiveRefCount": decisive_ref_count,
                    "winnerSupportRefCount": winner_support_ref_count,
                    "conflictSourceCount": evidence_conflict_sources,
                    "conflictRatio": evidence_conflict_ratio,
                    "lowReliabilityRefCount": low_reliability_ref_count,
                    "verdictReferencedCount": verdict_referenced_count,
                    "lowReliabilityRatio": evidence_low_reliability_ratio,
                    "thresholds": {
                        "minTotalRefs": evidence_min_total_refs,
                        "minDecisiveRefs": evidence_min_decisive_refs,
                        "minWinnerSupportRefs": evidence_min_winner_refs,
                        "maxConflictRatio": evidence_conflict_ratio_max,
                        "maxLowReliabilityRatio": evidence_max_low_reliability_ratio,
                    },
                },
            }
        )
    if evidence_conflict_ratio_high:
        error_codes.append("evidence_conflict_ratio_high")
        alerts.append(
            {
                "type": "evidence_conflict_ratio_high",
                "severity": "warning",
                "message": "conflicting evidence ratio exceeds configured threshold",
                "details": {
                    "conflictRatio": evidence_conflict_ratio,
                    "maxConflictRatio": evidence_conflict_ratio_max,
                    "conflictSourceCount": evidence_conflict_sources,
                    "totalEntries": evidence_total_entries,
                },
            }
        )
    if evidence_low_reliability_ratio_high:
        error_codes.append("evidence_reliability_too_low")
        alerts.append(
            {
                "type": "evidence_reliability_too_low",
                "severity": "critical",
                "message": "low-reliability evidence dominates decisive references",
                "details": {
                    "lowReliabilityRefCount": low_reliability_ref_count,
                    "verdictReferencedCount": verdict_referenced_count,
                    "lowReliabilityRatio": evidence_low_reliability_ratio,
                    "maxLowReliabilityRatio": evidence_max_low_reliability_ratio,
                    "verdictReferencedReliabilityCounts": verdict_reliability_counts,
                },
            }
        )

    review_required = bool(error_codes)
    review_reason_codes: list[str] = []
    seen_reason_codes: set[str] = set()
    for code in error_codes:
        token = str(code).strip()
        if token and token not in seen_reason_codes:
            review_reason_codes.append(token)
            seen_reason_codes.add(token)
    gate_decision = "blocked_to_draw" if review_required else "pass_through"
    summary = {
        "phase": "phase2",
        "gateDecision": gate_decision,
        "reviewReasons": review_reason_codes,
        "swapInstability": swap_instability,
        "styleShiftInstability": style_shift_instability,
        "panelHighDisagreement": panel_high_disagreement,
        "panelDisagreementRatio": panel_disagreement_ratio,
        "panelDisagreementRatioMax": panel_disagreement_ratio_max,
        "panelVoteBySide": panel_vote_by_side,
        "panelVoteCount": panel_vote_count,
        "panelMajorityWinner": panel_majority_winner,
        "panelDisagreementReasons": panel_disagreement_reasons,
        "evidenceSufficiencyPassed": evidence_sufficiency_passed,
        "evidenceConflictRatioHigh": evidence_conflict_ratio_high,
        "evidenceLowReliabilityRatioHigh": evidence_low_reliability_ratio_high,
        "scoreGap": score_gap,
        "styleProbeWinners": style_probe_winners,
        "panelProbeWinners": panel_probe_winners,
        "panelJudges": normalized_panel_judges,
        "panelRuntimeProfiles": normalized_panel_runtime_profiles,
        "evidenceSufficiency": {
            "checkApplied": evidence_check_applied,
            "winnerBeforeGate": winner_before_gate,
            "totalEntries": evidence_total_entries,
            "decisiveRefCount": decisive_ref_count,
            "winnerSupportRefCount": winner_support_ref_count,
            "verdictReferencedCount": verdict_referenced_count,
            "conflictSourceCount": evidence_conflict_sources,
            "conflictRatio": evidence_conflict_ratio,
            "lowReliabilityRefCount": low_reliability_ref_count,
            "lowReliabilityRatio": evidence_low_reliability_ratio,
            "reliabilityCounts": reliability_counts,
            "verdictReferencedReliabilityCounts": verdict_reliability_counts,
            "conflictReasonCounts": conflict_reason_counts,
            "thresholds": {
                "minTotalRefs": evidence_min_total_refs,
                "minDecisiveRefs": evidence_min_decisive_refs,
                "minWinnerSupportRefs": evidence_min_winner_refs,
                "maxConflictRatio": evidence_conflict_ratio_max,
                "maxLowReliabilityRatio": evidence_max_low_reliability_ratio,
            },
        },
        "reviewRequired": review_required,
    }
    return summary, alerts, error_codes, review_required


def _build_final_display_payload(
    *,
    style_mode: str,
    verdict_ledger: dict[str, Any],
    phase_count_used: int,
    phase_count_expected: int,
    missing_phase_nos: list[int],
) -> dict[str, Any]:
    score_card = (
        verdict_ledger.get("scoreCard")
        if isinstance(verdict_ledger.get("scoreCard"), dict)
        else {}
    )
    panel_decisions = (
        verdict_ledger.get("panelDecisions")
        if isinstance(verdict_ledger.get("panelDecisions"), dict)
        else {}
    )
    arbitration = (
        verdict_ledger.get("arbitration")
        if isinstance(verdict_ledger.get("arbitration"), dict)
        else {}
    )
    claim_verdict = (
        verdict_ledger.get("claimVerdict")
        if isinstance(verdict_ledger.get("claimVerdict"), dict)
        else {}
    )
    fairness_summary = (
        verdict_ledger.get("fairnessSummary")
        if isinstance(verdict_ledger.get("fairnessSummary"), dict)
        else {}
    )
    winner = str(verdict_ledger.get("winner") or "").strip().lower() or "draw"
    pro_score = _clamp_score(_safe_float(score_card.get("proScore"), default=50.0))
    con_score = _clamp_score(_safe_float(score_card.get("conScore"), default=50.0))
    probe_winners = (
        panel_decisions.get("probeWinners")
        if isinstance(panel_decisions.get("probeWinners"), dict)
        else {}
    )
    winner_first = str(probe_winners.get("agent3Weighted") or "").strip().lower() or "draw"
    winner_second = str(probe_winners.get("agent2Path") or "").strip().lower() or "draw"
    winner_third = str(probe_winners.get("agent1Dimensions") or "").strip().lower() or "draw"
    review_required = bool(arbitration.get("reviewRequired"))
    rejudge_triggered = bool(arbitration.get("rejudgeTriggered"))
    gate_decision = str(arbitration.get("gateDecision") or "").strip() or "pass_through"
    decision_path = (
        [
            str(item).strip()
            for item in (arbitration.get("decisionPath") or [])
            if str(item).strip()
        ]
        if isinstance(arbitration.get("decisionPath"), list)
        else []
    )
    if not decision_path:
        decision_path = ["judge_panel", "fairness_sentinel", "chief_arbiter"]
    decisive_evidence_refs = (
        verdict_ledger.get("decisiveEvidenceRefs")
        if isinstance(verdict_ledger.get("decisiveEvidenceRefs"), list)
        else []
    )
    accepted_claims = (
        claim_verdict.get("acceptedClaims")
        if isinstance(claim_verdict.get("acceptedClaims"), list)
        else []
    )
    rejected_claims = (
        claim_verdict.get("rejectedClaims")
        if isinstance(claim_verdict.get("rejectedClaims"), list)
        else []
    )
    unresolved_claims = (
        claim_verdict.get("unresolvedClaims")
        if isinstance(claim_verdict.get("unresolvedClaims"), list)
        else []
    )

    def _count_claims(rows: list[Any], *, side: str) -> int:
        return sum(
            1
            for row in rows
            if isinstance(row, dict) and str(row.get("side") or "").strip().lower() == side
        )

    pro_accepted = _count_claims(accepted_claims, side="pro")
    con_accepted = _count_claims(accepted_claims, side="con")
    pro_rejected = _count_claims(rejected_claims, side="pro")
    con_rejected = _count_claims(rejected_claims, side="con")
    unresolved_total = len([row for row in unresolved_claims if isinstance(row, dict)])

    panel_disagreement = (
        panel_decisions.get("panelDisagreement")
        if isinstance(panel_decisions.get("panelDisagreement"), dict)
        else {}
    )
    disagreement_ratio = _safe_float(panel_disagreement.get("ratio"), default=0.0)
    panel_majority_winner = (
        str(panel_disagreement.get("majorityWinner") or "").strip().lower() or None
    )
    evidence_sufficiency = (
        fairness_summary.get("evidenceSufficiency")
        if isinstance(fairness_summary.get("evidenceSufficiency"), dict)
        else {}
    )

    winner_label = _winner_label(winner)
    missing = ",".join(str(no) for no in missing_phase_nos) if missing_phase_nos else "none"
    normalized = str(style_mode or "").strip().lower()
    if normalized == "entertaining":
        debate_summary = (
            f"Final buzzer: {winner_label}. Scoreboard pro {round(pro_score, 2)} vs "
            f"con {round(con_score, 2)}, gate={gate_decision}, phases={phase_count_used}/{phase_count_expected}."
        )
    elif normalized == "mixed":
        debate_summary = (
            f"Final call: {winner_label}. Pro {round(pro_score, 2)} and con {round(con_score, 2)} "
            f"after {phase_count_used}/{phase_count_expected} phase(s), gate={gate_decision}."
        )
    else:
        normalized = "rational"
        debate_summary = (
            f"Final verdict: {winner_label}. Scores pro={round(pro_score, 2)}, con={round(con_score, 2)}; "
            f"arbitration gate={gate_decision}, missing phases={missing}."
        )
    side_analysis = {
        "pro": (
            f"Panel score pro={round(pro_score, 2)}; accepted claims={pro_accepted}, "
            f"rejected claims={pro_rejected}, unresolved={unresolved_total}."
        ),
        "con": (
            f"Panel score con={round(con_score, 2)}; accepted claims={con_accepted}, "
            f"rejected claims={con_rejected}, unresolved={unresolved_total}."
        ),
    }
    verdict_reason = (
        f"Decision path={' -> '.join(decision_path)}; probe winners "
        f"(a3={winner_first}, a2={winner_second}, a1={winner_third}); "
        f"majority={panel_majority_winner or 'none'}, disagreement={round(disagreement_ratio, 4)}, "
        f"gateDecision={gate_decision}, reviewRequired={str(review_required).lower()}, "
        f"rejudge={str(rejudge_triggered).lower()}, "
        f"decisiveEvidenceRefs={len([row for row in decisive_evidence_refs if isinstance(row, dict)])}, "
        f"evidenceSufficiencyPassed={str(bool(fairness_summary.get('evidenceSufficiencyPassed'))).lower()}, "
        f"winnerSupportRefs={_safe_int(evidence_sufficiency.get('winnerSupportRefCount'), default=0)}."
    )
    return {
        "styleMode": normalized,
        "debateSummary": debate_summary,
        "sideAnalysis": side_analysis,
        "verdictReason": verdict_reason,
        "factLock": {
            "winner": winner,
            "proScore": round(pro_score, 2),
            "conScore": round(con_score, 2),
            "phaseCountUsed": phase_count_used,
            "phaseCountExpected": phase_count_expected,
            "missingPhaseNos": list(missing_phase_nos),
            "decisionPath": decision_path,
            "gateDecision": gate_decision,
            "reviewRequired": review_required,
            "winnerFirst": winner_first,
            "winnerSecond": winner_second,
            "winnerThird": winner_third,
            "rejudgeTriggered": rejudge_triggered,
        },
    }


def validate_final_report_payload_contract(payload: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    winner = str(payload.get("winner") or "").strip().lower()
    if winner not in {"pro", "con", "draw"}:
        missing.append("winner")

    if not isinstance(payload.get("proScore"), (int, float)):
        missing.append("proScore")
    if not isinstance(payload.get("conScore"), (int, float)):
        missing.append("conScore")

    debate_summary = str(payload.get("debateSummary") or "").strip()
    if not debate_summary:
        missing.append("debateSummary")
    verdict_reason = str(payload.get("verdictReason") or "").strip()
    if not verdict_reason:
        missing.append("verdictReason")
    side_analysis = payload.get("sideAnalysis")
    if not isinstance(side_analysis, dict):
        missing.append("sideAnalysis")
    else:
        for side in ("pro", "con"):
            if not str(side_analysis.get(side) or "").strip():
                missing.append(f"sideAnalysis.{side}")

    dimension_scores = payload.get("dimensionScores")
    if not isinstance(dimension_scores, dict):
        missing.append("dimensionScores")
    else:
        for key in ("logic", "evidence", "rebuttal", "clarity"):
            if not isinstance(dimension_scores.get(key), (int, float)):
                missing.append(f"dimensionScores.{key}")

    verdict_refs = payload.get("verdictEvidenceRefs")
    if not isinstance(verdict_refs, list):
        missing.append("verdictEvidenceRefs")
        verdict_refs = []
    review_required = payload.get("reviewRequired")
    if not isinstance(review_required, bool):
        missing.append("reviewRequired")
    for key in ("phaseRollupSummary", "retrievalSnapshotRollup"):
        if not isinstance(payload.get(key), list):
            missing.append(key)

    evidence_ledger = payload.get("evidenceLedger")
    evidence_ids: set[str] = set()
    if not isinstance(evidence_ledger, dict):
        missing.append("evidenceLedger")
    else:
        entries = evidence_ledger.get("entries")
        if not isinstance(entries, list):
            missing.append("evidenceLedger.entries")
            entries = []
        refs_by_id = evidence_ledger.get("refsById")
        if not isinstance(refs_by_id, dict):
            missing.append("evidenceLedger.refsById")
        source_citations = evidence_ledger.get("sourceCitations")
        if not isinstance(source_citations, list):
            missing.append("evidenceLedger.sourceCitations")
        conflict_sources = evidence_ledger.get("conflictSources")
        if not isinstance(conflict_sources, list):
            missing.append("evidenceLedger.conflictSources")
        stats = evidence_ledger.get("stats")
        if not isinstance(stats, dict):
            missing.append("evidenceLedger.stats")
        else:
            for key in (
                "totalEntries",
                "messageRefCount",
                "sourceCitationCount",
                "conflictSourceCount",
                "verdictReferencedCount",
            ):
                if not isinstance(stats.get(key), (int, float)):
                    missing.append(f"evidenceLedger.stats.{key}")
        for row in entries:
            if not isinstance(row, dict):
                continue
            evidence_id = str(row.get("evidenceId") or "").strip()
            if evidence_id:
                evidence_ids.add(evidence_id)
    for row in verdict_refs:
        if not isinstance(row, dict):
            missing.append("verdictEvidenceRefs[]")
            continue
        evidence_id = str(row.get("evidenceId") or "").strip()
        if not evidence_id:
            missing.append("verdictEvidenceRefs.evidenceId")
            continue
        if evidence_id not in evidence_ids:
            missing.append("verdictEvidenceRefs.evidenceId_not_found")

    verdict_ledger = payload.get("verdictLedger")
    fairness_summary = payload.get("fairnessSummary")
    fairness_gate_decision: str | None = None
    fairness_review_reasons: list[str] | None = None
    if not isinstance(fairness_summary, dict):
        missing.append("fairnessSummary")
    else:
        if not isinstance(fairness_summary.get("reviewRequired"), bool):
            missing.append("fairnessSummary.reviewRequired")
        elif (
            isinstance(review_required, bool)
            and bool(fairness_summary.get("reviewRequired")) != review_required
        ):
            missing.append("fairnessSummary.reviewRequired_mismatch")

        fairness_gate_decision = (
            str(fairness_summary.get("gateDecision") or "").strip().lower() or None
        )
        if (
            fairness_gate_decision is not None
            and fairness_gate_decision not in _FINAL_ARBITRATION_GATE_DECISIONS
        ):
            missing.append("fairnessSummary.gateDecision_invalid")

        raw_review_reasons = fairness_summary.get("reviewReasons")
        if raw_review_reasons is None:
            fairness_review_reasons = None
        elif not isinstance(raw_review_reasons, list):
            missing.append("fairnessSummary.reviewReasons")
        else:
            fairness_review_reasons = []
            for row in raw_review_reasons:
                token = str(row).strip()
                if token:
                    fairness_review_reasons.append(token)
            if len(fairness_review_reasons) != len(raw_review_reasons):
                missing.append("fairnessSummary.reviewReasons.invalid_item")
    if not isinstance(verdict_ledger, dict):
        missing.append("verdictLedger")
    else:
        ledger_winner = str(verdict_ledger.get("winner") or "").strip().lower()
        if ledger_winner in {"pro", "con", "draw"} and ledger_winner != winner:
            missing.append("verdictLedger.winner_mismatch")
        if not isinstance(verdict_ledger.get("scoreCard"), dict):
            missing.append("verdictLedger.scoreCard")
        if not isinstance(verdict_ledger.get("panelDecisions"), dict):
            missing.append("verdictLedger.panelDecisions")
        if not isinstance(verdict_ledger.get("arbitration"), dict):
            missing.append("verdictLedger.arbitration")
        if not isinstance(verdict_ledger.get("pivotalMoments"), list):
            missing.append("verdictLedger.pivotalMoments")
        if not isinstance(verdict_ledger.get("decisiveEvidenceRefs"), list):
            missing.append("verdictLedger.decisiveEvidenceRefs")
        arbitration = (
            verdict_ledger.get("arbitration")
            if isinstance(verdict_ledger.get("arbitration"), dict)
            else {}
        )
        if not str(arbitration.get("chainVersion") or "").strip():
            missing.append("verdictLedger.arbitration.chainVersion")
        if not isinstance(arbitration.get("decisionPath"), list):
            missing.append("verdictLedger.arbitration.decisionPath")
        if not isinstance(arbitration.get("fairnessGateApplied"), bool):
            missing.append("verdictLedger.arbitration.fairnessGateApplied")
        gate_decision = str(arbitration.get("gateDecision") or "").strip().lower()
        if not gate_decision:
            missing.append("verdictLedger.arbitration.gateDecision")
        elif gate_decision not in _FINAL_ARBITRATION_GATE_DECISIONS:
            missing.append("verdictLedger.arbitration.gateDecision_invalid")
        if fairness_gate_decision is not None and gate_decision and fairness_gate_decision != gate_decision:
            missing.append("verdictLedger.arbitration.gateDecision_fairness_mismatch")
        arbitration_winner = str(arbitration.get("winnerAfterArbitration") or "").strip().lower()
        if arbitration_winner not in {"pro", "con", "draw"}:
            missing.append("verdictLedger.arbitration.winnerAfterArbitration")
        elif arbitration_winner != winner:
            missing.append("verdictLedger.arbitration.winnerAfterArbitration_mismatch")
        if not isinstance(arbitration.get("reviewRequired"), bool):
            missing.append("verdictLedger.arbitration.reviewRequired")
        elif isinstance(review_required, bool) and bool(arbitration.get("reviewRequired")) != review_required:
            missing.append("verdictLedger.arbitration.reviewRequired_mismatch")
        if (
            isinstance(arbitration.get("reviewRequired"), bool)
            and isinstance(fairness_summary, dict)
            and isinstance(fairness_summary.get("reviewRequired"), bool)
            and bool(arbitration.get("reviewRequired")) != bool(fairness_summary.get("reviewRequired"))
        ):
            missing.append("verdictLedger.arbitration.reviewRequired_fairness_mismatch")
        if (
            isinstance(arbitration.get("reviewRequired"), bool)
            and bool(arbitration.get("reviewRequired"))
            and winner != "draw"
        ):
            missing.append("verdictLedger.arbitration.reviewRequired_winner_not_draw")
        if isinstance(arbitration.get("reviewRequired"), bool):
            arbitration_review_required = bool(arbitration.get("reviewRequired"))
            if arbitration_review_required and gate_decision != "blocked_to_draw":
                missing.append("verdictLedger.arbitration.reviewRequired_gate_decision_invalid")
            if (not arbitration_review_required) and gate_decision == "blocked_to_draw":
                missing.append("verdictLedger.arbitration.pass_through_gate_decision_invalid")

    opinion_pack = payload.get("opinionPack")
    if not isinstance(opinion_pack, dict):
        missing.append("opinionPack")
    else:
        user_report = (
            opinion_pack.get("userReport")
            if isinstance(opinion_pack.get("userReport"), dict)
            else None
        )
        if user_report is None:
            missing.append("opinionPack.userReport")
        else:
            user_winner = str(user_report.get("winner") or "").strip().lower()
            if user_winner not in {"pro", "con", "draw"}:
                missing.append("opinionPack.userReport.winner")
            elif user_winner != winner:
                missing.append("opinionPack.userReport.winner_mismatch")
            if str(user_report.get("debateSummary") or "").strip() != debate_summary:
                missing.append("opinionPack.userReport.debateSummary_mismatch")
            user_side_analysis = user_report.get("sideAnalysis")
            if isinstance(user_side_analysis, dict) and user_side_analysis != side_analysis:
                missing.append("opinionPack.userReport.sideAnalysis_mismatch")
            user_verdict_reason = str(user_report.get("verdictReason") or "").strip()
            if user_verdict_reason and user_verdict_reason != verdict_reason:
                missing.append("opinionPack.userReport.verdictReason_mismatch")
            if not isinstance(user_report.get("phaseDebateTimeline"), list):
                missing.append("opinionPack.userReport.phaseDebateTimeline")
            if not isinstance(user_report.get("evidenceInsightCards"), list):
                missing.append("opinionPack.userReport.evidenceInsightCards")
        if not isinstance(opinion_pack.get("opsSummary"), dict):
            missing.append("opinionPack.opsSummary")
        if not isinstance(opinion_pack.get("internalReview"), dict):
            missing.append("opinionPack.internalReview")

    winner_first = str(payload.get("winnerFirst") or "").strip().lower()
    winner_second = str(payload.get("winnerSecond") or "").strip().lower()
    if winner_first not in {"pro", "con", "draw"}:
        missing.append("winnerFirst")
    if winner_second not in {"pro", "con", "draw"}:
        missing.append("winnerSecond")

    if not isinstance(payload.get("rejudgeTriggered"), bool):
        missing.append("rejudgeTriggered")
    if not isinstance(payload.get("needsDrawVote"), bool):
        missing.append("needsDrawVote")
    error_codes = payload.get("errorCodes")
    if not isinstance(error_codes, list):
        missing.append("errorCodes")
        error_codes = []
    normalized_error_codes = {str(item).strip() for item in error_codes if str(item).strip()}
    if not isinstance(payload.get("degradationLevel"), int):
        missing.append("degradationLevel")
    elif isinstance(review_required, bool) and review_required and int(payload.get("degradationLevel") or 0) <= 0:
        missing.append("degradationLevel.review_required_not_degraded")

    if isinstance(review_required, bool) and review_required:
        if "fairness_gate_review_required" not in normalized_error_codes:
            missing.append("errorCodes.fairness_gate_review_required_missing")
        if fairness_review_reasons is None:
            missing.append("fairnessSummary.reviewReasons")
        elif not fairness_review_reasons:
            missing.append("fairnessSummary.reviewReasons_empty")
    if isinstance(fairness_review_reasons, list):
        for code in fairness_review_reasons:
            if code not in normalized_error_codes:
                missing.append("fairnessSummary.reviewReasons_not_in_errorCodes")
                break

    claim_graph = payload.get("claimGraph")
    if not isinstance(claim_graph, dict):
        missing.append("claimGraph")
    else:
        if not isinstance(claim_graph.get("nodes"), list):
            missing.append("claimGraph.nodes")
        if not isinstance(claim_graph.get("edges"), list):
            missing.append("claimGraph.edges")
        if not isinstance(claim_graph.get("stats"), dict):
            missing.append("claimGraph.stats")

    claim_graph_summary = payload.get("claimGraphSummary")
    if not isinstance(claim_graph_summary, dict):
        missing.append("claimGraphSummary")
    else:
        if not isinstance(claim_graph_summary.get("coreClaims"), dict):
            missing.append("claimGraphSummary.coreClaims")
        if not isinstance(claim_graph_summary.get("stats"), dict):
            missing.append("claimGraphSummary.stats")

    judge_trace = payload.get("judgeTrace")
    if not isinstance(judge_trace, dict):
        missing.append("judgeTrace")
    else:
        trace_id = str(judge_trace.get("traceId") or "").strip()
        if not trace_id:
            missing.append("judgeTrace.traceId")
    return missing


def build_final_report_payload(
    *,
    request: FinalDispatchRequest,
    phase_receipts: list[Any],
    judge_style_mode: str,
    fairness_thresholds: dict[str, Any] | None = None,
    panel_runtime_profiles: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    expected_phase_nos = list(range(request.phase_start_no, request.phase_end_no + 1))
    expected_phase_set = set(expected_phase_nos)

    phase_reports_by_no: dict[int, tuple[datetime, dict[str, Any]]] = {}
    for receipt in phase_receipts:
        phase_no, report_payload = _extract_phase_report_payload_from_receipt(receipt)
        if phase_no not in expected_phase_set or not isinstance(report_payload, dict):
            continue
        updated_at = getattr(receipt, "updated_at", None)
        if not isinstance(updated_at, datetime):
            updated_at = datetime.min.replace(tzinfo=timezone.utc)
        prev = phase_reports_by_no.get(phase_no)
        if prev is not None and prev[0] >= updated_at:
            continue
        phase_reports_by_no[phase_no] = (updated_at, report_payload)

    used_phase_nos = sorted(phase_reports_by_no.keys())
    missing_phase_nos = [no for no in expected_phase_nos if no not in phase_reports_by_no]

    phase_rollup_summary: list[dict[str, Any]] = []
    retrieval_snapshot_rollup: list[dict[str, Any]] = []
    retrieval_seen: set[tuple[int, str, str]] = set()
    pro_agent3_scores: list[float] = []
    con_agent3_scores: list[float] = []
    pro_agent2_scores: list[float] = []
    con_agent2_scores: list[float] = []
    pro_dimensions_rows: list[dict[str, float]] = []
    con_dimensions_rows: list[dict[str, float]] = []
    verdict_evidence_refs: list[dict[str, Any]] = []
    score_evidence_rollup: list[dict[str, Any]] = []
    evidence_ledger_builder = EvidenceLedgerBuilder()

    for phase_no in used_phase_nos:
        payload = phase_reports_by_no[phase_no][1]
        agent3 = (
            payload.get("agent3WeightedScore")
            if isinstance(payload.get("agent3WeightedScore"), dict)
            else {}
        )
        agent2 = payload.get("agent2Score") if isinstance(payload.get("agent2Score"), dict) else {}

        pro_agent3 = _clamp_score(_safe_float(agent3.get("pro"), default=50.0))
        con_agent3 = _clamp_score(_safe_float(agent3.get("con"), default=50.0))
        pro_agent2 = _clamp_score(_safe_float(agent2.get("pro"), default=50.0))
        con_agent2 = _clamp_score(_safe_float(agent2.get("con"), default=50.0))
        pro_agent3_scores.append(pro_agent3)
        con_agent3_scores.append(con_agent3)
        pro_agent2_scores.append(pro_agent2)
        con_agent2_scores.append(con_agent2)
        pro_dimensions_rows.append(_extract_agent1_dimensions(payload, side="pro"))
        con_dimensions_rows.append(_extract_agent1_dimensions(payload, side="con"))
        hit_items = [item for item in (agent2.get("hitItems") or []) if str(item or "").strip()]
        miss_items = [item for item in (agent2.get("missItems") or []) if str(item or "").strip()]
        score_evidence_rollup.append(
            {
                "phaseNo": phase_no,
                "agent1Dimensions": {
                    "pro": _extract_agent1_dimensions(payload, side="pro"),
                    "con": _extract_agent1_dimensions(payload, side="con"),
                },
                "agent2": {
                    "proScore": round(pro_agent2, 2),
                    "conScore": round(con_agent2, 2),
                    "hitCount": len(hit_items),
                    "missCount": len(miss_items),
                },
            }
        )

        phase_rollup_summary.append(
            {
                "phaseNo": phase_no,
                "messageStartId": payload.get("messageStartId"),
                "messageEndId": payload.get("messageEndId"),
                "messageCount": payload.get("messageCount"),
                "proScore": round(pro_agent3, 2),
                "conScore": round(con_agent3, 2),
                "winnerHint": _resolve_winner(pro_agent3, con_agent3, margin=0.6),
                "errorCodes": payload.get("errorCodes") or [],
                "degradationLevel": int(payload.get("degradationLevel") or 0),
            }
        )

        agent1 = payload.get("agent1Score") if isinstance(payload.get("agent1Score"), dict) else {}
        refs = agent1.get("evidenceRefs") if isinstance(agent1.get("evidenceRefs"), dict) else {}
        retrieval_lookup = {
            "pro": _index_retrieval_items(payload, side="pro"),
            "con": _index_retrieval_items(payload, side="con"),
        }
        for side in ("pro", "con"):
            ref = refs.get(side) if isinstance(refs.get(side), dict) else {}
            for message_id in ref.get("messageIds") or []:
                if len(verdict_evidence_refs) >= 16:
                    break
                evidence_id = evidence_ledger_builder.register_message_ref(
                    phase_no=phase_no,
                    side=side,
                    message_id=message_id,
                    reason="agent1_evidence_ref",
                )
                if evidence_id is None:
                    continue
                evidence_ledger_builder.mark_verdict_referenced(evidence_id)
                verdict_evidence_refs.append(
                    {
                        "evidenceId": evidence_id,
                        "phaseNo": phase_no,
                        "side": side,
                        "type": "message",
                        "messageId": message_id,
                        "reason": "agent1_evidence_ref",
                    }
                )
            for chunk_id in ref.get("chunkIds") or []:
                if len(verdict_evidence_refs) >= 16:
                    break
                chunk_meta = retrieval_lookup.get(side, {}).get(str(chunk_id))
                evidence_id = evidence_ledger_builder.register_retrieval_chunk(
                    phase_no=phase_no,
                    side=side,
                    chunk_id=chunk_id,
                    reason="agent1_retrieval_ref",
                    source_url=(
                        chunk_meta.get("sourceUrl") or chunk_meta.get("source_url")
                        if isinstance(chunk_meta, dict)
                        else None
                    ),
                    title=chunk_meta.get("title") if isinstance(chunk_meta, dict) else None,
                    score=chunk_meta.get("score") if isinstance(chunk_meta, dict) else None,
                    conflict=chunk_meta.get("conflict") if isinstance(chunk_meta, dict) else False,
                )
                if evidence_id is None:
                    continue
                evidence_ledger_builder.mark_verdict_referenced(evidence_id)
                verdict_evidence_refs.append(
                    {
                        "evidenceId": evidence_id,
                        "phaseNo": phase_no,
                        "side": side,
                        "type": "retrieval_chunk",
                        "chunkId": chunk_id,
                        "reason": "agent1_retrieval_ref",
                    }
                )
        for ref_type, rows in (
            ("agent2_hit", agent2.get("hitItems") or []),
            ("agent2_miss", agent2.get("missItems") or []),
        ):
            for raw in rows:
                if len(verdict_evidence_refs) >= 16:
                    break
                side, content = _parse_agent2_ref_item(raw)
                if not content:
                    continue
                evidence_id = evidence_ledger_builder.register_agent2_path_item(
                    phase_no=phase_no,
                    side=side,
                    path_type=ref_type,
                    item=content,
                    reason="agent2_path_alignment",
                )
                if evidence_id is None:
                    continue
                evidence_ledger_builder.mark_verdict_referenced(evidence_id)
                verdict_evidence_refs.append(
                    {
                        "evidenceId": evidence_id,
                        "phaseNo": phase_no,
                        "side": side,
                        "type": ref_type,
                        "item": content,
                        "reason": "agent2_path_alignment",
                    }
                )

        for side, bundle_key in (("pro", "proRetrievalBundle"), ("con", "conRetrievalBundle")):
            bundle = payload.get(bundle_key) if isinstance(payload.get(bundle_key), dict) else {}
            for item in bundle.get("items") or []:
                if not isinstance(item, dict):
                    continue
                chunk_id = str(item.get("chunkId") or item.get("chunk_id") or "").strip()
                dedupe_key = (phase_no, side, chunk_id or str(item.get("sourceUrl") or ""))
                if dedupe_key in retrieval_seen:
                    continue
                retrieval_seen.add(dedupe_key)
                evidence_ledger_builder.register_retrieval_chunk(
                    phase_no=phase_no,
                    side=side,
                    chunk_id=chunk_id,
                    reason="retrieval_snapshot",
                    source_url=item.get("sourceUrl") or item.get("source_url"),
                    title=item.get("title"),
                    score=item.get("score"),
                    conflict=item.get("conflict"),
                )
                retrieval_snapshot_rollup.append(
                    {
                        "phaseNo": phase_no,
                        "side": side,
                        "chunkId": chunk_id or None,
                        "title": item.get("title"),
                        "sourceUrl": item.get("sourceUrl") or item.get("source_url"),
                        "score": _safe_float(item.get("score"), default=0.0),
                        "conflict": bool(item.get("conflict")),
                        "snippet": item.get("snippet"),
                    }
                )
                if len(retrieval_snapshot_rollup) >= 120:
                    break

    evidence_ledger = evidence_ledger_builder.build_payload()
    second_pro = 50.0
    second_con = 50.0
    pro_dimension_composite = 50.0
    con_dimension_composite = 50.0

    if phase_rollup_summary:
        pro_score = round(sum(pro_agent3_scores) / float(len(pro_agent3_scores)), 2)
        con_score = round(sum(con_agent3_scores) / float(len(con_agent3_scores)), 2)
        winner_first = _resolve_winner(pro_score, con_score, margin=0.8)
        second_pro = sum(pro_agent2_scores) / float(max(1, len(pro_agent2_scores)))
        second_con = sum(con_agent2_scores) / float(max(1, len(con_agent2_scores)))
        winner_second = _resolve_winner(second_pro, second_con, margin=0.8)

        def _avg_dim(rows: list[dict[str, float]], key: str, default: float = 50.0) -> float:
            if not rows:
                return default
            return sum(_safe_float(row.get(key), default=default) for row in rows) / float(
                len(rows)
            )

        pro_dimension_composite = _clamp_score(
            (
                _avg_dim(pro_dimensions_rows, "logic")
                + _avg_dim(pro_dimensions_rows, "evidence")
                + _avg_dim(pro_dimensions_rows, "rebuttal")
                + _avg_dim(pro_dimensions_rows, "clarity")
            )
            / 4.0
        )
        con_dimension_composite = _clamp_score(
            (
                _avg_dim(con_dimensions_rows, "logic")
                + _avg_dim(con_dimensions_rows, "evidence")
                + _avg_dim(con_dimensions_rows, "rebuttal")
                + _avg_dim(con_dimensions_rows, "clarity")
            )
            / 4.0
        )
        winner_third = _resolve_winner(
            pro_dimension_composite,
            con_dimension_composite,
            margin=0.8,
        )

        if winner_first in {"pro", "con"}:
            winner_side = winner_first
            dims_rows = pro_dimensions_rows if winner_side == "pro" else con_dimensions_rows
        else:
            dims_rows = pro_dimensions_rows + con_dimensions_rows

        dimension_scores = {
            "logic": round(_clamp_score(_avg_dim(dims_rows, "logic")), 2),
            "evidence": round(_clamp_score(_avg_dim(dims_rows, "evidence")), 2),
            "rebuttal": round(_clamp_score(_avg_dim(dims_rows, "rebuttal")), 2),
            "clarity": round(_clamp_score(_avg_dim(dims_rows, "clarity")), 2),
        }
    else:
        pro_score = 50.0
        con_score = 50.0
        winner_first = "draw"
        winner_second = "draw"
        winner_third = "draw"
        dimension_scores = {
            "logic": 50.0,
            "evidence": 50.0,
            "rebuttal": 50.0,
            "clarity": 50.0,
        }

    normalized_panel_runtime_profiles = _normalize_panel_runtime_profiles(panel_runtime_profiles)
    panel_judges = {
        "judgeA": _build_panel_judge_item(
            judge_id="judgeA",
            name="Weighted Score Judge",
            source="agent3WeightedScore",
            winner=winner_first,
            pro_score=pro_score,
            con_score=con_score,
            reason=(
                f"Aggregates phase weighted scores across {len(phase_rollup_summary)} phase(s). "
                f"Uses margin=0.8 winner rule."
            ),
            runtime_profile=normalized_panel_runtime_profiles.get("judgeA"),
        ),
        "judgeB": _build_panel_judge_item(
            judge_id="judgeB",
            name="Path Alignment Judge",
            source="agent2Score",
            winner=winner_second,
            pro_score=second_pro,
            con_score=second_con,
            reason=(
                "Uses agent2 hit/miss path alignment averages as an independent lane."
            ),
            runtime_profile=normalized_panel_runtime_profiles.get("judgeB"),
        ),
        "judgeC": _build_panel_judge_item(
            judge_id="judgeC",
            name="Dimension Composite Judge",
            source="agent1Dimensions",
            winner=winner_third,
            pro_score=pro_dimension_composite,
            con_score=con_dimension_composite,
            reason=(
                "Uses agent1 logic/evidence/rebuttal/clarity composite scores as an independent lane."
            ),
            runtime_profile=normalized_panel_runtime_profiles.get("judgeC"),
        ),
    }

    error_codes: list[str] = []
    if missing_phase_nos:
        error_codes.append("final_rollup_incomplete")
    if not phase_rollup_summary:
        error_codes.append("final_rollup_no_phase_payload")

    rejudge_triggered = False
    winner = winner_first
    if winner_first != winner_second:
        winner = "draw"
        rejudge_triggered = True
        error_codes.append("consistency_conflict")

    fairness_summary, fairness_alerts, fairness_error_codes, review_required = (
        _evaluate_fairness_gate(
            winner_first=winner_first,
            winner_second=winner_second,
            panel_judges=panel_judges,
            panel_runtime_profiles=normalized_panel_runtime_profiles,
            winner_before_gate=winner,
            pro_score=pro_score,
            con_score=con_score,
            phase_count_used=len(phase_rollup_summary),
            verdict_evidence_refs=verdict_evidence_refs,
            evidence_ledger=evidence_ledger,
            fairness_thresholds=fairness_thresholds,
        )
    )
    for code in fairness_error_codes:
        if code not in error_codes:
            error_codes.append(code)
    winner_before_fairness_gate = winner
    if review_required:
        if winner != "draw":
            winner = "draw"
            rejudge_triggered = True
        if "fairness_gate_review_required" not in error_codes:
            error_codes.append("fairness_gate_review_required")

    needs_draw_vote = winner == "draw"
    if not error_codes:
        degradation_level = 0
    elif phase_rollup_summary:
        degradation_level = 1
    else:
        degradation_level = 2

    if phase_rollup_summary:
        final_rationale_raw = (
            f"A9 final aggregated {len(phase_rollup_summary)} phases "
            f"(expected={len(expected_phase_nos)}), "
            f"agent3_avg: pro={pro_score}, con={con_score}, winner={winner}."
        )
    else:
        final_rationale_raw = (
            "A9 final aggregation fallback: no usable phase report payload was found "
            "in the requested phase range."
        )

    audit_alerts: list[dict[str, Any]] = []
    if missing_phase_nos:
        audit_alerts.append(
            {
                "type": "final_rollup_incomplete",
                "severity": "warning",
                "message": f"missing phase payloads: {missing_phase_nos}",
            }
        )
    audit_alerts.extend(fairness_alerts)

    final_style_mode, final_style_mode_source = resolve_effective_style_mode(
        "rational",
        judge_style_mode,
    )
    claim_graph_payload = build_claim_graph_payload(
        phase_payloads=[(phase_no, phase_reports_by_no[phase_no][1]) for phase_no in used_phase_nos],
        verdict_evidence_refs=verdict_evidence_refs,
        evidence_ref_resolver=lambda phase_no, side, message_ids, chunk_ids: (
            evidence_ledger_builder.resolve_reference_ids(
                phase_no=phase_no,
                side=side,
                message_ids=message_ids,
                chunk_ids=chunk_ids,
            )
        ),
    )
    claim_graph = (
        claim_graph_payload.get("claimGraph")
        if isinstance(claim_graph_payload.get("claimGraph"), dict)
        else {}
    )
    claim_graph_summary = (
        claim_graph_payload.get("claimGraphSummary")
        if isinstance(claim_graph_payload.get("claimGraphSummary"), dict)
        else {}
    )
    verdict_ledger = _build_verdict_ledger(
        winner=winner,
        pro_score=pro_score,
        con_score=con_score,
        dimension_scores=dimension_scores,
        panel_judges=panel_judges,
        panel_runtime_profiles=normalized_panel_runtime_profiles,
        winner_first=winner_first,
        winner_second=winner_second,
        winner_third=winner_third,
        winner_before_fairness_gate=winner_before_fairness_gate,
        review_required=review_required,
        rejudge_triggered=rejudge_triggered,
        needs_draw_vote=needs_draw_vote,
        fairness_summary=fairness_summary,
        fairness_error_codes=fairness_error_codes,
        error_codes=error_codes,
        claim_graph_summary=claim_graph_summary,
        phase_rollup_summary=phase_rollup_summary,
        verdict_evidence_refs=verdict_evidence_refs,
    )
    display_payload = _build_final_display_payload(
        style_mode=final_style_mode,
        verdict_ledger=verdict_ledger,
        phase_count_used=len(phase_rollup_summary),
        phase_count_expected=len(expected_phase_nos),
        missing_phase_nos=missing_phase_nos,
    )
    debate_summary = str(display_payload.get("debateSummary") or "").strip()
    side_analysis = (
        display_payload.get("sideAnalysis")
        if isinstance(display_payload.get("sideAnalysis"), dict)
        else {}
    )
    verdict_reason = str(display_payload.get("verdictReason") or final_rationale_raw)
    opinion_pack = _build_opinion_pack(
        winner=winner,
        pro_score=pro_score,
        con_score=con_score,
        debate_summary=debate_summary,
        side_analysis=side_analysis,
        verdict_reason=verdict_reason,
        verdict_ledger=verdict_ledger,
        fairness_summary=fairness_summary,
        audit_alerts=audit_alerts,
        error_codes=error_codes,
        degradation_level=degradation_level,
        review_required=review_required,
        needs_draw_vote=needs_draw_vote,
        trace_id=request.trace_id,
        phase_rollup_summary=phase_rollup_summary,
        verdict_evidence_refs=verdict_evidence_refs,
        claim_graph=claim_graph,
        claim_graph_summary=claim_graph_summary,
        evidence_ledger=evidence_ledger,
        panel_judges=panel_judges,
    )

    return {
        "sessionId": request.session_id,
        "winner": winner,
        "proScore": round(_clamp_score(pro_score), 2),
        "conScore": round(_clamp_score(con_score), 2),
        "dimensionScores": dimension_scores,
        "debateSummary": debate_summary,
        "sideAnalysis": side_analysis,
        "verdictReason": verdict_reason,
        "claimGraph": claim_graph,
        "claimGraphSummary": claim_graph_summary,
        "evidenceLedger": evidence_ledger,
        "verdictLedger": verdict_ledger,
        "opinionPack": opinion_pack,
        "verdictEvidenceRefs": verdict_evidence_refs[:16],
        "phaseRollupSummary": phase_rollup_summary,
        "retrievalSnapshotRollup": retrieval_snapshot_rollup,
        "winnerFirst": winner_first,
        "winnerSecond": winner_second,
        "winnerThird": winner_third,
        "rejudgeTriggered": rejudge_triggered,
        "needsDrawVote": needs_draw_vote,
        "reviewRequired": review_required,
        "judgeTrace": {
            "traceId": request.trace_id,
            "pipelineVersion": "v3-final-a9a10-rollup-v2",
            "idempotencyKey": request.idempotency_key,
            "phaseRange": {
                "startNo": request.phase_start_no,
                "endNo": request.phase_end_no,
            },
            "phaseCountExpected": len(expected_phase_nos),
            "phaseCountUsed": len(phase_rollup_summary),
            "phaseNosUsed": used_phase_nos,
            "missingPhaseNos": missing_phase_nos,
            "winnerFirst": winner_first,
            "winnerSecond": winner_second,
            "winnerThird": winner_third,
            "source": "phase_receipt_report_payload",
            "a9RationaleRaw": final_rationale_raw,
            "displayStyleMode": final_style_mode,
            "displayStyleModeSource": final_style_mode_source,
            "displayDebateSummary": debate_summary,
            "displayVerdictReason": verdict_reason,
            "factLock": display_payload.get("factLock"),
            "scoreEvidenceRollup": score_evidence_rollup,
            "claimGraphSummary": claim_graph_summary,
            "claimGraphStats": claim_graph.get("stats") if isinstance(claim_graph, dict) else {},
            "evidenceLedgerVersion": evidence_ledger.get("pipelineVersion"),
            "evidenceLedgerStats": evidence_ledger.get("stats")
            if isinstance(evidence_ledger.get("stats"), dict)
            else {},
            "panelArbiter": {
                "version": verdict_ledger.get("version"),
                "panelDecisions": (
                    verdict_ledger.get("panelDecisions")
                    if isinstance(verdict_ledger.get("panelDecisions"), dict)
                    else {}
                ),
                "runtimeProfiles": normalized_panel_runtime_profiles,
                "arbitration": (
                    verdict_ledger.get("arbitration")
                    if isinstance(verdict_ledger.get("arbitration"), dict)
                    else {}
                ),
                "nonBypassInvariant": {
                    # 当公平门禁要求人工复核时，Chief Arbiter 必须把终局锁到 draw，禁止直接终判到某一方。
                    "reviewRequiredImpliesDraw": (not review_required) or winner == "draw",
                    "arbitrationWinnerMatchesTopWinner": (
                        str(
                            (
                                verdict_ledger.get("arbitration")
                                if isinstance(verdict_ledger.get("arbitration"), dict)
                                else {}
                            ).get("winnerAfterArbitration")
                            or ""
                        ).strip().lower()
                        == str(winner or "").strip().lower()
                    ),
                    "fairnessReviewMatchesArbitration": (
                        bool(fairness_summary.get("reviewRequired"))
                        == bool(
                            (
                                verdict_ledger.get("arbitration")
                                if isinstance(verdict_ledger.get("arbitration"), dict)
                                else {}
                            ).get("reviewRequired")
                        )
                    ),
                },
                "pivotalMomentCount": len(
                    verdict_ledger.get("pivotalMoments")
                    if isinstance(verdict_ledger.get("pivotalMoments"), list)
                    else []
                ),
            },
            "panelRuntimeProfiles": normalized_panel_runtime_profiles,
            "opinionPackVersion": opinion_pack.get("version"),
            "fairnessGate": fairness_summary,
        },
        "fairnessSummary": fairness_summary,
        "auditAlerts": audit_alerts,
        "errorCodes": error_codes,
        "degradationLevel": degradation_level,
    }
