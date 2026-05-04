from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DebateSide = Literal["pro", "con"]
NpcActionType = Literal["speak", "praise", "effect", "state_changed"]
NpcStatus = Literal["observing", "speaking", "praising", "silent", "manual_takeover", "unavailable"]
NpcRoomStatus = Literal["active", "silent", "manual_takeover", "unavailable"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=None, populate_by_name=True)


class DebateMessageSnapshot(CamelModel):
    message_id: int = Field(alias="messageId")
    session_id: int = Field(alias="sessionId")
    user_id: int = Field(alias="userId")
    side: DebateSide
    content: str
    created_at: str | None = Field(default=None, alias="createdAt")


class NpcPublicCallSnapshot(CamelModel):
    public_call_id: int = Field(alias="publicCallId")
    session_id: int = Field(alias="sessionId")
    user_id: int = Field(alias="userId")
    npc_id: str = Field(alias="npcId")
    call_type: str = Field(alias="callType")
    content: str
    status: str
    created_at: str | None = Field(default=None, alias="createdAt")


class NpcRoomConfig(CamelModel):
    session_id: int = Field(alias="sessionId")
    npc_id: str = Field(default="virtual_judge_default", alias="npcId")
    display_name: str = Field(default="虚拟裁判", alias="displayName")
    enabled: bool = False
    persona_style: str = Field(default="balanced_host", alias="personaStyle")
    status: NpcRoomStatus = "unavailable"
    allow_speak: bool = Field(default=True, alias="allowSpeak")
    allow_praise: bool = Field(default=True, alias="allowPraise")
    allow_effect: bool = Field(default=True, alias="allowEffect")
    allow_state_change: bool = Field(default=True, alias="allowStateChange")
    allow_warning: bool = Field(default=True, alias="allowWarning")
    allow_public_call: bool = Field(default=False, alias="allowPublicCall")
    allow_pause: bool = Field(default=False, alias="allowPause")
    manual_takeover_by_user_id: int | None = Field(default=None, alias="manualTakeoverByUserId")
    status_reason: str | None = Field(default=None, alias="statusReason")
    updated_by_user_id: int | None = Field(default=None, alias="updatedByUserId")
    created_at: str | None = Field(default=None, alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")


class NpcDecisionContext(CamelModel):
    session_id: int = Field(alias="sessionId")
    npc_id: str = Field(default="virtual_judge_default", alias="npcId")
    room_config: NpcRoomConfig = Field(alias="roomConfig")
    source_event_id: str | None = Field(default=None, alias="sourceEventId")
    trigger_message: DebateMessageSnapshot | None = Field(default=None, alias="triggerMessage")
    public_call: NpcPublicCallSnapshot | None = Field(default=None, alias="publicCall")
    recent_messages: list[DebateMessageSnapshot] = Field(default_factory=list, alias="recentMessages")
    now: str = Field(default_factory=utc_now_iso)


class NpcActionCandidate(CamelModel):
    action_uid: str = Field(alias="actionUid")
    session_id: int = Field(alias="sessionId")
    npc_id: str = Field(alias="npcId")
    action_type: NpcActionType = Field(alias="actionType")
    public_text: str | None = Field(default=None, alias="publicText")
    target_message_id: int | None = Field(default=None, alias="targetMessageId")
    target_user_id: int | None = Field(default=None, alias="targetUserId")
    target_side: DebateSide | None = Field(default=None, alias="targetSide")
    effect_kind: str | None = Field(default=None, alias="effectKind")
    npc_status: NpcStatus | None = Field(default=None, alias="npcStatus")
    reason_code: str | None = Field(default=None, alias="reasonCode")
    source_event_id: str | None = Field(default=None, alias="sourceEventId")
    source_message_id: int | None = Field(default=None, alias="sourceMessageId")
    policy_version: str = Field(alias="policyVersion")
    executor_kind: str = Field(alias="executorKind")
    executor_version: str = Field(alias="executorVersion")
    trace_id: str | None = Field(default=None, alias="traceId")


class NpcDecisionRun(CamelModel):
    status: Literal["created", "fallback", "silent", "rejected"]
    executor_kind: str = Field(alias="executorKind")
    executor_version: str = Field(alias="executorVersion")
    fallback_used: bool = Field(alias="fallbackUsed")
    fallback_reason: str | None = Field(default=None, alias="fallbackReason")
    candidate: NpcActionCandidate | None = None
    guard_reason: str | None = Field(default=None, alias="guardReason")
    failures: list[str] = Field(default_factory=list)


class SubmitActionCandidateOutput(CamelModel):
    accepted: bool
    action_id: int | None = Field(default=None, alias="actionId")
    action_uid: str = Field(alias="actionUid")
    status: str
    reason_code: str | None = Field(default=None, alias="reasonCode")


class DebateMessageCreatedTrigger(CamelModel):
    event: Literal["DebateMessageCreated"] = "DebateMessageCreated"
    session_id: int = Field(alias="sessionId")
    message_id: int = Field(alias="messageId")
    user_id: int = Field(alias="userId")
    side: DebateSide
    content: str
    created_at: str = Field(alias="createdAt")
    source_event_id: str | None = Field(default=None, alias="sourceEventId")


class DebateNpcPublicCallCreatedTrigger(CamelModel):
    event: Literal["DebateNpcPublicCallCreated"] = "DebateNpcPublicCallCreated"
    session_id: int = Field(alias="sessionId")
    public_call_id: int = Field(alias="publicCallId")
    user_id: int = Field(alias="userId")
    npc_id: str = Field(alias="npcId")
    call_type: str = Field(alias="callType")
    content: str
    created_at: str = Field(alias="createdAt")
    source_event_id: str | None = Field(default=None, alias="sourceEventId")


NpcEventTrigger = DebateMessageCreatedTrigger | DebateNpcPublicCallCreatedTrigger


class NpcEventProcessingRun(CamelModel):
    status: Literal[
        "submitted",
        "candidate_rejected",
        "silent",
        "decision_rejected",
        "submit_failed",
    ]
    trigger: NpcEventTrigger
    decision_run: NpcDecisionRun = Field(alias="decisionRun")
    submit_result: SubmitActionCandidateOutput | None = Field(default=None, alias="submitResult")
    submit_attempts: int = Field(default=0, alias="submitAttempts")
    failures: list[str] = Field(default_factory=list)
