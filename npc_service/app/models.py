from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DebateSide = Literal["pro", "con"]
NpcActionType = Literal["speak", "praise", "effect", "state_changed"]
NpcStatus = Literal["observing", "speaking", "praising", "silent", "unavailable"]


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


class NpcDecisionContext(CamelModel):
    session_id: int = Field(alias="sessionId")
    npc_id: str = Field(default="virtual_judge_default", alias="npcId")
    source_event_id: str | None = Field(default=None, alias="sourceEventId")
    trigger_message: DebateMessageSnapshot | None = Field(default=None, alias="triggerMessage")
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
