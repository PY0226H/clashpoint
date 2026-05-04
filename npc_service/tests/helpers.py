from __future__ import annotations

from app.models import (
    DebateMessageCreatedTrigger,
    DebateMessageSnapshot,
    DebateNpcPublicCallCreatedTrigger,
    NpcDecisionContext,
    NpcPublicCallSnapshot,
    NpcRoomConfig,
)
from app.settings import EventConsumerSettings, LlmRuntimeSettings, OpenAIProviderSettings, Settings


def make_settings(
    *,
    api_key: str = "test-openai-key",
    llm_enabled: bool = True,
    rule_fallback_enabled: bool = True,
    llm_canary_enabled: bool = False,
    llm_canary_session_ids: tuple[int, ...] = (),
    llm_circuit_failure_threshold: int = 3,
    llm_circuit_cooldown_secs: float = 60.0,
    llm_daily_cost_limit_microusd: int = 0,
    llm_room_cost_limit_microusd: int = 0,
    input_token_cost_microusd: int = 0,
    output_token_cost_microusd: int = 0,
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
        npc_prompt_version="npc_prompt_test",
        llm_enabled=llm_enabled,
        rule_fallback_enabled=rule_fallback_enabled,
        llm_runtime=LlmRuntimeSettings(
            canary_enabled=llm_canary_enabled,
            canary_session_ids=llm_canary_session_ids,
            circuit_failure_threshold=llm_circuit_failure_threshold,
            circuit_cooldown_secs=llm_circuit_cooldown_secs,
            daily_cost_limit_microusd=llm_daily_cost_limit_microusd,
            room_cost_limit_microusd=llm_room_cost_limit_microusd,
        ),
        event_consumer=EventConsumerSettings(
            enabled=event_consumer_enabled,
            webhook_enabled=event_webhook_enabled,
            source="kafka",
            brokers="127.0.0.1:9092",
            topic_prefix="echoisle",
            consume_topics=(
                "debate.message.created.v1",
                "debate.npc.public_call.created.v1",
            ),
            group_id="npc-service-test",
            client_id="npc-service-test",
            max_attempts=event_consumer_max_attempts,
            retry_backoff_ms=0,
            dlq_path=event_consumer_dlq_path,
        ),
        openai=OpenAIProviderSettings(
            provider_name="openai-compatible-test",
            api_key=api_key,
            model="test-model",
            base_url="http://openai.test/v1",
            timeout_secs=1.0,
            temperature=0.2,
            max_retries=1,
            max_output_tokens=256,
            input_token_cost_microusd=input_token_cost_microusd,
            output_token_cost_microusd=output_token_cost_microusd,
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
    public_call: NpcPublicCallSnapshot | None = None,
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
        publicCall=public_call,
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
    allow_public_call: bool = False,
    allow_pause: bool = False,
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
        allowPublicCall=allow_public_call,
        allowPause=allow_pause,
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


def make_public_call(*, call_type: str = "issue_summary") -> NpcPublicCallSnapshot:
    return NpcPublicCallSnapshot(
        publicCallId=3001,
        sessionId=77,
        userId=42,
        npcId="virtual_judge_default",
        callType=call_type,
        content="帮忙总结一下当前争议焦点。",
        status="queued",
        createdAt="2026-05-03T00:00:02Z",
    )


def make_public_call_trigger(*, call_type: str = "issue_summary") -> DebateNpcPublicCallCreatedTrigger:
    return DebateNpcPublicCallCreatedTrigger(
        event="DebateNpcPublicCallCreated",
        sessionId=77,
        publicCallId=3001,
        userId=42,
        npcId="virtual_judge_default",
        callType=call_type,
        content="帮忙总结一下当前争议焦点。",
        createdAt="2026-05-03T00:00:02Z",
        sourceEventId="evt-call-1",
    )
