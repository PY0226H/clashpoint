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

    def to_payload(self) -> dict[str, Any]:
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
) -> JudgeRoleDomainState:
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
        keys=("caseId", "dispatchType", "roleOrder"),
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

    claim_graph = workflow.get("claimGraph")
    if not isinstance(claim_graph, dict):
        raise ValueError("judge_workflow_claim_graph_not_dict")
    evidence_bundle = workflow.get("evidenceBundle")
    if not isinstance(evidence_bundle, dict):
        raise ValueError("judge_workflow_evidence_bundle_not_dict")
    panel_bundle = workflow.get("panelBundle")
    if not isinstance(panel_bundle, dict):
        raise ValueError("judge_workflow_panel_bundle_not_dict")

    fairness_gate = workflow.get("fairnessGate")
    if not isinstance(fairness_gate, dict):
        raise ValueError("judge_workflow_fairness_gate_not_dict")
    fairness_decision = str(fairness_gate.get("decision") or "").strip().lower()
    if fairness_decision not in _ALLOWED_FAIRNESS_DECISIONS:
        raise ValueError("judge_workflow_fairness_gate_decision_invalid")
    if not isinstance(fairness_gate.get("reviewRequired"), bool):
        raise ValueError("judge_workflow_fairness_gate_review_required_not_bool")

    verdict = workflow.get("verdict")
    if not isinstance(verdict, dict):
        raise ValueError("judge_workflow_verdict_not_dict")
    winner = verdict.get("winner")
    if winner is not None:
        winner_token = str(winner).strip().lower()
        if winner_token not in _ALLOWED_WINNERS:
            raise ValueError("judge_workflow_verdict_winner_invalid")
    if not isinstance(verdict.get("needsDrawVote"), bool):
        raise ValueError("judge_workflow_verdict_needs_draw_vote_not_bool")
    if not isinstance(verdict.get("reviewRequired"), bool):
        raise ValueError("judge_workflow_verdict_review_required_not_bool")

    opinion = workflow.get("opinion")
    if not isinstance(opinion, dict):
        raise ValueError("judge_workflow_opinion_not_dict")
    side_analysis = opinion.get("sideAnalysis")
    if not isinstance(side_analysis, dict):
        raise ValueError("judge_workflow_opinion_side_analysis_not_dict")
