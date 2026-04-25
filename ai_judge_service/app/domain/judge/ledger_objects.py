from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

JUDGE_LEDGER_DISPATCH_TYPES = {"phase", "final"}
JUDGE_LEDGER_WINNERS = {"pro", "con", "draw"}


def _dict_payload(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_payload(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _normalize_dispatch_type(value: Any) -> str:
    token = str(value or "").strip().lower()
    return token if token in JUDGE_LEDGER_DISPATCH_TYPES else "unknown"


def _normalize_winner(value: Any) -> str | None:
    token = str(value or "").strip().lower()
    return token if token in JUDGE_LEDGER_WINNERS else None


@dataclass(frozen=True)
class JudgeLedgerCaseDossier:
    case_id: int
    dispatch_type: str
    trace_id: str
    scope_id: int = 1
    session_id: int | None = None
    phase_start_no: int | None = None
    phase_end_no: int | None = None
    message_count: int = 0
    judge_policy_version: str = ""
    rubric_version: str = ""
    topic_domain: str = "default"
    retrieval_profile: str | None = None
    input_validation: dict[str, Any] = field(default_factory=dict)
    redaction_summary: dict[str, Any] = field(default_factory=dict)
    transcript_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "caseId": int(self.case_id),
            "dispatchType": _normalize_dispatch_type(self.dispatch_type),
            "traceId": str(self.trace_id or "").strip(),
            "scopeId": int(self.scope_id),
            "sessionId": self.session_id,
            "phaseRange": {
                "startNo": self.phase_start_no,
                "endNo": self.phase_end_no,
            },
            "messageCount": max(0, int(self.message_count)),
            "policy": {
                "judgePolicyVersion": str(self.judge_policy_version or "").strip(),
                "rubricVersion": str(self.rubric_version or "").strip(),
                "topicDomain": str(self.topic_domain or "").strip() or "default",
                "retrievalProfile": self.retrieval_profile,
            },
            "inputValidation": dict(self.input_validation),
            "redactionSummary": dict(self.redaction_summary),
            "transcriptSnapshot": dict(self.transcript_snapshot),
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> JudgeLedgerCaseDossier:
        phase_range = _dict_payload(payload.get("phaseRange"))
        policy = _dict_payload(payload.get("policy"))
        return cls(
            case_id=int(payload.get("caseId") or 0),
            dispatch_type=_normalize_dispatch_type(payload.get("dispatchType")),
            trace_id=str(payload.get("traceId") or "").strip(),
            scope_id=int(payload.get("scopeId") or 1),
            session_id=(
                int(payload["sessionId"])
                if payload.get("sessionId") is not None
                else None
            ),
            phase_start_no=(
                int(phase_range["startNo"])
                if phase_range.get("startNo") is not None
                else None
            ),
            phase_end_no=(
                int(phase_range["endNo"])
                if phase_range.get("endNo") is not None
                else None
            ),
            message_count=max(0, int(payload.get("messageCount") or 0)),
            judge_policy_version=str(policy.get("judgePolicyVersion") or "").strip(),
            rubric_version=str(policy.get("rubricVersion") or "").strip(),
            topic_domain=str(policy.get("topicDomain") or "").strip() or "default",
            retrieval_profile=(
                str(policy.get("retrievalProfile")).strip()
                if policy.get("retrievalProfile") is not None
                else None
            ),
            input_validation=_dict_payload(payload.get("inputValidation")),
            redaction_summary=_dict_payload(payload.get("redactionSummary")),
            transcript_snapshot=_dict_payload(payload.get("transcriptSnapshot")),
        )


@dataclass(frozen=True)
class JudgeLedgerClaimGraph:
    payload: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        out = dict(self.payload)
        out.setdefault("stats", {})
        out.setdefault("items", [])
        out.setdefault("unansweredClaimIds", [])
        if self.summary:
            out["summary"] = dict(self.summary)
        return out

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> JudgeLedgerClaimGraph:
        return cls(
            payload=_dict_payload(payload),
            summary=_dict_payload(payload.get("summary")),
        )


@dataclass(frozen=True)
class JudgeLedgerEvidenceLedger:
    payload: dict[str, Any] = field(default_factory=dict)
    verdict_evidence_refs: list[dict[str, Any]] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        out = dict(self.payload)
        out.setdefault("entries", [])
        out.setdefault("messageRefs", [])
        out.setdefault("sourceCitations", [])
        out.setdefault("conflictSources", [])
        out["verdictEvidenceRefs"] = [
            dict(item) for item in self.verdict_evidence_refs if isinstance(item, dict)
        ]
        return out

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> JudgeLedgerEvidenceLedger:
        refs = [
            dict(item)
            for item in _list_payload(payload.get("verdictEvidenceRefs"))
            if isinstance(item, dict)
        ]
        return cls(payload=_dict_payload(payload), verdict_evidence_refs=refs)


@dataclass(frozen=True)
class JudgeLedgerVerdictLedger:
    winner: str | None = None
    side_scores: dict[str, Any] = field(default_factory=dict)
    dimension_scores: dict[str, Any] = field(default_factory=dict)
    accepted_claims: list[dict[str, Any]] = field(default_factory=list)
    rejected_claims: list[dict[str, Any]] = field(default_factory=list)
    pivotal_moments: list[dict[str, Any]] = field(default_factory=list)
    decisive_evidence_refs: list[dict[str, Any]] = field(default_factory=list)
    draw_reason: str | None = None
    review_reason: str | None = None
    arbitration: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "winner": _normalize_winner(self.winner),
            "sideScores": dict(self.side_scores),
            "dimensionScores": dict(self.dimension_scores),
            "acceptedClaims": [
                dict(item) for item in self.accepted_claims if isinstance(item, dict)
            ],
            "rejectedClaims": [
                dict(item) for item in self.rejected_claims if isinstance(item, dict)
            ],
            "pivotalMoments": [
                dict(item) for item in self.pivotal_moments if isinstance(item, dict)
            ],
            "decisiveEvidenceRefs": [
                dict(item) for item in self.decisive_evidence_refs if isinstance(item, dict)
            ],
            "drawReason": self.draw_reason,
            "reviewReason": self.review_reason,
            "arbitration": dict(self.arbitration),
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> JudgeLedgerVerdictLedger:
        return cls(
            winner=_normalize_winner(payload.get("winner")),
            side_scores=_dict_payload(payload.get("sideScores")),
            dimension_scores=_dict_payload(payload.get("dimensionScores")),
            accepted_claims=[
                dict(item)
                for item in _list_payload(payload.get("acceptedClaims"))
                if isinstance(item, dict)
            ],
            rejected_claims=[
                dict(item)
                for item in _list_payload(payload.get("rejectedClaims"))
                if isinstance(item, dict)
            ],
            pivotal_moments=[
                dict(item)
                for item in _list_payload(payload.get("pivotalMoments"))
                if isinstance(item, dict)
            ],
            decisive_evidence_refs=[
                dict(item)
                for item in _list_payload(payload.get("decisiveEvidenceRefs"))
                if isinstance(item, dict)
            ],
            draw_reason=(
                str(payload.get("drawReason")).strip()
                if payload.get("drawReason") is not None
                else None
            ),
            review_reason=(
                str(payload.get("reviewReason")).strip()
                if payload.get("reviewReason") is not None
                else None
            ),
            arbitration=_dict_payload(payload.get("arbitration")),
        )


@dataclass(frozen=True)
class JudgeLedgerFairnessReport:
    auto_judge_allowed: bool = True
    review_required: bool = False
    alerts: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "autoJudgeAllowed": bool(self.auto_judge_allowed),
            "reviewRequired": bool(self.review_required),
            "alerts": [dict(item) for item in self.alerts if isinstance(item, dict)],
            "metrics": dict(self.metrics),
            "reasons": [str(item) for item in self.reasons if str(item or "").strip()],
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> JudgeLedgerFairnessReport:
        return cls(
            auto_judge_allowed=bool(payload.get("autoJudgeAllowed", True)),
            review_required=bool(payload.get("reviewRequired", False)),
            alerts=[
                dict(item)
                for item in _list_payload(payload.get("alerts"))
                if isinstance(item, dict)
            ],
            metrics=_dict_payload(payload.get("metrics")),
            reasons=[
                str(item)
                for item in _list_payload(payload.get("reasons"))
                if str(item or "").strip()
            ],
        )


@dataclass(frozen=True)
class JudgeLedgerOpinionPack:
    user_report: dict[str, Any] = field(default_factory=dict)
    business_result: dict[str, Any] = field(default_factory=dict)
    ops_audit_summary: dict[str, Any] = field(default_factory=dict)
    trust_commitment: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "userReport": dict(self.user_report),
            "businessResult": dict(self.business_result),
            "opsAuditSummary": dict(self.ops_audit_summary),
            "trustCommitment": dict(self.trust_commitment),
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> JudgeLedgerOpinionPack:
        return cls(
            user_report=_dict_payload(payload.get("userReport")),
            business_result=_dict_payload(payload.get("businessResult")),
            ops_audit_summary=_dict_payload(payload.get("opsAuditSummary")),
            trust_commitment=_dict_payload(payload.get("trustCommitment")),
        )


@dataclass(frozen=True)
class JudgeLedgerSnapshot:
    case_id: int
    dispatch_type: str
    trace_id: str
    case_dossier: JudgeLedgerCaseDossier
    claim_graph: JudgeLedgerClaimGraph = field(default_factory=JudgeLedgerClaimGraph)
    evidence_ledger: JudgeLedgerEvidenceLedger = field(
        default_factory=JudgeLedgerEvidenceLedger
    )
    verdict_ledger: JudgeLedgerVerdictLedger = field(default_factory=JudgeLedgerVerdictLedger)
    fairness_report: JudgeLedgerFairnessReport = field(
        default_factory=JudgeLedgerFairnessReport
    )
    opinion_pack: JudgeLedgerOpinionPack = field(default_factory=JudgeLedgerOpinionPack)
    job_id: int | None = None
    scope_id: int = 1
    session_id: int | None = None
    judge_policy_version: str = ""
    rubric_version: str = ""
    topic_domain: str = "default"
    retrieval_profile: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "caseId": int(self.case_id),
            "jobId": self.job_id,
            "dispatchType": _normalize_dispatch_type(self.dispatch_type),
            "traceId": str(self.trace_id or "").strip(),
            "scopeId": int(self.scope_id),
            "sessionId": self.session_id,
            "policy": {
                "judgePolicyVersion": str(self.judge_policy_version or "").strip(),
                "rubricVersion": str(self.rubric_version or "").strip(),
                "topicDomain": str(self.topic_domain or "").strip() or "default",
                "retrievalProfile": self.retrieval_profile,
            },
            "caseDossier": self.case_dossier.to_payload(),
            "claimGraph": self.claim_graph.to_payload(),
            "evidenceLedger": self.evidence_ledger.to_payload(),
            "verdictLedger": self.verdict_ledger.to_payload(),
            "fairnessReport": self.fairness_report.to_payload(),
            "opinionPack": self.opinion_pack.to_payload(),
        }


def validate_judge_ledger_snapshot(snapshot: JudgeLedgerSnapshot) -> list[str]:
    errors: list[str] = []
    if int(snapshot.case_id) <= 0:
        errors.append("case_id_invalid")
    if _normalize_dispatch_type(snapshot.dispatch_type) not in JUDGE_LEDGER_DISPATCH_TYPES:
        errors.append("dispatch_type_invalid")
    if int(snapshot.case_dossier.case_id) != int(snapshot.case_id):
        errors.append("case_dossier_case_id_mismatch")
    if _normalize_dispatch_type(snapshot.case_dossier.dispatch_type) != _normalize_dispatch_type(
        snapshot.dispatch_type
    ):
        errors.append("case_dossier_dispatch_type_mismatch")
    if not str(snapshot.trace_id or "").strip():
        errors.append("trace_id_missing")
    winner = _normalize_winner(snapshot.verdict_ledger.winner)
    if snapshot.verdict_ledger.winner is not None and winner is None:
        errors.append("verdict_winner_invalid")
    if snapshot.opinion_pack.user_report and winner is None:
        errors.append("opinion_without_locked_verdict")
    return errors
