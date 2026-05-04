from __future__ import annotations

import asyncio
from typing import Any

from app.executors import (
    LLM_EXECUTOR_KIND,
    RULE_EXECUTOR_KIND,
    LlmExecutorV1,
    NpcExecutorRouter,
    RuleExecutorV1,
)
from app.models import NpcDecisionContext

from helpers import make_context, make_message, make_public_call, make_settings


class FakeProvider:
    def __init__(self, output: dict[str, Any] | Exception) -> None:
        self.output = output
        self.call_count = 0

    async def generate_action(self, context: NpcDecisionContext) -> dict[str, Any]:
        self.call_count += 1
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


def _make_router(
    provider: FakeProvider,
    *,
    rule_fallback_enabled: bool = True,
    **settings_kwargs: Any,
) -> NpcExecutorRouter:
    settings = make_settings(
        rule_fallback_enabled=rule_fallback_enabled,
        **settings_kwargs,
    )
    return NpcExecutorRouter(
        settings=settings,
        llm_executor=LlmExecutorV1(settings=settings, provider=provider),
        rule_executor=RuleExecutorV1(settings=settings),
    )


def test_router_uses_llm_executor_for_valid_structured_action() -> None:
    async def scenario() -> None:
        router = _make_router(
            FakeProvider(
                {
                    "actionType": "praise",
                    "publicText": "这个反击很清楚。",
                    "targetMessageId": 1001,
                    "npcStatus": "praising",
                    "reasonCode": "llm_praise",
                    "_openaiUsage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 4,
                        "total_tokens": 14,
                    },
                    "_openaiModel": "test-model",
                }
            )
        )

        run = await router.decide(make_context())

        assert run.status == "created"
        assert run.executor_kind == LLM_EXECUTOR_KIND
        assert run.fallback_used is False
        assert run.candidate is not None
        assert run.candidate.executor_kind == LLM_EXECUTOR_KIND
        assert run.candidate.public_text == "这个反击很清楚。"
        assert run.llm_token_usage is not None
        assert run.llm_token_usage.total_tokens == 14
        assert run.llm_model == "test-model"
        assert router.metrics_snapshot().llm_success_total == 1

    asyncio.run(scenario())


def test_router_falls_back_to_rule_executor_when_llm_fails() -> None:
    async def scenario() -> None:
        router = _make_router(FakeProvider(RuntimeError("timeout")))

        run = await router.decide(make_context())

        assert run.status == "fallback"
        assert run.executor_kind == RULE_EXECUTOR_KIND
        assert run.fallback_used is True
        assert run.fallback_reason == "RuntimeError:timeout"
        assert run.candidate is not None
        assert run.candidate.executor_kind == RULE_EXECUTOR_KIND
        assert run.candidate.action_type == "praise"
        assert run.fallback_from_executor_kind == LLM_EXECUTOR_KIND
        assert run.llm_error_code == "RuntimeError:timeout"

    asyncio.run(scenario())


def test_router_falls_back_when_llm_output_violates_guard() -> None:
    async def scenario() -> None:
        router = _make_router(
            FakeProvider(
                {
                    "actionType": "praise",
                    "publicText": "这段很精彩。",
                    "targetMessageId": 1001,
                    "winner": "pro",
                }
            )
        )

        run = await router.decide(make_context())

        assert run.status == "fallback"
        assert run.fallback_reason == "official_verdict_field_forbidden"
        assert run.candidate is not None
        assert run.candidate.executor_kind == RULE_EXECUTOR_KIND
        assert router.metrics_snapshot().llm_guard_rejected_total == 1

    asyncio.run(scenario())


def test_router_rejects_when_guard_fails_and_rule_fallback_disabled() -> None:
    async def scenario() -> None:
        router = _make_router(
            FakeProvider({"actionType": "speak", "publicText": "正式裁决", "score": 99}),
            rule_fallback_enabled=False,
        )

        run = await router.decide(make_context())

        assert run.status == "rejected"
        assert run.executor_kind == LLM_EXECUTOR_KIND
        assert run.fallback_used is False
        assert run.guard_reason == "official_verdict_field_forbidden"
        assert run.candidate is None

    asyncio.run(scenario())


def test_router_opens_circuit_after_llm_provider_failure() -> None:
    async def scenario() -> None:
        provider = FakeProvider(RuntimeError("timeout"))
        router = _make_router(provider, llm_circuit_failure_threshold=1)

        first = await router.decide(make_context())
        second = await router.decide(make_context())

        assert first.fallback_reason == "RuntimeError:timeout"
        assert second.fallback_reason == "llm_circuit_open"
        assert provider.call_count == 1
        snapshot = router.metrics_snapshot()
        assert snapshot.llm_circuit_open_total == 1
        assert snapshot.llm_fallback_total == 2

    asyncio.run(scenario())


def test_router_canary_restricts_real_llm_to_allowed_sessions() -> None:
    async def scenario() -> None:
        provider = FakeProvider({"actionType": "speak", "publicText": "现场继续保持节奏。"})
        router = _make_router(
            provider,
            llm_canary_enabled=True,
            llm_canary_session_ids=(999,),
        )

        run = await router.decide(make_context())

        assert run.status == "fallback"
        assert run.fallback_reason == "llm_canary_session_not_allowed"
        assert provider.call_count == 0
        assert router.metrics_snapshot().llm_canary_enabled is True

    asyncio.run(scenario())


def test_router_treats_llm_no_action_as_silent_without_rule_fallback() -> None:
    async def scenario() -> None:
        router = _make_router(
            FakeProvider(
                {
                    "actionType": "no_action",
                    "reasonCode": "stay_quiet",
                    "_openaiUsage": {"prompt_tokens": 2, "completion_tokens": 1},
                }
            )
        )

        run = await router.decide(make_context())

        assert run.status == "silent"
        assert run.executor_kind == LLM_EXECUTOR_KIND
        assert run.fallback_used is False
        assert run.guard_reason == "llm_no_action"
        assert router.metrics_snapshot().llm_no_action_total == 1

    asyncio.run(scenario())


def test_router_enforces_room_cost_limit_after_recording_usage() -> None:
    async def scenario() -> None:
        provider = FakeProvider(
            {
                "actionType": "speak",
                "publicText": "现场节奏不错，继续围绕证据展开。",
                "_openaiUsage": {
                    "prompt_tokens": 4,
                    "completion_tokens": 3,
                    "total_tokens": 7,
                },
            }
        )
        router = _make_router(
            provider,
            input_token_cost_microusd=10,
            output_token_cost_microusd=20,
            llm_room_cost_limit_microusd=100,
        )

        first = await router.decide(make_context())
        second = await router.decide(make_context())

        assert first.status == "created"
        assert first.llm_estimated_cost_microusd == 100
        assert second.status == "fallback"
        assert second.fallback_reason == "llm_room_cost_limit_exceeded"
        assert provider.call_count == 1
        assert router.metrics_snapshot().llm_estimated_cost_microusd_by_session == {"77": 100}

    asyncio.run(scenario())


def test_router_returns_silent_when_llm_fails_without_trigger_message() -> None:
    async def scenario() -> None:
        router = _make_router(FakeProvider(RuntimeError("rate limit")))

        run = await router.decide(make_context(trigger_message=None))

        assert run.status == "silent"
        assert run.executor_kind == RULE_EXECUTOR_KIND
        assert run.fallback_used is True
        assert run.candidate is None

    asyncio.run(scenario())


def test_rule_executor_can_emit_state_changed_for_short_trigger() -> None:
    async def scenario() -> None:
        settings = make_settings()
        rule = RuleExecutorV1(settings=settings)
        context = make_context(trigger_message=make_message(content="短句"))

        candidate = await rule.decide(context, fallback_reason="llm_not_configured")

        assert candidate is not None
        assert candidate.action_type == "state_changed"
        assert candidate.npc_status == "observing"
        assert candidate.public_text is None

    asyncio.run(scenario())


def test_rule_executor_can_answer_public_call_without_private_target() -> None:
    async def scenario() -> None:
        settings = make_settings()
        rule = RuleExecutorV1(settings=settings)
        context = make_context(trigger_message=None, public_call=make_public_call())

        candidate = await rule.decide(context, fallback_reason="llm_not_configured")

        assert candidate is not None
        assert candidate.action_type == "speak"
        assert candidate.public_text is not None
        assert candidate.target_message_id is None
        assert candidate.source_message_id is None
        assert candidate.reason_code == "rule_public_call_response"

    asyncio.run(scenario())
