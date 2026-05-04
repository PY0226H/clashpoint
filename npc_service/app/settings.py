from __future__ import annotations

import os
from dataclasses import dataclass


def parse_env_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    token = value.strip().lower()
    if token in {"1", "true", "yes", "on"}:
        return True
    if token in {"0", "false", "no", "off"}:
        return False
    return default


def parse_env_int(value: str | None, *, default: int, minimum: int | None = None) -> int:
    try:
        parsed = int(value) if value is not None else default
    except ValueError:
        parsed = default
    if minimum is not None:
        return max(minimum, parsed)
    return parsed


def parse_env_float(value: str | None, *, default: float, minimum: float | None = None) -> float:
    try:
        parsed = float(value) if value is not None else default
    except ValueError:
        parsed = default
    if minimum is not None:
        return max(minimum, parsed)
    return parsed


@dataclass(frozen=True)
class OpenAIProviderSettings:
    provider_name: str
    api_key: str
    model: str
    base_url: str
    timeout_secs: float
    temperature: float
    max_retries: int
    max_output_tokens: int
    input_token_cost_microusd: int
    output_token_cost_microusd: int

    @property
    def configured(self) -> bool:
        return bool(self.api_key.strip())


@dataclass(frozen=True)
class EventConsumerSettings:
    enabled: bool
    webhook_enabled: bool
    source: str
    brokers: str
    topic_prefix: str
    consume_topics: tuple[str, ...]
    group_id: str
    client_id: str
    max_attempts: int
    retry_backoff_ms: int
    dlq_path: str


@dataclass(frozen=True)
class LlmRuntimeSettings:
    canary_enabled: bool
    canary_session_ids: tuple[int, ...]
    circuit_failure_threshold: int
    circuit_cooldown_secs: float
    daily_cost_limit_microusd: int
    room_cost_limit_microusd: int


@dataclass(frozen=True)
class Settings:
    service_name: str
    ai_internal_key: str
    chat_server_base_url: str
    chat_action_candidate_path: str
    chat_context_path_template: str
    event_submit_max_attempts: int
    event_submit_retry_backoff_ms: int
    npc_id: str
    npc_policy_version: str
    npc_prompt_version: str
    llm_enabled: bool
    rule_fallback_enabled: bool
    llm_runtime: LlmRuntimeSettings
    event_consumer: EventConsumerSettings
    openai: OpenAIProviderSettings


def parse_env_csv(value: str | None, *, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None:
        return default
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    return items or default


def parse_env_int_csv(value: str | None, *, default: tuple[int, ...]) -> tuple[int, ...]:
    if value is None:
        return default
    parsed: list[int] = []
    for item in value.split(","):
        token = item.strip()
        if not token:
            continue
        try:
            parsed.append(int(token))
        except ValueError:
            continue
    return tuple(parsed) or default


def load_settings() -> Settings:
    event_consumer = EventConsumerSettings(
        enabled=parse_env_bool(os.getenv("NPC_EVENT_CONSUMER_ENABLED"), default=False),
        webhook_enabled=parse_env_bool(os.getenv("NPC_EVENT_WEBHOOK_ENABLED"), default=False),
        source=os.getenv("NPC_EVENT_CONSUMER_SOURCE", "kafka"),
        brokers=os.getenv("NPC_KAFKA_BROKERS", "127.0.0.1:9092"),
        topic_prefix=os.getenv("NPC_KAFKA_TOPIC_PREFIX", "echoisle"),
        consume_topics=parse_env_csv(
            os.getenv("NPC_KAFKA_CONSUME_TOPICS"),
            default=(
                "debate.message.created.v1",
                "debate.npc.public_call.created.v1",
            ),
        ),
        group_id=os.getenv("NPC_KAFKA_GROUP_ID", "npc-service"),
        client_id=os.getenv("NPC_KAFKA_CLIENT_ID", "npc-service"),
        max_attempts=max(1, int(os.getenv("NPC_EVENT_CONSUMER_MAX_ATTEMPTS", "3"))),
        retry_backoff_ms=max(0, int(os.getenv("NPC_EVENT_CONSUMER_RETRY_BACKOFF_MS", "500"))),
        dlq_path=os.getenv("NPC_EVENT_CONSUMER_DLQ_PATH", "npc_service_dlq.jsonl"),
    )
    return Settings(
        service_name=os.getenv("NPC_SERVICE_NAME", "npc_service"),
        ai_internal_key=os.getenv("AI_JUDGE_INTERNAL_KEY", "dev-ai-internal-key"),
        chat_server_base_url=os.getenv("CHAT_SERVER_BASE_URL", "http://127.0.0.1:6688"),
        chat_action_candidate_path=os.getenv(
            "NPC_CHAT_ACTION_CANDIDATE_PATH",
            "/api/internal/ai/debate/npc/actions/candidates",
        ),
        chat_context_path_template=os.getenv(
            "NPC_CHAT_CONTEXT_PATH_TEMPLATE",
            "/api/internal/ai/debate/npc/sessions/{session_id}/context",
        ),
        event_submit_max_attempts=max(1, int(os.getenv("NPC_EVENT_SUBMIT_MAX_ATTEMPTS", "2"))),
        event_submit_retry_backoff_ms=max(
            0,
            int(os.getenv("NPC_EVENT_SUBMIT_RETRY_BACKOFF_MS", "100")),
        ),
        npc_id=os.getenv("NPC_SERVICE_NPC_ID", "virtual_judge_default"),
        npc_policy_version=os.getenv("NPC_SERVICE_POLICY_VERSION", "npc_policy_v1"),
        npc_prompt_version=os.getenv("NPC_SERVICE_PROMPT_VERSION", "npc_prompt_v1"),
        llm_enabled=parse_env_bool(os.getenv("NPC_SERVICE_LLM_ENABLED"), default=True),
        rule_fallback_enabled=parse_env_bool(
            os.getenv("NPC_SERVICE_RULE_FALLBACK_ENABLED"),
            default=True,
        ),
        llm_runtime=LlmRuntimeSettings(
            canary_enabled=parse_env_bool(
                os.getenv("NPC_SERVICE_LLM_CANARY_ENABLED"),
                default=False,
            ),
            canary_session_ids=parse_env_int_csv(
                os.getenv("NPC_SERVICE_LLM_CANARY_SESSION_IDS"),
                default=(),
            ),
            circuit_failure_threshold=parse_env_int(
                os.getenv("NPC_SERVICE_LLM_CIRCUIT_FAILURE_THRESHOLD"),
                default=3,
                minimum=1,
            ),
            circuit_cooldown_secs=parse_env_float(
                os.getenv("NPC_SERVICE_LLM_CIRCUIT_COOLDOWN_SECS"),
                default=60.0,
                minimum=0.0,
            ),
            daily_cost_limit_microusd=parse_env_int(
                os.getenv("NPC_SERVICE_LLM_DAILY_COST_LIMIT_MICRO_USD"),
                default=0,
                minimum=0,
            ),
            room_cost_limit_microusd=parse_env_int(
                os.getenv("NPC_SERVICE_LLM_ROOM_COST_LIMIT_MICRO_USD"),
                default=0,
                minimum=0,
            ),
        ),
        event_consumer=event_consumer,
        openai=OpenAIProviderSettings(
            provider_name=os.getenv("NPC_OPENAI_PROVIDER_NAME", "openai-compatible"),
            api_key=os.getenv("NPC_OPENAI_API_KEY", ""),
            model=os.getenv("NPC_OPENAI_MODEL", "gpt-4.1-mini"),
            base_url=os.getenv("NPC_OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            timeout_secs=parse_env_float(
                os.getenv("NPC_OPENAI_TIMEOUT_SECS"),
                default=12.0,
                minimum=0.1,
            ),
            temperature=parse_env_float(
                os.getenv("NPC_OPENAI_TEMPERATURE"),
                default=0.4,
                minimum=0.0,
            ),
            max_retries=parse_env_int(
                os.getenv("NPC_OPENAI_MAX_RETRIES"),
                default=1,
                minimum=1,
            ),
            max_output_tokens=parse_env_int(
                os.getenv("NPC_OPENAI_MAX_OUTPUT_TOKENS"),
                default=500,
                minimum=64,
            ),
            input_token_cost_microusd=parse_env_int(
                os.getenv("NPC_OPENAI_INPUT_TOKEN_COST_MICRO_USD"),
                default=0,
                minimum=0,
            ),
            output_token_cost_microusd=parse_env_int(
                os.getenv("NPC_OPENAI_OUTPUT_TOKEN_COST_MICRO_USD"),
                default=0,
                minimum=0,
            ),
        ),
    )
