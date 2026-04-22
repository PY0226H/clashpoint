from __future__ import annotations

from typing import Any


def build_case_evidence_view(
    *,
    report_payload: dict[str, Any] | None,
    verdict_contract: dict[str, Any] | None,
    claim_ledger_record: Any | None = None,
) -> dict[str, Any]:
    payload = report_payload if isinstance(report_payload, dict) else {}
    contract = verdict_contract if isinstance(verdict_contract, dict) else {}
    judge_trace = payload.get("judgeTrace") if isinstance(payload.get("judgeTrace"), dict) else {}
    ledger_case_dossier = (
        claim_ledger_record.case_dossier
        if claim_ledger_record is not None and isinstance(claim_ledger_record.case_dossier, dict)
        else None
    )
    ledger_claim_graph = (
        claim_ledger_record.claim_graph
        if claim_ledger_record is not None and isinstance(claim_ledger_record.claim_graph, dict)
        else None
    )
    ledger_claim_summary = (
        claim_ledger_record.claim_graph_summary
        if claim_ledger_record is not None and isinstance(claim_ledger_record.claim_graph_summary, dict)
        else None
    )
    ledger_evidence_ledger = (
        claim_ledger_record.evidence_ledger
        if claim_ledger_record is not None and isinstance(claim_ledger_record.evidence_ledger, dict)
        else None
    )
    ledger_verdict_refs = (
        claim_ledger_record.verdict_evidence_refs
        if claim_ledger_record is not None and isinstance(claim_ledger_record.verdict_evidence_refs, list)
        else []
    )

    claim_graph = (
        payload.get("claimGraph")
        if isinstance(payload.get("claimGraph"), dict)
        else ledger_claim_graph
    )
    claim_graph_summary = (
        payload.get("claimGraphSummary")
        if isinstance(payload.get("claimGraphSummary"), dict)
        else ledger_claim_summary
    )
    case_dossier = (
        payload.get("caseDossier")
        if isinstance(payload.get("caseDossier"), dict)
        else ledger_case_dossier
    )
    verdict_ledger = (
        payload.get("verdictLedger")
        if isinstance(payload.get("verdictLedger"), dict)
        else (
            contract.get("verdictLedger")
            if isinstance(contract.get("verdictLedger"), dict)
            else None
        )
    )
    opinion_pack = (
        payload.get("opinionPack")
        if isinstance(payload.get("opinionPack"), dict)
        else (
            contract.get("opinionPack")
            if isinstance(contract.get("opinionPack"), dict)
            else None
        )
    )
    evidence_ledger = (
        payload.get("evidenceLedger")
        if isinstance(payload.get("evidenceLedger"), dict)
        else (
            contract.get("evidenceLedger")
            if isinstance(contract.get("evidenceLedger"), dict)
            else ledger_evidence_ledger
        )
    )
    policy_snapshot = (
        judge_trace.get("policyRegistry")
        if isinstance(judge_trace.get("policyRegistry"), dict)
        else None
    )
    prompt_snapshot = (
        judge_trace.get("promptRegistry")
        if isinstance(judge_trace.get("promptRegistry"), dict)
        else None
    )
    tool_snapshot = (
        judge_trace.get("toolRegistry")
        if isinstance(judge_trace.get("toolRegistry"), dict)
        else None
    )
    trust_attestation = (
        payload.get("trustAttestation")
        if isinstance(payload.get("trustAttestation"), dict)
        else None
    )
    fairness_summary = (
        payload.get("fairnessSummary")
        if isinstance(payload.get("fairnessSummary"), dict)
        else (
            contract.get("fairnessSummary")
            if isinstance(contract.get("fairnessSummary"), dict)
            else None
        )
    )
    panel_runtime_profiles = (
        judge_trace.get("panelRuntimeProfiles")
        if isinstance(judge_trace.get("panelRuntimeProfiles"), dict)
        else (
            (
                verdict_ledger.get("panelDecisions")
                if isinstance(verdict_ledger, dict)
                and isinstance(verdict_ledger.get("panelDecisions"), dict)
                else {}
            ).get("runtimeProfiles")
            if isinstance(
                (
                    verdict_ledger.get("panelDecisions")
                    if isinstance(verdict_ledger, dict)
                    and isinstance(verdict_ledger.get("panelDecisions"), dict)
                    else {}
                ).get("runtimeProfiles"),
                dict,
            )
            else None
        )
    )

    raw_audit_alerts = payload.get("auditAlerts")
    if not isinstance(raw_audit_alerts, list):
        raw_audit_alerts = contract.get("auditAlerts")
    audit_alerts = [item for item in (raw_audit_alerts or []) if isinstance(item, dict)]

    raw_error_codes = payload.get("errorCodes")
    if not isinstance(raw_error_codes, list):
        raw_error_codes = contract.get("errorCodes")
    error_codes = [
        str(item).strip()
        for item in (raw_error_codes or [])
        if str(item).strip()
    ]

    raw_verdict_refs = payload.get("verdictEvidenceRefs")
    if not isinstance(raw_verdict_refs, list):
        raw_verdict_refs = contract.get("verdictEvidenceRefs")
    verdict_evidence_refs = [
        dict(item)
        for item in ((raw_verdict_refs or ledger_verdict_refs) or [])
        if isinstance(item, dict)
    ]

    degradation_level = (
        int(payload.get("degradationLevel"))
        if isinstance(payload.get("degradationLevel"), int)
        else (
            int(contract.get("degradationLevel"))
            if isinstance(contract.get("degradationLevel"), int)
            else None
        )
    )

    policy_version = (
        str(policy_snapshot.get("version")).strip()
        if isinstance(policy_snapshot, dict)
        and str(policy_snapshot.get("version") or "").strip()
        else None
    )
    prompt_version = (
        str(prompt_snapshot.get("version")).strip()
        if isinstance(prompt_snapshot, dict)
        and str(prompt_snapshot.get("version") or "").strip()
        else None
    )
    toolset_version = (
        str(tool_snapshot.get("version")).strip()
        if isinstance(tool_snapshot, dict)
        and str(tool_snapshot.get("version") or "").strip()
        else None
    )

    return {
        "caseDossier": case_dossier,
        "claimGraph": claim_graph,
        "claimGraphSummary": claim_graph_summary,
        "evidenceLedger": evidence_ledger,
        "verdictLedger": verdict_ledger,
        "opinionPack": opinion_pack,
        "policySnapshot": policy_snapshot,
        "policyVersion": policy_version,
        "promptSnapshot": prompt_snapshot,
        "promptVersion": prompt_version,
        "toolSnapshot": tool_snapshot,
        "toolsetVersion": toolset_version,
        "trustAttestation": trust_attestation,
        "fairnessSummary": fairness_summary,
        "panelRuntimeProfiles": panel_runtime_profiles,
        "verdictEvidenceRefs": verdict_evidence_refs,
        "auditSummary": {
            "alertCount": len(audit_alerts),
            "auditAlerts": audit_alerts,
            "errorCodes": error_codes,
            "degradationLevel": degradation_level,
        },
        "claimLedger": (
            {
                "dispatchType": claim_ledger_record.dispatch_type,
                "traceId": claim_ledger_record.trace_id,
                "createdAt": claim_ledger_record.created_at.isoformat(),
                "updatedAt": claim_ledger_record.updated_at.isoformat(),
            }
            if claim_ledger_record is not None
            else None
        ),
        "hasCaseDossier": case_dossier is not None,
        "hasClaimGraph": claim_graph is not None,
        "hasClaimLedger": claim_ledger_record is not None,
        "hasEvidenceLedger": evidence_ledger is not None,
        "hasVerdictLedger": verdict_ledger is not None,
        "hasOpinionPack": opinion_pack is not None,
        "hasTrustAttestation": trust_attestation is not None,
    }


def normalize_evidence_claim_reliability_counts(raw: Any) -> dict[str, int]:
    counts = {
        "high": 0,
        "medium": 0,
        "low": 0,
        "unknown": 0,
    }
    if not isinstance(raw, dict):
        return counts
    for key in counts:
        value = raw.get(key)
        try:
            counts[key] = max(0, int(value))
        except (TypeError, ValueError):
            counts[key] = 0
    return counts


def build_evidence_claim_reliability_profile(
    *,
    evidence_stats: dict[str, Any],
    fallback_decisive_count: int,
) -> dict[str, Any]:
    stats = evidence_stats if isinstance(evidence_stats, dict) else {}
    reliability_counts = normalize_evidence_claim_reliability_counts(
        stats.get("reliabilityCounts")
    )
    verdict_referenced_counts = normalize_evidence_claim_reliability_counts(
        stats.get("verdictReferencedReliabilityCounts")
    )

    try:
        verdict_referenced_count = max(0, int(stats.get("verdictReferencedCount") or 0))
    except (TypeError, ValueError):
        verdict_referenced_count = 0
    if verdict_referenced_count <= 0:
        verdict_referenced_count = sum(verdict_referenced_counts.values())
    if verdict_referenced_count <= 0:
        verdict_referenced_count = max(0, int(fallback_decisive_count))

    low_referenced_count = max(0, int(verdict_referenced_counts.get("low") or 0))
    if verdict_referenced_count > 0:
        low_referenced_ratio = round(
            low_referenced_count / float(max(1, verdict_referenced_count)),
            4,
        )
    else:
        low_referenced_ratio = None

    if verdict_referenced_count <= 0:
        level = "unknown"
        score = 0
    else:
        ratio = float(low_referenced_ratio or 0.0)
        score = max(0, min(100, int(round((1.0 - ratio) * 100.0))))
        if ratio >= 0.45:
            level = "low"
        elif ratio >= 0.2:
            level = "medium"
        else:
            level = "high"

    return {
        "level": level,
        "score": score,
        "lowReferencedCount": low_referenced_count,
        "lowReferencedRatio": low_referenced_ratio,
        "verdictReferencedCount": verdict_referenced_count,
        "reliabilityCounts": reliability_counts,
        "verdictReferencedReliabilityCounts": verdict_referenced_counts,
    }


def build_evidence_claim_ops_profile(
    *,
    risk_profile: dict[str, Any],
    courtroom_summary: dict[str, Any],
) -> dict[str, Any]:
    risk = risk_profile if isinstance(risk_profile, dict) else {}
    summary = courtroom_summary if isinstance(courtroom_summary, dict) else {}
    claim = summary.get("claim") if isinstance(summary.get("claim"), dict) else {}
    evidence = (
        summary.get("evidence") if isinstance(summary.get("evidence"), dict) else {}
    )
    claim_stats = claim.get("stats") if isinstance(claim.get("stats"), dict) else {}

    conflict_pair_count = max(
        int(claim.get("conflictPairCount") or 0),
        int(claim_stats.get("conflictEdges") or 0),
    )
    unanswered_claim_count = max(
        int(claim.get("unansweredClaimCount") or 0),
        int(claim_stats.get("unansweredClaims") or 0),
    )
    decisive_evidence_count = int(evidence.get("decisiveEvidenceCount") or 0)
    conflict_source_count = int(evidence.get("conflictSourceCount") or 0)
    source_citation_count = int(evidence.get("sourceCitationCount") or 0)
    evidence_stats = (
        evidence.get("stats") if isinstance(evidence.get("stats"), dict) else {}
    )
    reliability_profile = build_evidence_claim_reliability_profile(
        evidence_stats=evidence_stats,
        fallback_decisive_count=decisive_evidence_count,
    )

    has_conflict = conflict_pair_count > 0 or conflict_source_count > 0
    has_unanswered_claim = unanswered_claim_count > 0
    priority_score = int(risk.get("score") or 0)
    risk_tags: list[str] = []
    if has_conflict:
        priority_score += 15
        risk_tags.append("claim_conflict_present")
    if has_unanswered_claim:
        priority_score += 18
        risk_tags.append("claim_unanswered")
    reliability_level = str(reliability_profile.get("level") or "").strip().lower()
    if reliability_level == "low":
        priority_score += 20
        risk_tags.append("evidence_reliability_low")
    elif reliability_level == "medium":
        priority_score += 8
        risk_tags.append("evidence_reliability_medium")
    if decisive_evidence_count <= 0:
        priority_score += 8
        risk_tags.append("no_decisive_evidence")
    priority_score = max(0, min(priority_score, 100))

    if priority_score >= 75:
        priority_level = "high"
    elif priority_score >= 45:
        priority_level = "medium"
    else:
        priority_level = "low"

    return {
        "priorityScore": priority_score,
        "priorityLevel": priority_level,
        "slaBucket": str(risk.get("slaBucket") or "").strip().lower() or "unknown",
        "riskTags": risk_tags,
        "hasConflict": has_conflict,
        "hasUnansweredClaim": has_unanswered_claim,
        "conflictPairCount": max(0, conflict_pair_count),
        "unansweredClaimCount": max(0, unanswered_claim_count),
        "decisiveEvidenceCount": max(0, decisive_evidence_count),
        "sourceCitationCount": max(0, source_citation_count),
        "conflictSourceCount": max(0, conflict_source_count),
        "reliability": reliability_profile,
    }


def build_evidence_claim_action_hints(
    *,
    ops_profile: dict[str, Any],
    review_required: bool,
) -> list[str]:
    profile = ops_profile if isinstance(ops_profile, dict) else {}
    hints: list[str] = []
    if bool(profile.get("hasUnansweredClaim")):
        hints.append("claim.answer_missing")
    if int(profile.get("conflictPairCount") or 0) > 0:
        hints.append("claim.resolve_conflict")
    reliability = (
        profile.get("reliability")
        if isinstance(profile.get("reliability"), dict)
        else {}
    )
    reliability_level = str(reliability.get("level") or "").strip().lower()
    if reliability_level in {"low", "medium"}:
        hints.append("evidence.upgrade_reliability")
    if int(profile.get("decisiveEvidenceCount") or 0) <= 0:
        hints.append("evidence.add_decisive_refs")
    if review_required:
        hints.append("review.queue.decide")
    if not hints:
        hints.append("monitor")
    return hints


def build_evidence_claim_queue_sort_key(
    *,
    item: dict[str, Any],
    sort_by: str,
) -> tuple[Any, ...]:
    ops_profile = (
        item.get("claimEvidenceProfile")
        if isinstance(item.get("claimEvidenceProfile"), dict)
        else {}
    )
    reliability = (
        ops_profile.get("reliability")
        if isinstance(ops_profile.get("reliability"), dict)
        else {}
    )
    workflow = item.get("workflow") if isinstance(item.get("workflow"), dict) else {}
    risk = item.get("riskProfile") if isinstance(item.get("riskProfile"), dict) else {}
    if sort_by == "risk_score":
        return (
            int(ops_profile.get("priorityScore") or 0),
            int(risk.get("score") or 0),
            str(workflow.get("updatedAt") or "").strip(),
            int(workflow.get("caseId") or 0),
        )
    if sort_by == "conflict_pair_count":
        return (
            int(ops_profile.get("conflictPairCount") or 0),
            int(ops_profile.get("priorityScore") or 0),
            int(workflow.get("caseId") or 0),
        )
    if sort_by == "unanswered_claim_count":
        return (
            int(ops_profile.get("unansweredClaimCount") or 0),
            int(ops_profile.get("priorityScore") or 0),
            int(workflow.get("caseId") or 0),
        )
    if sort_by == "reliability_score":
        return (
            int(reliability.get("score") or 0),
            int(ops_profile.get("priorityScore") or 0),
            int(workflow.get("caseId") or 0),
        )
    if sort_by == "case_id":
        return (int(workflow.get("caseId") or 0),)
    return (
        str(workflow.get("updatedAt") or "").strip(),
        int(ops_profile.get("priorityScore") or 0),
        int(workflow.get("caseId") or 0),
    )
