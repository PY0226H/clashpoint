from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from typing import Any, cast

from pydantic import ValidationError

from .models import (
    DebateMessageSnapshot,
    NpcActionCandidate,
    NpcActionType,
    NpcDecisionContext,
    NpcStatus,
)
from .settings import Settings

MAX_PUBLIC_TEXT_CHARS = 500
MAX_EFFECT_KIND_CHARS = 48
MAX_REASON_CODE_CHARS = 80

ALLOWED_ACTION_TYPES: set[str] = {"speak", "praise", "effect", "state_changed"}
ALLOWED_NPC_STATUSES: set[str] = {
    "observing",
    "speaking",
    "praising",
    "silent",
    "manual_takeover",
    "unavailable",
}

FORBIDDEN_OFFICIAL_FIELDS: set[str] = {
    "officialverdict",
    "officialverdictreport",
    "verdict",
    "verdictledger",
    "judgereport",
    "judgetrace",
    "panelvotes",
    "winner",
    "proscore",
    "conscore",
    "score",
    "dimensionscore",
    "dimensionscores",
    "finalrationale",
    "verdictsummary",
    "verdictevidencerefs",
    "reviewdecision",
    "confidence",
}


class NpcGuardError(ValueError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def normalize_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def assert_no_forbidden_fields(value: object, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = normalize_key(key)
            if normalized in FORBIDDEN_OFFICIAL_FIELDS:
                raise NpcGuardError(
                    "official_verdict_field_forbidden",
                    f"forbidden official verdict field at {path}.{key}",
                )
            assert_no_forbidden_fields(child, path=f"{path}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for index, child in enumerate(value):
            assert_no_forbidden_fields(child, path=f"{path}[{index}]")


def build_action_uid(
    *,
    context: NpcDecisionContext,
    action_type: str,
    policy_version: str,
    executor_version: str,
) -> str:
    seed_parts = [
        str(context.session_id),
        context.npc_id,
        str(context.source_event_id or ""),
        str(context.trigger_message.message_id if context.trigger_message else ""),
        action_type,
        policy_version,
        executor_version,
    ]
    digest = hashlib.sha256("|".join(seed_parts).encode("utf-8")).hexdigest()[:24]
    return f"npc_action:{digest}"


def candidate_from_raw_output(
    raw: Mapping[str, Any],
    *,
    context: NpcDecisionContext,
    settings: Settings,
    executor_kind: str,
    executor_version: str,
    trace_id: str | None = None,
) -> NpcActionCandidate:
    assert_no_forbidden_fields(raw)
    action_type = _coerce_action_type(_get(raw, "actionType", "action_type", "type"))
    public_text = _normalize_public_text(_get(raw, "publicText", "public_text", "text"))
    target_message = _resolve_target_message(raw, context)
    effect_kind = _normalize_optional_token(
        _get(raw, "effectKind", "effect_kind"),
        max_chars=MAX_EFFECT_KIND_CHARS,
        reason_code="effect_kind_too_long",
        field_name="effectKind",
    )
    reason_code = _normalize_optional_token(
        _get(raw, "reasonCode", "reason_code"),
        max_chars=MAX_REASON_CODE_CHARS,
        reason_code="reason_code_too_long",
        field_name="reasonCode",
    )
    npc_status = _coerce_npc_status(
        _get(raw, "npcStatus", "npc_status"),
        action_type=action_type,
    )
    _validate_action_semantics(
        action_type=action_type,
        public_text=public_text,
        target_message=target_message,
        effect_kind=effect_kind,
    )
    try:
        return NpcActionCandidate(
            actionUid=build_action_uid(
                context=context,
                action_type=action_type,
                policy_version=settings.npc_policy_version,
                executor_version=executor_version,
            ),
            sessionId=context.session_id,
            npcId=context.npc_id or settings.npc_id,
            actionType=action_type,
            publicText=public_text,
            targetMessageId=target_message.message_id if target_message else None,
            targetUserId=target_message.user_id if target_message else None,
            targetSide=target_message.side if target_message else None,
            effectKind=effect_kind,
            npcStatus=npc_status,
            reasonCode=reason_code,
            sourceEventId=context.source_event_id,
            sourceMessageId=context.trigger_message.message_id if context.trigger_message else None,
            policyVersion=settings.npc_policy_version,
            executorKind=executor_kind,
            executorVersion=executor_version,
            traceId=trace_id,
        )
    except ValidationError as err:
        raise NpcGuardError("candidate_schema_invalid", str(err)) from err


def _get(raw: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in raw:
            return raw[key]
    return None


def _coerce_action_type(value: object) -> NpcActionType:
    token = str(value or "").strip().lower()
    if token not in ALLOWED_ACTION_TYPES:
        raise NpcGuardError("action_type_invalid", f"invalid actionType: {value!r}")
    return cast(NpcActionType, token)


def _coerce_npc_status(value: object, *, action_type: str) -> NpcStatus:
    token = str(value or "").strip().lower()
    if token in ALLOWED_NPC_STATUSES:
        return cast(NpcStatus, token)
    if action_type == "speak":
        return "speaking"
    if action_type == "praise":
        return "praising"
    if action_type == "state_changed":
        return "observing"
    return "observing"


def _normalize_public_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > MAX_PUBLIC_TEXT_CHARS:
        raise NpcGuardError(
            "public_text_too_long",
            f"publicText must be <= {MAX_PUBLIC_TEXT_CHARS} chars",
        )
    return text


def _normalize_optional_token(
    value: object,
    *,
    max_chars: int,
    reason_code: str,
    field_name: str,
) -> str | None:
    if value is None:
        return None
    token = str(value).strip()
    if not token:
        return None
    if len(token) > max_chars:
        raise NpcGuardError(reason_code, f"{field_name} must be <= {max_chars} chars")
    return token


def _resolve_target_message(
    raw: Mapping[str, Any],
    context: NpcDecisionContext,
) -> DebateMessageSnapshot | None:
    target_message_id = _coerce_int(_get(raw, "targetMessageId", "target_message_id"))
    if target_message_id is None:
        return context.trigger_message
    for message in [context.trigger_message, *context.recent_messages]:
        if message and message.message_id == target_message_id:
            return message
    raise NpcGuardError("target_message_not_in_context", "target message not found in context")


def _coerce_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        raise NpcGuardError("target_message_id_invalid", "targetMessageId must be integer")


def _validate_action_semantics(
    *,
    action_type: str,
    public_text: str | None,
    target_message: DebateMessageSnapshot | None,
    effect_kind: str | None,
) -> None:
    if action_type in {"speak", "praise"} and public_text is None:
        raise NpcGuardError("public_text_required", f"{action_type} requires publicText")
    if action_type == "praise" and target_message is None:
        raise NpcGuardError("praise_target_required", "praise requires target message")
    if action_type == "effect" and effect_kind is None:
        raise NpcGuardError("effect_kind_required", "effect requires effectKind")
