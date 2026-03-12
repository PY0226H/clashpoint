from datetime import datetime
from typing import Any

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
