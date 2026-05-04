from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .guard import NpcGuardError, candidate_from_raw_output
from .models import NpcActionCandidate, NpcDecisionContext, NpcDecisionRun
from .openai_provider import LlmActionProvider, OpenAICompatibleProvider
from .settings import Settings

LLM_EXECUTOR_KIND = "llm_executor_v1"
LLM_EXECUTOR_VERSION = "llm_executor_v1"
RULE_EXECUTOR_KIND = "rule_executor_v1"
RULE_EXECUTOR_VERSION = "rule_executor_v1"


class ExecutorUnavailable(RuntimeError):
    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


class LlmExecutorV1:
    def __init__(self, *, settings: Settings, provider: LlmActionProvider) -> None:
        self._settings = settings
        self._provider = provider

    async def decide(self, context: NpcDecisionContext) -> NpcActionCandidate:
        if not self._settings.llm_enabled:
            raise ExecutorUnavailable("llm_disabled")
        if not self._settings.openai.configured:
            raise ExecutorUnavailable("llm_not_configured")
        raw = await self._provider.generate_action(context)
        return candidate_from_raw_output(
            raw,
            context=context,
            settings=self._settings,
            executor_kind=LLM_EXECUTOR_KIND,
            executor_version=LLM_EXECUTOR_VERSION,
        )


class RuleExecutorV1:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

    async def decide(
        self,
        context: NpcDecisionContext,
        *,
        fallback_reason: str | None,
    ) -> NpcActionCandidate | None:
        if context.trigger_message is None:
            return None
        raw = self._rule_output(context, fallback_reason=fallback_reason)
        return candidate_from_raw_output(
            raw,
            context=context,
            settings=self._settings,
            executor_kind=RULE_EXECUTOR_KIND,
            executor_version=RULE_EXECUTOR_VERSION,
        )

    def _rule_output(
        self,
        context: NpcDecisionContext,
        *,
        fallback_reason: str | None,
    ) -> Mapping[str, Any]:
        trigger = context.trigger_message
        assert trigger is not None
        content = trigger.content.strip()
        if len(content) >= 16:
            return {
                "actionType": "praise",
                "publicText": "这段发言抓住了争议焦点，力度不错。",
                "targetMessageId": trigger.message_id,
                "effectKind": "sparkle",
                "npcStatus": "praising",
                "reasonCode": "rule_fallback_praise",
            }
        return {
            "actionType": "state_changed",
            "npcStatus": "observing",
            "reasonCode": fallback_reason or "rule_fallback_observing",
        }


class NpcExecutorRouter:
    def __init__(
        self,
        *,
        settings: Settings,
        llm_executor: LlmExecutorV1,
        rule_executor: RuleExecutorV1,
    ) -> None:
        self._settings = settings
        self._llm_executor = llm_executor
        self._rule_executor = rule_executor

    async def decide(self, context: NpcDecisionContext) -> NpcDecisionRun:
        failures: list[str] = []
        try:
            candidate = await self._llm_executor.decide(context)
            return NpcDecisionRun(
                status="created",
                executorKind=LLM_EXECUTOR_KIND,
                executorVersion=LLM_EXECUTOR_VERSION,
                fallbackUsed=False,
                candidate=candidate,
                failures=failures,
            )
        except Exception as err:
            failure_reason = _failure_reason(err)
            failures.append(f"{LLM_EXECUTOR_KIND}:{failure_reason}")
            if not self._settings.rule_fallback_enabled:
                return NpcDecisionRun(
                    status="rejected",
                    executorKind=LLM_EXECUTOR_KIND,
                    executorVersion=LLM_EXECUTOR_VERSION,
                    fallbackUsed=False,
                    fallbackReason=failure_reason,
                    guardReason=_guard_reason(err),
                    failures=failures,
                )
        try:
            fallback_reason = failures[-1].split(":", 1)[1] if failures else None
            candidate = await self._rule_executor.decide(
                context,
                fallback_reason=fallback_reason,
            )
            if candidate is None:
                return NpcDecisionRun(
                    status="silent",
                    executorKind=RULE_EXECUTOR_KIND,
                    executorVersion=RULE_EXECUTOR_VERSION,
                    fallbackUsed=True,
                    fallbackReason=fallback_reason,
                    failures=failures,
                )
            return NpcDecisionRun(
                status="fallback",
                executorKind=RULE_EXECUTOR_KIND,
                executorVersion=RULE_EXECUTOR_VERSION,
                fallbackUsed=True,
                fallbackReason=fallback_reason,
                candidate=candidate,
                failures=failures,
            )
        except Exception as err:
            failure_reason = _failure_reason(err)
            failures.append(f"{RULE_EXECUTOR_KIND}:{failure_reason}")
            return NpcDecisionRun(
                status="rejected",
                executorKind=RULE_EXECUTOR_KIND,
                executorVersion=RULE_EXECUTOR_VERSION,
                fallbackUsed=True,
                fallbackReason=failure_reason,
                guardReason=_guard_reason(err),
                failures=failures,
            )


def create_default_router(settings: Settings) -> NpcExecutorRouter:
    provider = OpenAICompatibleProvider(settings)
    return NpcExecutorRouter(
        settings=settings,
        llm_executor=LlmExecutorV1(settings=settings, provider=provider),
        rule_executor=RuleExecutorV1(settings=settings),
    )


def _failure_reason(err: Exception) -> str:
    if isinstance(err, NpcGuardError | ExecutorUnavailable):
        return err.reason_code
    message = str(err).strip()
    if not message:
        return err.__class__.__name__
    return f"{err.__class__.__name__}:{message}"[:200]


def _guard_reason(err: Exception) -> str | None:
    if isinstance(err, NpcGuardError):
        return err.reason_code
    return None
