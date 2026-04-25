from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

JUDGE_WORKFLOW_ROOT_KEY = "judgeWorkflow"
JUDGE_ROLE_ORDER: tuple[str, ...] = (
    "clerk",
    "recorder",
    "claim_graph",
    "evidence",
    "panel",
    "fairness_sentinel",
    "chief_arbiter",
    "opinion_writer",
)
JUDGE_WORKFLOW_SECTION_KEYS: tuple[str, ...] = (
    "caseDossier",
    "claimGraph",
    "evidenceBundle",
    "panelBundle",
    "fairnessGate",
    "verdict",
    "opinion",
)
JUDGE_CLAIM_GRAPH_KEYS: tuple[str, ...] = (
    "stats",
    "items",
    "unansweredClaimIds",
)
JUDGE_EVIDENCE_BUNDLE_KEYS: tuple[str, ...] = (
    "entries",
    "sourceCitations",
    "conflictSources",
    "stats",
)
JUDGE_PANEL_BUNDLE_KEYS: tuple[str, ...] = (
    "topWinner",
    "disagreementRatio",
    "judges",
)
JUDGE_FAIRNESS_GATE_KEYS: tuple[str, ...] = (
    "decision",
    "reviewRequired",
    "reasons",
    "auditAlertIds",
)
JUDGE_VERDICT_KEYS: tuple[str, ...] = (
    "winner",
    "needsDrawVote",
    "reviewRequired",
    "decisionPath",
)
JUDGE_OPINION_KEYS: tuple[str, ...] = (
    "debateSummary",
    "sideAnalysis",
    "verdictReason",
)
JUDGE_CASE_DOSSIER_KEYS: tuple[str, ...] = (
    "caseId",
    "dispatchType",
    "roleOrder",
)

_ALLOWED_DISPATCH_TYPES = {"phase", "final"}
_ALLOWED_WINNERS = {"pro", "con", "draw"}
_ALLOWED_FAIRNESS_DECISIONS = {
    "pass_through",
    "blocked_to_draw",
}


def _merge_defaults(default_payload: dict[str, Any], value: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(default_payload)
    if isinstance(value, dict):
        out.update(value)
    return out


def _required_keys_missing(payload: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    return [key for key in keys if key not in payload]


def _dict_payload(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _assert_required_keys(
    *,
    section: str,
    payload: dict[str, Any],
    keys: tuple[str, ...],
) -> None:
    missing = _required_keys_missing(payload, keys)
    if missing:
        raise ValueError(f"{section}_missing_keys:{','.join(sorted(missing))}")


@dataclass(frozen=True)
class JudgeCaseDossier:
    case_id: int
    dispatch_type: str
    trace_id: str | None = None
    scope_id: int | None = None
    session_id: int | None = None
    phase_start_no: int | None = None
    phase_end_no: int | None = None
    message_count: int = 0
    judge_policy_version: str | None = None
    rubric_version: str | None = None
    topic_domain: str | None = None
    role_order: tuple[str, ...] = JUDGE_ROLE_ORDER
    phase: dict[str, Any] = field(default_factory=dict)
    message_window: dict[str, Any] = field(default_factory=dict)
    input_validation: dict[str, Any] = field(default_factory=dict)
    redaction_summary: dict[str, Any] = field(default_factory=dict)
    transcript_snapshot: dict[str, Any] = field(default_factory=dict)
    completeness: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        input_validation = {
            "status": "accepted",
            "blocked": False,
            "auditReasons": [],
        }
        input_validation.update(self.input_validation)
        redaction_summary = {
            "status": "clean",
            "identityFieldsRemoved": 0,
            "semanticRedactionCount": 0,
            "redactedMessageIds": [],
            "auditReasons": [],
        }
        redaction_summary.update(self.redaction_summary)
        transcript_snapshot = {
            "version": "recorder_case_dossier_v1",
            "messageIds": [],
            "messageDigest": [],
            "timeline": [],
            "turnIndex": [],
            "replyLinks": [],
            "phaseWindows": [],
        }
        transcript_snapshot.update(self.transcript_snapshot)
        completeness = {
            "guard": "case_dossier_completeness_v1",
            "complete": True,
            "status": "complete",
            "coverageRatio": 1.0,
            "missingMessageIds": [],
            "invalidReplyLinks": [],
        }
        completeness.update(self.completeness)
        return {
            "caseId": int(self.case_id),
            "scopeId": self.scope_id,
            "sessionId": self.session_id,
            "traceId": self.trace_id,
            "dispatchType": str(self.dispatch_type).strip().lower(),
            "phaseRange": {
                "startNo": self.phase_start_no,
                "endNo": self.phase_end_no,
            },
            "messageCount": max(0, int(self.message_count)),
            "policy": {
                "judgePolicyVersion": self.judge_policy_version,
                "rubricVersion": self.rubric_version,
                "topicDomain": self.topic_domain,
            },
            "roleOrder": list(self.role_order),
            "phase": dict(self.phase),
            "messageWindow": dict(self.message_window),
            "inputValidation": input_validation,
            "redactionSummary": redaction_summary,
            "transcriptSnapshot": transcript_snapshot,
            "completeness": completeness,
        }


@dataclass(frozen=True)
class JudgeRoleDomainState:
    case_dossier: JudgeCaseDossier
    claim_graph: dict[str, Any] = field(default_factory=dict)
    evidence_bundle: dict[str, Any] = field(default_factory=dict)
    panel_bundle: dict[str, Any] = field(default_factory=dict)
    fairness_gate: dict[str, Any] = field(default_factory=dict)
    verdict: dict[str, Any] = field(default_factory=dict)
    opinion: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            JUDGE_WORKFLOW_ROOT_KEY: {
                "caseDossier": self.case_dossier.to_payload(),
                "claimGraph": _merge_defaults(
                    {
                        "stats": {},
                        "items": [],
                        "unansweredClaimIds": [],
                    },
                    self.claim_graph,
                ),
                "evidenceBundle": _merge_defaults(
                    {
                        "entries": [],
                        "sourceCitations": [],
                        "conflictSources": [],
                        "stats": {},
                    },
                    self.evidence_bundle,
                ),
                "panelBundle": _merge_defaults(
                    {
                        "topWinner": None,
                        "disagreementRatio": 0.0,
                        "judges": {},
                    },
                    self.panel_bundle,
                ),
                "fairnessGate": _merge_defaults(
                    {
                        "decision": "pass_through",
                        "reviewRequired": False,
                        "reasons": [],
                        "auditAlertIds": [],
                    },
                    self.fairness_gate,
                ),
                "verdict": _merge_defaults(
                    {
                        "winner": None,
                        "needsDrawVote": False,
                        "reviewRequired": False,
                        "decisionPath": [
                            "judge_panel",
                            "fairness_sentinel",
                            "chief_arbiter",
                        ],
                    },
                    self.verdict,
                ),
                "opinion": _merge_defaults(
                    {
                        "debateSummary": None,
                        "sideAnalysis": {},
                        "verdictReason": None,
                    },
                    self.opinion,
                ),
            }
        }


def build_judge_role_domain_state(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str | None = None,
    scope_id: int | None = None,
    session_id: int | None = None,
    phase_start_no: int | None = None,
    phase_end_no: int | None = None,
    message_count: int = 0,
    judge_policy_version: str | None = None,
    rubric_version: str | None = None,
    topic_domain: str | None = None,
    claim_graph: dict[str, Any] | None = None,
    evidence_bundle: dict[str, Any] | None = None,
    panel_bundle: dict[str, Any] | None = None,
    fairness_gate: dict[str, Any] | None = None,
    verdict: dict[str, Any] | None = None,
    opinion: dict[str, Any] | None = None,
    case_dossier_enrichment: dict[str, Any] | None = None,
) -> JudgeRoleDomainState:
    enrichment = dict(case_dossier_enrichment or {})
    return JudgeRoleDomainState(
        case_dossier=JudgeCaseDossier(
            case_id=case_id,
            dispatch_type=dispatch_type,
            trace_id=trace_id,
            scope_id=scope_id,
            session_id=session_id,
            phase_start_no=phase_start_no,
            phase_end_no=phase_end_no,
            message_count=message_count,
            judge_policy_version=judge_policy_version,
            rubric_version=rubric_version,
            topic_domain=topic_domain,
            phase=_dict_payload(enrichment.get("phase")),
            message_window=_dict_payload(enrichment.get("messageWindow")),
            input_validation=_dict_payload(enrichment.get("inputValidation")),
            redaction_summary=_dict_payload(enrichment.get("redactionSummary")),
            transcript_snapshot=_dict_payload(enrichment.get("transcriptSnapshot")),
            completeness=_dict_payload(enrichment.get("completeness")),
        ),
        claim_graph=dict(claim_graph) if isinstance(claim_graph, dict) else {},
        evidence_bundle=(
            dict(evidence_bundle) if isinstance(evidence_bundle, dict) else {}
        ),
        panel_bundle=dict(panel_bundle) if isinstance(panel_bundle, dict) else {},
        fairness_gate=dict(fairness_gate) if isinstance(fairness_gate, dict) else {},
        verdict=dict(verdict) if isinstance(verdict, dict) else {},
        opinion=dict(opinion) if isinstance(opinion, dict) else {},
    )


def validate_judge_app_domain_payload(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("judge_workflow_payload_not_dict")
    if set(payload.keys()) != {JUDGE_WORKFLOW_ROOT_KEY}:
        raise ValueError("judge_workflow_root_key_invalid")

    workflow = payload.get(JUDGE_WORKFLOW_ROOT_KEY)
    if not isinstance(workflow, dict):
        raise ValueError("judge_workflow_not_dict")
    _assert_required_keys(
        section="judge_workflow",
        payload=workflow,
        keys=JUDGE_WORKFLOW_SECTION_KEYS,
    )

    dossier = workflow.get("caseDossier")
    if not isinstance(dossier, dict):
        raise ValueError("judge_workflow_case_dossier_not_dict")
    _assert_required_keys(
        section="judge_workflow_case_dossier",
        payload=dossier,
        keys=JUDGE_CASE_DOSSIER_KEYS,
    )
    try:
        case_id = int(dossier.get("caseId"))
    except (TypeError, ValueError):
        case_id = 0
    if case_id <= 0:
        raise ValueError("judge_workflow_case_dossier_case_id_invalid")
    dispatch_type = str(dossier.get("dispatchType") or "").strip().lower()
    if dispatch_type not in _ALLOWED_DISPATCH_TYPES:
        raise ValueError("judge_workflow_case_dossier_dispatch_type_invalid")
    role_order = dossier.get("roleOrder")
    if not isinstance(role_order, list):
        raise ValueError("judge_workflow_case_dossier_role_order_not_list")
    normalized_role_order = tuple(str(item or "").strip().lower() for item in role_order)
    if normalized_role_order != JUDGE_ROLE_ORDER:
        raise ValueError("judge_workflow_case_dossier_role_order_invalid")
    for key in (
        "inputValidation",
        "redactionSummary",
        "transcriptSnapshot",
        "completeness",
    ):
        if key in dossier and not isinstance(dossier.get(key), dict):
            raise ValueError(f"judge_workflow_case_dossier_{key}_not_dict")
    completeness = dossier.get("completeness")
    if isinstance(completeness, dict):
        if not isinstance(completeness.get("complete"), bool):
            raise ValueError("judge_workflow_case_dossier_completeness_complete_not_bool")
        coverage_ratio = completeness.get("coverageRatio")
        if isinstance(coverage_ratio, bool) or not isinstance(coverage_ratio, (int, float)):
            raise ValueError("judge_workflow_case_dossier_completeness_coverage_ratio_invalid")
        if float(coverage_ratio) < 0.0 or float(coverage_ratio) > 1.0:
            raise ValueError("judge_workflow_case_dossier_completeness_coverage_ratio_invalid")

    claim_graph = workflow.get("claimGraph")
    if not isinstance(claim_graph, dict):
        raise ValueError("judge_workflow_claim_graph_not_dict")
    _assert_required_keys(
        section="judge_workflow_claim_graph",
        payload=claim_graph,
        keys=JUDGE_CLAIM_GRAPH_KEYS,
    )
    if not isinstance(claim_graph.get("stats"), dict):
        raise ValueError("judge_workflow_claim_graph_stats_not_dict")
    if not isinstance(claim_graph.get("items"), list):
        raise ValueError("judge_workflow_claim_graph_items_not_list")
    if not isinstance(claim_graph.get("unansweredClaimIds"), list):
        raise ValueError("judge_workflow_claim_graph_unanswered_claim_ids_not_list")

    evidence_bundle = workflow.get("evidenceBundle")
    if not isinstance(evidence_bundle, dict):
        raise ValueError("judge_workflow_evidence_bundle_not_dict")
    _assert_required_keys(
        section="judge_workflow_evidence_bundle",
        payload=evidence_bundle,
        keys=JUDGE_EVIDENCE_BUNDLE_KEYS,
    )
    if not isinstance(evidence_bundle.get("entries"), list):
        raise ValueError("judge_workflow_evidence_bundle_entries_not_list")
    if not isinstance(evidence_bundle.get("sourceCitations"), list):
        raise ValueError("judge_workflow_evidence_bundle_source_citations_not_list")
    if not isinstance(evidence_bundle.get("conflictSources"), list):
        raise ValueError("judge_workflow_evidence_bundle_conflict_sources_not_list")
    if not isinstance(evidence_bundle.get("stats"), dict):
        raise ValueError("judge_workflow_evidence_bundle_stats_not_dict")

    panel_bundle = workflow.get("panelBundle")
    if not isinstance(panel_bundle, dict):
        raise ValueError("judge_workflow_panel_bundle_not_dict")
    _assert_required_keys(
        section="judge_workflow_panel_bundle",
        payload=panel_bundle,
        keys=JUDGE_PANEL_BUNDLE_KEYS,
    )
    panel_top_winner = panel_bundle.get("topWinner")
    if panel_top_winner is not None and str(panel_top_winner).strip().lower() not in _ALLOWED_WINNERS:
        raise ValueError("judge_workflow_panel_bundle_top_winner_invalid")
    disagreement_ratio = panel_bundle.get("disagreementRatio")
    if isinstance(disagreement_ratio, bool) or not isinstance(disagreement_ratio, (int, float)):
        raise ValueError("judge_workflow_panel_bundle_disagreement_ratio_invalid")
    if float(disagreement_ratio) < 0.0 or float(disagreement_ratio) > 1.0:
        raise ValueError("judge_workflow_panel_bundle_disagreement_ratio_invalid")
    if not isinstance(panel_bundle.get("judges"), dict):
        raise ValueError("judge_workflow_panel_bundle_judges_not_dict")

    fairness_gate = workflow.get("fairnessGate")
    if not isinstance(fairness_gate, dict):
        raise ValueError("judge_workflow_fairness_gate_not_dict")
    _assert_required_keys(
        section="judge_workflow_fairness_gate",
        payload=fairness_gate,
        keys=JUDGE_FAIRNESS_GATE_KEYS,
    )
    fairness_decision = str(fairness_gate.get("decision") or "").strip().lower()
    if fairness_decision not in _ALLOWED_FAIRNESS_DECISIONS:
        raise ValueError("judge_workflow_fairness_gate_decision_invalid")
    if not isinstance(fairness_gate.get("reviewRequired"), bool):
        raise ValueError("judge_workflow_fairness_gate_review_required_not_bool")
    if not isinstance(fairness_gate.get("reasons"), list):
        raise ValueError("judge_workflow_fairness_gate_reasons_not_list")
    if not isinstance(fairness_gate.get("auditAlertIds"), list):
        raise ValueError("judge_workflow_fairness_gate_audit_alert_ids_not_list")

    verdict = workflow.get("verdict")
    if not isinstance(verdict, dict):
        raise ValueError("judge_workflow_verdict_not_dict")
    _assert_required_keys(
        section="judge_workflow_verdict",
        payload=verdict,
        keys=JUDGE_VERDICT_KEYS,
    )
    winner = verdict.get("winner")
    if winner is not None:
        winner_token = str(winner).strip().lower()
        if winner_token not in _ALLOWED_WINNERS:
            raise ValueError("judge_workflow_verdict_winner_invalid")
    else:
        winner_token = None
        if dispatch_type == "final":
            raise ValueError("judge_workflow_verdict_winner_missing_for_final")
    if not isinstance(verdict.get("needsDrawVote"), bool):
        raise ValueError("judge_workflow_verdict_needs_draw_vote_not_bool")
    verdict_review_required = verdict.get("reviewRequired")
    if not isinstance(verdict_review_required, bool):
        raise ValueError("judge_workflow_verdict_review_required_not_bool")
    decision_path = verdict.get("decisionPath")
    if not isinstance(decision_path, list):
        raise ValueError("judge_workflow_verdict_decision_path_not_list")
    normalized_path = [
        str(item or "").strip().lower()
        for item in decision_path
        if str(item or "").strip()
    ]
    if not normalized_path:
        raise ValueError("judge_workflow_verdict_decision_path_empty")

    fairness_review_required = bool(fairness_gate.get("reviewRequired"))
    if fairness_review_required != bool(verdict_review_required):
        raise ValueError("judge_workflow_fairness_verdict_review_required_mismatch")
    if fairness_decision == "blocked_to_draw" and not fairness_review_required:
        raise ValueError("judge_workflow_fairness_gate_blocked_to_draw_without_review")
    if fairness_decision == "pass_through" and fairness_review_required:
        raise ValueError("judge_workflow_fairness_gate_pass_through_with_review")
    if (
        dispatch_type == "final"
        and bool(verdict_review_required)
        and winner_token is not None
        and winner_token != "draw"
    ):
        raise ValueError("judge_workflow_verdict_review_required_winner_not_draw")

    opinion = workflow.get("opinion")
    if not isinstance(opinion, dict):
        raise ValueError("judge_workflow_opinion_not_dict")
    _assert_required_keys(
        section="judge_workflow_opinion",
        payload=opinion,
        keys=JUDGE_OPINION_KEYS,
    )
    side_analysis = opinion.get("sideAnalysis")
    if not isinstance(side_analysis, dict):
        raise ValueError("judge_workflow_opinion_side_analysis_not_dict")
