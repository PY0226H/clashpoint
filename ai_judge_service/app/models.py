from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

PhaseSide = Literal["pro", "con"]
VerdictWinner = Literal["pro", "con", "draw"]


class PhaseDispatchMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: int
    side: PhaseSide
    content: str
    created_at: datetime
    speaker_tag: str | None = None


class PhaseDispatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: int
    scope_id: int = Field(
        default=1,
        validation_alias=AliasChoices("scope_id", "scopeId"),
        serialization_alias="scopeId",
    )
    session_id: int
    phase_no: int
    message_start_id: int
    message_end_id: int
    message_count: int
    messages: list[PhaseDispatchMessage] = []
    rubric_version: str
    judge_policy_version: str = "v3-default"
    topic_domain: str = "default"
    retrieval_profile: str = "hybrid_v1"
    trace_id: str
    idempotency_key: str


class FinalDispatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: int
    scope_id: int = Field(
        default=1,
        validation_alias=AliasChoices("scope_id", "scopeId"),
        serialization_alias="scopeId",
    )
    session_id: int
    phase_start_no: int
    phase_end_no: int
    rubric_version: str
    judge_policy_version: str = "v3-default"
    topic_domain: str = "default"
    trace_id: str
    idempotency_key: str


class CaseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: int
    scope_id: int = Field(
        default=1,
        validation_alias=AliasChoices("scope_id", "scopeId"),
        serialization_alias="scopeId",
    )
    session_id: int
    rubric_version: str
    judge_policy_version: str = "v3-default"
    topic_domain: str = "default"
    retrieval_profile: str = "hybrid_v1"
    trace_id: str
    idempotency_key: str


class GroundedSummaryPayload(BaseModel):
    text: str
    message_ids: list[int] = []


class RetrievalBundleItemPayload(BaseModel):
    chunk_id: str
    title: str
    source_url: str
    score: float | None = None
    snippet: str | None = None
    conflict: bool = False


class RetrievalBundlePayload(BaseModel):
    queries: list[str] = []
    items: list[RetrievalBundleItemPayload] = []


class PhaseAgent1ScorePayload(BaseModel):
    pro: float
    con: float
    dimensions: dict[str, float] = {}
    rationale: str


class PhaseAgent2ScorePayload(BaseModel):
    pro: float
    con: float
    hit_items: list[str] = []
    miss_items: list[str] = []
    rationale: str


class PhaseAgent3WeightedScorePayload(BaseModel):
    pro: float
    con: float
    w1: float
    w2: float


class PhaseReportInput(BaseModel):
    session_id: int
    phase_no: int
    message_start_id: int
    message_end_id: int
    message_count: int
    pro_summary_grounded: GroundedSummaryPayload
    con_summary_grounded: GroundedSummaryPayload
    pro_retrieval_bundle: RetrievalBundlePayload
    con_retrieval_bundle: RetrievalBundlePayload
    agent1_score: PhaseAgent1ScorePayload
    agent2_score: PhaseAgent2ScorePayload
    agent3_weighted_score: PhaseAgent3WeightedScorePayload
    prompt_hashes: dict[str, str] = {}
    token_usage: dict[str, Any] = {}
    latency_ms: dict[str, Any] = {}
    error_codes: list[str] = []
    degradation_level: int = 0
    judge_trace: dict[str, Any] = {}


class FinalReportInput(BaseModel):
    session_id: int
    winner: VerdictWinner
    pro_score: float
    con_score: float
    dimension_scores: dict[str, float] = {}
    debate_summary: str
    side_analysis: dict[str, str] = {}
    verdict_reason: str
    claim_graph: dict[str, Any] = {}
    claim_graph_summary: dict[str, Any] = {}
    evidence_ledger: dict[str, Any] = {}
    verdict_ledger: dict[str, Any] = {}
    opinion_pack: dict[str, Any] = {}
    verdict_evidence_refs: list[dict[str, Any]] = []
    phase_rollup_summary: list[dict[str, Any]] = []
    retrieval_snapshot_rollup: list[dict[str, Any]] = []
    winner_first: VerdictWinner | None = None
    winner_second: VerdictWinner | None = None
    rejudge_triggered: bool = False
    needs_draw_vote: bool = False
    judge_trace: dict[str, Any] = {}
    audit_alerts: list[dict[str, Any]] = []
    error_codes: list[str] = []
    degradation_level: int = 0
