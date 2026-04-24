from __future__ import annotations

from typing import Any, Callable


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


def build_courtroom_read_model_view(
    *,
    report_payload: dict[str, Any] | None,
    case_evidence: dict[str, Any] | None,
    normalize_fairness_gate_decision: Callable[..., str],
) -> dict[str, Any]:
    payload = report_payload if isinstance(report_payload, dict) else {}
    evidence_view = case_evidence if isinstance(case_evidence, dict) else {}
    judge_trace = payload.get("judgeTrace") if isinstance(payload.get("judgeTrace"), dict) else {}

    case_dossier = (
        evidence_view.get("caseDossier")
        if isinstance(evidence_view.get("caseDossier"), dict)
        else {}
    )
    claim_graph = (
        evidence_view.get("claimGraph")
        if isinstance(evidence_view.get("claimGraph"), dict)
        else {}
    )
    claim_graph_summary = (
        evidence_view.get("claimGraphSummary")
        if isinstance(evidence_view.get("claimGraphSummary"), dict)
        else {}
    )
    evidence_ledger = (
        evidence_view.get("evidenceLedger")
        if isinstance(evidence_view.get("evidenceLedger"), dict)
        else {}
    )
    verdict_ledger = (
        evidence_view.get("verdictLedger")
        if isinstance(evidence_view.get("verdictLedger"), dict)
        else {}
    )
    opinion_pack = (
        evidence_view.get("opinionPack")
        if isinstance(evidence_view.get("opinionPack"), dict)
        else {}
    )
    fairness_summary = (
        evidence_view.get("fairnessSummary")
        if isinstance(evidence_view.get("fairnessSummary"), dict)
        else {}
    )
    panel_runtime_profiles = (
        evidence_view.get("panelRuntimeProfiles")
        if isinstance(evidence_view.get("panelRuntimeProfiles"), dict)
        else {}
    )
    audit_summary = (
        evidence_view.get("auditSummary")
        if isinstance(evidence_view.get("auditSummary"), dict)
        else {}
    )
    user_report = (
        opinion_pack.get("userReport")
        if isinstance(opinion_pack.get("userReport"), dict)
        else {}
    )
    ops_summary = (
        opinion_pack.get("opsSummary")
        if isinstance(opinion_pack.get("opsSummary"), dict)
        else {}
    )
    internal_review = (
        opinion_pack.get("internalReview")
        if isinstance(opinion_pack.get("internalReview"), dict)
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
    key_claims = (
        claim_graph_summary.get("coreClaims")
        if isinstance(claim_graph_summary.get("coreClaims"), dict)
        else {"pro": [], "con": []}
    )
    conflict_pairs = (
        claim_graph_summary.get("conflictPairs")
        if isinstance(claim_graph_summary.get("conflictPairs"), list)
        else []
    )
    unanswered_claims = (
        claim_graph_summary.get("unansweredClaims")
        if isinstance(claim_graph_summary.get("unansweredClaims"), list)
        else []
    )
    decisive_evidence_refs = (
        verdict_ledger.get("decisiveEvidenceRefs")
        if isinstance(verdict_ledger.get("decisiveEvidenceRefs"), list)
        else []
    )
    pivotal_moments = (
        verdict_ledger.get("pivotalMoments")
        if isinstance(verdict_ledger.get("pivotalMoments"), list)
        else []
    )
    gate_decision = normalize_fairness_gate_decision(
        arbitration.get("gateDecision"),
        review_required=bool(payload.get("reviewRequired")),
    )
    if not gate_decision:
        gate_decision = "blocked_to_draw" if bool(payload.get("reviewRequired")) else "pass_through"

    return {
        "recorder": {
            "caseDossier": case_dossier,
            "phaseRollupSummary": (
                payload.get("phaseRollupSummary")
                if isinstance(payload.get("phaseRollupSummary"), list)
                else []
            ),
            "retrievalSnapshotRollup": (
                payload.get("retrievalSnapshotRollup")
                if isinstance(payload.get("retrievalSnapshotRollup"), list)
                else []
            ),
            "phaseDebateTimeline": (
                user_report.get("phaseDebateTimeline")
                if isinstance(user_report.get("phaseDebateTimeline"), list)
                else []
            ),
        },
        "claim": {
            "claimGraph": claim_graph,
            "claimGraphSummary": claim_graph_summary,
            "keyClaimsBySide": key_claims,
            "conflictPairs": conflict_pairs,
            "unansweredClaims": unanswered_claims,
        },
        "evidence": {
            "evidenceLedger": evidence_ledger,
            "verdictEvidenceRefs": (
                evidence_view.get("verdictEvidenceRefs")
                if isinstance(evidence_view.get("verdictEvidenceRefs"), list)
                else []
            ),
            "decisiveEvidenceRefs": decisive_evidence_refs,
            "evidenceInsightCards": (
                user_report.get("evidenceInsightCards")
                if isinstance(user_report.get("evidenceInsightCards"), list)
                else []
            ),
        },
        "panel": {
            "panelDecisions": panel_decisions,
            "runtimeProfiles": panel_runtime_profiles,
            "pivotalMoments": pivotal_moments,
            "courtroomRoles": (
                judge_trace.get("courtroomRoles")
                if isinstance(judge_trace.get("courtroomRoles"), list)
                else []
            ),
            "courtroomWorkflowEdges": (
                judge_trace.get("courtroomWorkflowEdges")
                if isinstance(judge_trace.get("courtroomWorkflowEdges"), list)
                else []
            ),
            "courtroomArtifacts": (
                judge_trace.get("courtroomArtifacts")
                if isinstance(judge_trace.get("courtroomArtifacts"), list)
                else []
            ),
            "courtroomRoleOrder": (
                judge_trace.get("courtroomRoleOrder")
                if isinstance(judge_trace.get("courtroomRoleOrder"), list)
                else []
            ),
            "agentRuntime": (
                judge_trace.get("agentRuntime")
                if isinstance(judge_trace.get("agentRuntime"), dict)
                else {}
            ),
        },
        "fairness": {
            "summary": fairness_summary,
            "gateDecision": gate_decision,
            "reviewRequired": bool(payload.get("reviewRequired")),
            "errorCodes": (
                audit_summary.get("errorCodes")
                if isinstance(audit_summary.get("errorCodes"), list)
                else []
            ),
            "auditAlertCount": int(audit_summary.get("alertCount") or 0),
            "degradationLevel": audit_summary.get("degradationLevel"),
        },
        "opinion": {
            "winner": str(payload.get("winner") or "").strip().lower() or None,
            "debateSummary": payload.get("debateSummary"),
            "sideAnalysis": (
                payload.get("sideAnalysis")
                if isinstance(payload.get("sideAnalysis"), dict)
                else {}
            ),
            "verdictReason": payload.get("verdictReason"),
            "userReport": user_report,
            "opsSummary": ops_summary,
            "internalReview": internal_review,
        },
        "governance": {
            "policyVersion": evidence_view.get("policyVersion"),
            "promptVersion": evidence_view.get("promptVersion"),
            "toolsetVersion": evidence_view.get("toolsetVersion"),
            "policySnapshot": (
                evidence_view.get("policySnapshot")
                if isinstance(evidence_view.get("policySnapshot"), dict)
                else None
            ),
            "promptSnapshot": (
                evidence_view.get("promptSnapshot")
                if isinstance(evidence_view.get("promptSnapshot"), dict)
                else None
            ),
            "toolSnapshot": (
                evidence_view.get("toolSnapshot")
                if isinstance(evidence_view.get("toolSnapshot"), dict)
                else None
            ),
            "trustAttestation": (
                evidence_view.get("trustAttestation")
                if isinstance(evidence_view.get("trustAttestation"), dict)
                else None
            ),
        },
    }


def build_courtroom_read_model_light_summary(
    *,
    courtroom_view: dict[str, Any] | None,
    normalize_fairness_gate_decision: Callable[..., str],
) -> dict[str, Any]:
    model = courtroom_view if isinstance(courtroom_view, dict) else {}
    recorder = model.get("recorder") if isinstance(model.get("recorder"), dict) else {}
    claim = model.get("claim") if isinstance(model.get("claim"), dict) else {}
    evidence = model.get("evidence") if isinstance(model.get("evidence"), dict) else {}
    panel = model.get("panel") if isinstance(model.get("panel"), dict) else {}
    fairness = model.get("fairness") if isinstance(model.get("fairness"), dict) else {}
    opinion = model.get("opinion") if isinstance(model.get("opinion"), dict) else {}

    case_dossier = (
        recorder.get("caseDossier")
        if isinstance(recorder.get("caseDossier"), dict)
        else {}
    )
    message_window = (
        case_dossier.get("messageWindow")
        if isinstance(case_dossier.get("messageWindow"), dict)
        else {}
    )
    phase_info = case_dossier.get("phase") if isinstance(case_dossier.get("phase"), dict) else {}
    key_claims_by_side = (
        claim.get("keyClaimsBySide")
        if isinstance(claim.get("keyClaimsBySide"), dict)
        else {}
    )
    key_claim_count = 0
    for side in ("pro", "con"):
        entries = key_claims_by_side.get(side)
        if isinstance(entries, list):
            key_claim_count += len(entries)

    evidence_ledger = (
        evidence.get("evidenceLedger")
        if isinstance(evidence.get("evidenceLedger"), dict)
        else {}
    )
    evidence_stats = (
        evidence_ledger.get("stats")
        if isinstance(evidence_ledger.get("stats"), dict)
        else {}
    )
    source_citations = (
        evidence_ledger.get("sourceCitations")
        if isinstance(evidence_ledger.get("sourceCitations"), list)
        else []
    )
    conflict_sources = (
        evidence_ledger.get("conflictSources")
        if isinstance(evidence_ledger.get("conflictSources"), list)
        else []
    )
    decisive_refs = (
        evidence.get("decisiveEvidenceRefs")
        if isinstance(evidence.get("decisiveEvidenceRefs"), list)
        else []
    )
    courtroom_roles = (
        panel.get("courtroomRoles")
        if isinstance(panel.get("courtroomRoles"), list)
        else []
    )
    pivotal_moments = (
        panel.get("pivotalMoments")
        if isinstance(panel.get("pivotalMoments"), list)
        else []
    )
    conflict_pairs = (
        claim.get("conflictPairs")
        if isinstance(claim.get("conflictPairs"), list)
        else []
    )
    unanswered_claims = (
        claim.get("unansweredClaims")
        if isinstance(claim.get("unansweredClaims"), list)
        else []
    )
    claim_graph_summary = (
        claim.get("claimGraphSummary")
        if isinstance(claim.get("claimGraphSummary"), dict)
        else {}
    )
    claim_graph_stats = (
        claim_graph_summary.get("stats")
        if isinstance(claim_graph_summary.get("stats"), dict)
        else {}
    )
    fairness_summary = (
        fairness.get("summary")
        if isinstance(fairness.get("summary"), dict)
        else {}
    )

    return {
        "recorder": {
            "dispatchType": str(case_dossier.get("dispatchType") or "").strip().lower() or None,
            "phase": {
                "no": phase_info.get("no"),
                "startNo": phase_info.get("startNo"),
                "endNo": phase_info.get("endNo"),
            },
            "messageCount": (
                int(message_window.get("count"))
                if isinstance(message_window.get("count"), int)
                else 0
            ),
            "timelineCount": (
                len(recorder.get("phaseDebateTimeline"))
                if isinstance(recorder.get("phaseDebateTimeline"), list)
                else 0
            ),
        },
        "claim": {
            "keyClaimCount": key_claim_count,
            "conflictPairCount": len(conflict_pairs),
            "unansweredClaimCount": len(unanswered_claims),
            "stats": {
                "conflictEdges": (
                    int(claim_graph_stats.get("conflictEdges"))
                    if isinstance(claim_graph_stats.get("conflictEdges"), int)
                    else len(conflict_pairs)
                ),
                "unansweredClaims": (
                    int(claim_graph_stats.get("unansweredClaims"))
                    if isinstance(claim_graph_stats.get("unansweredClaims"), int)
                    else len(unanswered_claims)
                ),
            },
        },
        "evidence": {
            "decisiveEvidenceCount": len(decisive_refs),
            "sourceCitationCount": (
                int(evidence_stats.get("sourceCitationCount"))
                if isinstance(evidence_stats.get("sourceCitationCount"), int)
                else len(source_citations)
            ),
            "conflictSourceCount": (
                int(evidence_stats.get("conflictSourceCount"))
                if isinstance(evidence_stats.get("conflictSourceCount"), int)
                else len(conflict_sources)
            ),
            "stats": {
                "verdictReferencedCount": (
                    int(evidence_stats.get("verdictReferencedCount"))
                    if isinstance(evidence_stats.get("verdictReferencedCount"), int)
                    else len(decisive_refs)
                ),
                "reliabilityCounts": (
                    dict(evidence_stats.get("reliabilityCounts"))
                    if isinstance(evidence_stats.get("reliabilityCounts"), dict)
                    else {}
                ),
                "verdictReferencedReliabilityCounts": (
                    dict(evidence_stats.get("verdictReferencedReliabilityCounts"))
                    if isinstance(
                        evidence_stats.get("verdictReferencedReliabilityCounts"),
                        dict,
                    )
                    else {}
                ),
            },
        },
        "panel": {
            "courtroomRoleCount": len(courtroom_roles),
            "pivotalMomentCount": len(pivotal_moments),
            "panelHighDisagreement": bool(fairness_summary.get("panelHighDisagreement")),
        },
        "fairness": {
            "gateDecision": (
                normalize_fairness_gate_decision(
                    fairness.get("gateDecision"),
                    review_required=bool(fairness.get("reviewRequired")),
                )
                or None
            ),
            "reviewRequired": bool(fairness.get("reviewRequired")),
            "auditAlertCount": int(fairness.get("auditAlertCount") or 0),
            "degradationLevel": fairness.get("degradationLevel"),
        },
        "opinion": {
            "winner": str(opinion.get("winner") or "").strip().lower() or None,
            "debateSummary": (
                opinion.get("debateSummary")
                if isinstance(opinion.get("debateSummary"), str)
                else None
            ),
            "verdictReason": (
                opinion.get("verdictReason")
                if isinstance(opinion.get("verdictReason"), str)
                else None
            ),
        },
    }


def build_courtroom_drilldown_bundle_view(
    *,
    courtroom_view: dict[str, Any] | None,
    claim_preview_limit: int,
    evidence_preview_limit: int,
    panel_preview_limit: int,
    normalize_fairness_gate_decision: Callable[..., str],
) -> dict[str, Any]:
    model = courtroom_view if isinstance(courtroom_view, dict) else {}
    claim = model.get("claim") if isinstance(model.get("claim"), dict) else {}
    evidence = model.get("evidence") if isinstance(model.get("evidence"), dict) else {}
    panel = model.get("panel") if isinstance(model.get("panel"), dict) else {}
    fairness = model.get("fairness") if isinstance(model.get("fairness"), dict) else {}
    opinion = model.get("opinion") if isinstance(model.get("opinion"), dict) else {}
    governance = model.get("governance") if isinstance(model.get("governance"), dict) else {}

    claim_preview_cap = max(1, min(int(claim_preview_limit), 100))
    evidence_preview_cap = max(1, min(int(evidence_preview_limit), 100))
    panel_preview_cap = max(1, min(int(panel_preview_limit), 100))

    conflict_pairs = (
        claim.get("conflictPairs")
        if isinstance(claim.get("conflictPairs"), list)
        else []
    )
    unanswered_claims = (
        claim.get("unansweredClaims")
        if isinstance(claim.get("unansweredClaims"), list)
        else []
    )
    claim_graph_summary = (
        claim.get("claimGraphSummary")
        if isinstance(claim.get("claimGraphSummary"), dict)
        else {}
    )
    claim_graph_stats = (
        claim_graph_summary.get("stats")
        if isinstance(claim_graph_summary.get("stats"), dict)
        else {}
    )
    conflict_pair_count = max(
        len(conflict_pairs),
        int(claim_graph_stats.get("conflictEdges") or 0),
    )
    unanswered_claim_count = max(
        len(unanswered_claims),
        int(claim_graph_stats.get("unansweredClaims") or 0),
    )

    evidence_ledger = (
        evidence.get("evidenceLedger")
        if isinstance(evidence.get("evidenceLedger"), dict)
        else {}
    )
    evidence_stats = (
        evidence_ledger.get("stats")
        if isinstance(evidence_ledger.get("stats"), dict)
        else {}
    )
    source_citations = (
        evidence_ledger.get("sourceCitations")
        if isinstance(evidence_ledger.get("sourceCitations"), list)
        else []
    )
    conflict_sources = (
        evidence_ledger.get("conflictSources")
        if isinstance(evidence_ledger.get("conflictSources"), list)
        else []
    )
    decisive_refs = (
        evidence.get("decisiveEvidenceRefs")
        if isinstance(evidence.get("decisiveEvidenceRefs"), list)
        else []
    )
    verdict_refs = (
        evidence.get("verdictEvidenceRefs")
        if isinstance(evidence.get("verdictEvidenceRefs"), list)
        else []
    )
    evidence_reliability = build_evidence_claim_reliability_profile(
        evidence_stats=evidence_stats,
        fallback_decisive_count=len(decisive_refs),
    )

    pivotal_moments = (
        panel.get("pivotalMoments")
        if isinstance(panel.get("pivotalMoments"), list)
        else []
    )
    runtime_profiles = (
        panel.get("runtimeProfiles")
        if isinstance(panel.get("runtimeProfiles"), dict)
        else {}
    )
    courtroom_roles = (
        panel.get("courtroomRoles")
        if isinstance(panel.get("courtroomRoles"), list)
        else []
    )
    workflow_edges = (
        panel.get("courtroomWorkflowEdges")
        if isinstance(panel.get("courtroomWorkflowEdges"), list)
        else []
    )
    courtroom_artifacts = (
        panel.get("courtroomArtifacts")
        if isinstance(panel.get("courtroomArtifacts"), list)
        else []
    )

    return {
        "claim": {
            "keyClaimsBySide": (
                claim.get("keyClaimsBySide")
                if isinstance(claim.get("keyClaimsBySide"), dict)
                else {}
            ),
            "conflictPairCount": max(0, conflict_pair_count),
            "conflictPairsPreview": conflict_pairs[:claim_preview_cap],
            "conflictPairsHasMore": len(conflict_pairs) > claim_preview_cap,
            "unansweredClaimCount": max(0, unanswered_claim_count),
            "unansweredClaimsPreview": unanswered_claims[:claim_preview_cap],
            "unansweredClaimsHasMore": len(unanswered_claims) > claim_preview_cap,
            "claimGraphStats": claim_graph_stats,
        },
        "evidence": {
            "decisiveEvidenceCount": len(decisive_refs),
            "decisiveEvidenceRefsPreview": decisive_refs[:evidence_preview_cap],
            "decisiveEvidenceRefsHasMore": len(decisive_refs) > evidence_preview_cap,
            "verdictEvidenceRefCount": len(verdict_refs),
            "verdictEvidenceRefsPreview": verdict_refs[:evidence_preview_cap],
            "verdictEvidenceRefsHasMore": len(verdict_refs) > evidence_preview_cap,
            "sourceCitationCount": (
                int(evidence_stats.get("sourceCitationCount"))
                if isinstance(evidence_stats.get("sourceCitationCount"), int)
                else len(source_citations)
            ),
            "sourceCitationsPreview": source_citations[:evidence_preview_cap],
            "sourceCitationsHasMore": len(source_citations) > evidence_preview_cap,
            "conflictSourceCount": (
                int(evidence_stats.get("conflictSourceCount"))
                if isinstance(evidence_stats.get("conflictSourceCount"), int)
                else len(conflict_sources)
            ),
            "conflictSourcesPreview": conflict_sources[:evidence_preview_cap],
            "conflictSourcesHasMore": len(conflict_sources) > evidence_preview_cap,
            "reliability": evidence_reliability,
            "evidenceLedgerStats": evidence_stats,
        },
        "panel": {
            "pivotalMomentCount": len(pivotal_moments),
            "pivotalMomentsPreview": pivotal_moments[:panel_preview_cap],
            "pivotalMomentsHasMore": len(pivotal_moments) > panel_preview_cap,
            "runtimeProfiles": runtime_profiles,
            "courtroomRoleCount": len(courtroom_roles),
            "courtroomRolesPreview": courtroom_roles[:panel_preview_cap],
            "courtroomRolesHasMore": len(courtroom_roles) > panel_preview_cap,
            "workflowEdgeCount": len(workflow_edges),
            "workflowEdgesPreview": workflow_edges[:panel_preview_cap],
            "workflowEdgesHasMore": len(workflow_edges) > panel_preview_cap,
            "artifactCount": len(courtroom_artifacts),
            "artifactsPreview": courtroom_artifacts[:panel_preview_cap],
            "artifactsHasMore": len(courtroom_artifacts) > panel_preview_cap,
            "panelDecisions": (
                panel.get("panelDecisions")
                if isinstance(panel.get("panelDecisions"), dict)
                else {}
            ),
        },
        "fairness": {
            "gateDecision": (
                normalize_fairness_gate_decision(
                    fairness.get("gateDecision"),
                    review_required=bool(fairness.get("reviewRequired")),
                )
                or None
            ),
            "reviewRequired": bool(fairness.get("reviewRequired")),
            "auditAlertCount": int(fairness.get("auditAlertCount") or 0),
            "degradationLevel": fairness.get("degradationLevel"),
            "summary": (
                fairness.get("summary")
                if isinstance(fairness.get("summary"), dict)
                else {}
            ),
            "errorCodes": (
                fairness.get("errorCodes")
                if isinstance(fairness.get("errorCodes"), list)
                else []
            ),
        },
        "opinion": {
            "winner": str(opinion.get("winner") or "").strip().lower() or None,
            "debateSummary": (
                opinion.get("debateSummary")
                if isinstance(opinion.get("debateSummary"), str)
                else None
            ),
            "sideAnalysis": (
                opinion.get("sideAnalysis")
                if isinstance(opinion.get("sideAnalysis"), dict)
                else {}
            ),
            "verdictReason": (
                opinion.get("verdictReason")
                if isinstance(opinion.get("verdictReason"), str)
                else None
            ),
        },
        "governance": {
            "policyVersion": str(governance.get("policyVersion") or "").strip() or None,
            "promptVersion": str(governance.get("promptVersion") or "").strip() or None,
            "toolsetVersion": str(governance.get("toolsetVersion") or "").strip() or None,
        },
    }


def build_courtroom_drilldown_action_hints(
    *,
    drilldown: dict[str, Any],
) -> list[str]:
    payload = drilldown if isinstance(drilldown, dict) else {}
    claim = payload.get("claim") if isinstance(payload.get("claim"), dict) else {}
    evidence = (
        payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    )
    panel = payload.get("panel") if isinstance(payload.get("panel"), dict) else {}
    fairness = (
        payload.get("fairness") if isinstance(payload.get("fairness"), dict) else {}
    )
    reliability = (
        evidence.get("reliability")
        if isinstance(evidence.get("reliability"), dict)
        else {}
    )
    hints: list[str] = []
    if int(claim.get("conflictPairCount") or 0) > 0:
        hints.append("claim.resolve_conflict")
    if int(claim.get("unansweredClaimCount") or 0) > 0:
        hints.append("claim.answer_missing")
    reliability_level = str(reliability.get("level") or "").strip().lower()
    if reliability_level in {"low", "medium"}:
        hints.append("evidence.upgrade_reliability")
    if int(evidence.get("decisiveEvidenceCount") or 0) <= 0:
        hints.append("evidence.add_decisive_refs")
    if int(panel.get("pivotalMomentCount") or 0) <= 0:
        hints.append("panel.inspect_runtime")
    if bool(fairness.get("reviewRequired")):
        hints.append("review.queue.decide")
    if not hints:
        hints.append("monitor")
    return hints


def serialize_claim_ledger_record(
    record: Any,
    *,
    include_payload: bool = True,
) -> dict[str, Any]:
    item = {
        "caseId": record.case_id,
        "dispatchType": record.dispatch_type,
        "traceId": record.trace_id,
        "createdAt": record.created_at.isoformat(),
        "updatedAt": record.updated_at.isoformat(),
    }
    if include_payload:
        item["caseDossier"] = dict(record.case_dossier)
        item["claimGraph"] = dict(record.claim_graph)
        item["claimGraphSummary"] = dict(record.claim_graph_summary)
        item["evidenceLedger"] = dict(record.evidence_ledger)
        item["verdictEvidenceRefs"] = [dict(row) for row in record.verdict_evidence_refs]
    return item


def normalize_courtroom_case_sort_by(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "updated_at"
    return normalized


def normalize_courtroom_case_sort_order(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "desc"
    return normalized


def build_courtroom_case_sort_key(
    *,
    item: dict[str, Any],
    sort_by: str,
) -> tuple[Any, ...]:
    risk = item.get("riskProfile") if isinstance(item.get("riskProfile"), dict) else {}
    workflow = item.get("workflow") if isinstance(item.get("workflow"), dict) else {}
    if sort_by == "risk_score":
        return (
            int(risk.get("score") or 0),
            str(workflow.get("updatedAt") or "").strip(),
            int(workflow.get("caseId") or 0),
        )
    if sort_by == "case_id":
        return (int(workflow.get("caseId") or 0),)
    return (
        str(workflow.get("updatedAt") or "").strip(),
        int(risk.get("score") or 0),
        int(workflow.get("caseId") or 0),
    )


def normalize_evidence_claim_reliability_level(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return normalized


def normalize_evidence_claim_queue_sort_by(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "updated_at"
    return normalized


def normalize_evidence_claim_queue_sort_order(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "desc"
    return normalized
