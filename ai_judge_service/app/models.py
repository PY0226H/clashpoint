from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field


class DispatchJob(BaseModel):
    job_id: int
    scope_id: int = Field(
        default=1,
        validation_alias=AliasChoices("scope_id", "scopeId"),
        serialization_alias="scopeId",
    )
    session_id: int
    requested_by: int
    style_mode: str
    rejudge_triggered: bool = False
    requested_at: datetime


class DispatchSession(BaseModel):
    status: str
    scheduled_start_at: datetime
    actual_start_at: datetime | None = None
    end_at: datetime


class DispatchTopic(BaseModel):
    title: str
    description: str
    category: str
    stance_pro: str
    stance_con: str
    context_seed: str | None = None


class DispatchMessage(BaseModel):
    message_id: int
    speaker_tag: str | None = None
    user_id: int | None = None
    side: str
    content: str
    created_at: datetime


class JudgeDispatchRequest(BaseModel):
    job: DispatchJob
    session: DispatchSession
    topic: DispatchTopic
    messages: list[DispatchMessage] = Field(default_factory=list)
    message_window_size: int = 100
    rubric_version: str
    trace_id: str | None = None
    idempotency_key: str | None = None
    judge_policy_version: str = "v2-default"
    topic_domain: str = "default"
    retrieval_profile: str = "hybrid_v1"


class JudgeStageSummaryInput(BaseModel):
    stage_no: int
    from_message_id: int | None = None
    to_message_id: int | None = None
    pro_score: int
    con_score: int
    summary: dict[str, Any] = Field(default_factory=dict)


class SubmitJudgeReportInput(BaseModel):
    winner: str
    pro_score: int
    con_score: int
    logic_pro: int
    logic_con: int
    evidence_pro: int
    evidence_con: int
    rebuttal_pro: int
    rebuttal_con: int
    clarity_pro: int
    clarity_con: int
    pro_summary: str
    con_summary: str
    rationale: str
    style_mode: str | None = None
    needs_draw_vote: bool = False
    rejudge_triggered: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)
    winner_first: str | None = None
    winner_second: str | None = None
    stage_summaries: list[JudgeStageSummaryInput] = Field(default_factory=list)


class MarkJudgeJobFailedInput(BaseModel):
    error_message: str


PhaseSide = Literal["pro", "con"]
VerdictWinner = Literal["pro", "con", "draw"]


class PhaseDispatchMessage(BaseModel):
    message_id: int
    side: PhaseSide
    content: str
    created_at: datetime
    speaker_tag: str | None = None


class PhaseDispatchRequest(BaseModel):
    job_id: int
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
    messages: list[PhaseDispatchMessage] = Field(default_factory=list)
    rubric_version: str
    judge_policy_version: str = "v3-default"
    topic_domain: str = "default"
    retrieval_profile: str = "hybrid_v1"
    trace_id: str
    idempotency_key: str


class FinalDispatchRequest(BaseModel):
    job_id: int
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


class GroundedSummaryPayload(BaseModel):
    text: str
    message_ids: list[int] = Field(default_factory=list)


class RetrievalBundleItemPayload(BaseModel):
    chunk_id: str
    title: str
    source_url: str
    score: float | None = None
    snippet: str | None = None
    conflict: bool = False


class RetrievalBundlePayload(BaseModel):
    queries: list[str] = Field(default_factory=list)
    items: list[RetrievalBundleItemPayload] = Field(default_factory=list)


class PhaseAgent1ScorePayload(BaseModel):
    pro: float
    con: float
    dimensions: dict[str, float] = Field(default_factory=dict)
    rationale: str


class PhaseAgent2ScorePayload(BaseModel):
    pro: float
    con: float
    hit_items: list[str] = Field(default_factory=list)
    miss_items: list[str] = Field(default_factory=list)
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
    prompt_hashes: dict[str, str] = Field(default_factory=dict)
    token_usage: dict[str, Any] = Field(default_factory=dict)
    latency_ms: dict[str, Any] = Field(default_factory=dict)
    error_codes: list[str] = Field(default_factory=list)
    degradation_level: int = 0
    judge_trace: dict[str, Any] = Field(default_factory=dict)


class FinalReportInput(BaseModel):
    session_id: int
    winner: VerdictWinner
    pro_score: float
    con_score: float
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    final_rationale: str
    verdict_evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    phase_rollup_summary: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_snapshot_rollup: list[dict[str, Any]] = Field(default_factory=list)
    winner_first: VerdictWinner | None = None
    winner_second: VerdictWinner | None = None
    rejudge_triggered: bool = False
    needs_draw_vote: bool = False
    judge_trace: dict[str, Any] = Field(default_factory=dict)
    audit_alerts: list[dict[str, Any]] = Field(default_factory=list)
    error_codes: list[str] = Field(default_factory=list)
    degradation_level: int = 0
