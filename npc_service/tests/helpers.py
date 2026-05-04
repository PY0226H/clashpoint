from __future__ import annotations

from app.models import DebateMessageSnapshot, NpcDecisionContext
from app.settings import OpenAIProviderSettings, Settings


def make_settings(
    *,
    api_key: str = "test-openai-key",
    llm_enabled: bool = True,
    rule_fallback_enabled: bool = True,
) -> Settings:
    return Settings(
        service_name="npc_service_test",
        ai_internal_key="test-internal-key",
        chat_server_base_url="http://chat.test",
        chat_action_candidate_path="/api/internal/ai/debate/npc/actions/candidates",
        npc_id="virtual_judge_default",
        npc_policy_version="npc_policy_test",
        llm_enabled=llm_enabled,
        rule_fallback_enabled=rule_fallback_enabled,
        openai=OpenAIProviderSettings(
            api_key=api_key,
            model="test-model",
            base_url="http://openai.test/v1",
            timeout_secs=1.0,
            temperature=0.2,
            max_retries=1,
            max_output_tokens=256,
        ),
    )


def make_message(
    *,
    message_id: int = 1001,
    content: str = "这段发言把核心矛盾说清楚了，值得回应。",
) -> DebateMessageSnapshot:
    return DebateMessageSnapshot(
        messageId=message_id,
        sessionId=77,
        userId=42,
        side="pro",
        content=content,
        createdAt="2026-05-03T00:00:00Z",
    )


_DEFAULT_TRIGGER: object = object()


def make_context(
    *,
    trigger_message: DebateMessageSnapshot | None | object = _DEFAULT_TRIGGER,
) -> NpcDecisionContext:
    trigger = make_message() if trigger_message is _DEFAULT_TRIGGER else trigger_message
    assert trigger is None or isinstance(trigger, DebateMessageSnapshot)
    return NpcDecisionContext(
        sessionId=77,
        npcId="virtual_judge_default",
        sourceEventId="evt-1",
        triggerMessage=trigger,
        recentMessages=[trigger] if trigger is not None else [],
        now="2026-05-03T00:00:01Z",
    )
