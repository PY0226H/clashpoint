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

from helpers import make_context, make_message, make_settings


class FakeProvider:
    def __init__(self, output: dict[str, Any] | Exception) -> None:
        self.output = output

    async def generate_action(self, context: NpcDecisionContext) -> dict[str, Any]:
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


def _make_router(provider: FakeProvider, *, rule_fallback_enabled: bool = True) -> NpcExecutorRouter:
    settings = make_settings(rule_fallback_enabled=rule_fallback_enabled)
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
