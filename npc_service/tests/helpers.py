from __future__ import annotations

from app.models import (
    DebateMessageCreatedTrigger,
    DebateMessageSnapshot,
    NpcDecisionContext,
    NpcRoomConfig,
)
from app.settings import EventConsumerSettings, OpenAIProviderSettings, Settings


def make_settings(
    *,
    api_key: str = "test-openai-key",
    llm_enabled: bool = True,
    rule_fallback_enabled: bool = True,
    event_submit_max_attempts: int = 2,
    event_consumer_enabled: bool = False,
    event_webhook_enabled: bool = True,
    event_consumer_max_attempts: int = 3,
    event_consumer_dlq_path: str = "npc_service_test_dlq.jsonl",
) -> Settings:
    return Settings(
        service_name="npc_service_test",
        ai_internal_key="test-internal-key",
        chat_server_base_url="http://chat.test",
        chat_action_candidate_path="/api/internal/ai/debate/npc/actions/candidates",
        chat_context_path_template="/api/internal/ai/debate/npc/sessions/{session_id}/context",
        event_submit_max_attempts=event_submit_max_attempts,
        event_submit_retry_backoff_ms=0,
        npc_id="virtual_judge_default",
        npc_policy_version="npc_policy_test",
        llm_enabled=llm_enabled,
        rule_fallback_enabled=rule_fallback_enabled,
        event_consumer=EventConsumerSettings(
            enabled=event_consumer_enabled,
            webhook_enabled=event_webhook_enabled,
            source="kafka",
            brokers="127.0.0.1:9092",
            topic_prefix="echoisle",
            consume_topics=("debate.message.created.v1",),
            group_id="npc-service-test",
            client_id="npc-service-test",
            max_attempts=event_consumer_max_attempts,
            retry_backoff_ms=0,
            dlq_path=event_consumer_dlq_path,
        ),
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
    room_config: NpcRoomConfig | None = None,
) -> NpcDecisionContext:
    trigger = make_message() if trigger_message is _DEFAULT_TRIGGER else trigger_message
    assert trigger is None or isinstance(trigger, DebateMessageSnapshot)
    return NpcDecisionContext(
        sessionId=77,
        npcId="virtual_judge_default",
        roomConfig=room_config or make_room_config(),
        sourceEventId="evt-1",
        triggerMessage=trigger,
        recentMessages=[trigger] if trigger is not None else [],
        now="2026-05-03T00:00:01Z",
    )


def make_room_config(
    *,
    enabled: bool = True,
    status: str = "active",
    allow_speak: bool = True,
    allow_praise: bool = True,
    allow_effect: bool = True,
) -> NpcRoomConfig:
    return NpcRoomConfig(
        sessionId=77,
        npcId="virtual_judge_default",
        displayName="虚拟裁判",
        enabled=enabled,
        personaStyle="balanced_host",
        status=status,
        allowSpeak=allow_speak,
        allowPraise=allow_praise,
        allowEffect=allow_effect,
        allowStateChange=True,
        allowWarning=True,
        allowPublicCall=False,
        allowPause=False,
        manualTakeoverByUserId=None,
        statusReason=None,
        updatedByUserId=None,
        createdAt="2026-05-03T00:00:00Z",
        updatedAt="2026-05-03T00:00:00Z",
    )


def make_trigger() -> DebateMessageCreatedTrigger:
    return DebateMessageCreatedTrigger(
        event="DebateMessageCreated",
        sessionId=77,
        messageId=1001,
        userId=42,
        side="pro",
        content="这段发言把核心矛盾说清楚了，值得回应。",
        createdAt="2026-05-03T00:00:00Z",
        sourceEventId="evt-1",
    )
