from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .guard import NpcGuardError, NpcNoAction, candidate_from_raw_output
from .llm_runtime import LlmRunTelemetry, NpcRuntimeMetrics, build_llm_telemetry
from .models import LlmTokenUsage, NpcActionCandidate, NpcDecisionContext, NpcDecisionRun
from .openai_provider import LlmActionProvider, OpenAICompatibleProvider, OpenAIProviderError
from .settings import Settings

LLM_EXECUTOR_KIND = "llm_executor_v1"
LLM_EXECUTOR_VERSION = "llm_executor_v1"
RULE_EXECUTOR_KIND = "rule_executor_v1"
RULE_EXECUTOR_VERSION = "rule_executor_v1"


class ExecutorUnavailable(RuntimeError):
    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True)
class LlmDecisionResult:
    candidate: NpcActionCandidate
    telemetry: LlmRunTelemetry


class LlmExecutorError(RuntimeError):
    def __init__(
        self,
        *,
        reason_code: str,
        telemetry: LlmRunTelemetry | None,
        guard_reason: str | None = None,
    ) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.telemetry = telemetry
        self.guard_reason = guard_reason


class LlmNoActionDecision(RuntimeError):
    def __init__(self, *, telemetry: LlmRunTelemetry, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.telemetry = telemetry


class LlmExecutorV1:
    def __init__(self, *, settings: Settings, provider: LlmActionProvider) -> None:
        self._settings = settings
        self._provider = provider

    async def decide(self, context: NpcDecisionContext) -> LlmDecisionResult:
        if not self._settings.llm_enabled:
            raise ExecutorUnavailable("llm_disabled")
        if not self._settings.openai.configured:
            raise ExecutorUnavailable("llm_not_configured")
        started = time.perf_counter()
        try:
            raw = await self._provider.generate_action(context)
        except Exception as err:
            latency_ms = _elapsed_ms(started)
            raise LlmExecutorError(
                reason_code=_failure_reason(err),
                telemetry=_empty_llm_telemetry(self._settings, latency_ms=latency_ms),
            ) from err
        latency_ms = _elapsed_ms(started)
        telemetry = build_llm_telemetry(raw, settings=self._settings, latency_ms=latency_ms)
        try:
            candidate = candidate_from_raw_output(
                raw,
                context=context,
                settings=self._settings,
                executor_kind=LLM_EXECUTOR_KIND,
                executor_version=LLM_EXECUTOR_VERSION,
            )
        except NpcNoAction as err:
            raise LlmNoActionDecision(telemetry=telemetry, reason_code=err.reason_code) from err
        except NpcGuardError as err:
            raise LlmExecutorError(
                reason_code=err.reason_code,
                telemetry=telemetry,
                guard_reason=err.reason_code,
            ) from err
        return LlmDecisionResult(candidate=candidate, telemetry=telemetry)


class RuleExecutorV1:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

    async def decide(
        self,
        context: NpcDecisionContext,
        *,
        fallback_reason: str | None,
    ) -> NpcActionCandidate | None:
        if context.trigger_message is None and context.public_call is None:
            return None
        raw = self._rule_output(context, fallback_reason=fallback_reason)
        if raw is None:
            return None
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
    ) -> Mapping[str, Any] | None:
        if context.public_call is not None:
            call_type = context.public_call.call_type
            if call_type == "pause_review":
                if context.room_config.allow_pause:
                    return {
                        "actionType": "pause_suggestion",
                        "publicText": "我建议先短暂停一下，把当前争议焦点对齐后再继续。",
                        "npcStatus": "speaking",
                        "reasonCode": "rule_public_call_pause_review",
                    }
                if not context.room_config.allow_speak:
                    return None
                return {
                    "actionType": "speak",
                    "publicText": _public_call_reply(call_type),
                    "npcStatus": "speaking",
                    "reasonCode": "rule_public_call_response",
                }
            if call_type == "atmosphere_effect":
                return {
                    "actionType": "effect",
                    "effectKind": "sparkle",
                    "npcStatus": "observing",
                    "reasonCode": "rule_public_call_effect",
                }
            return {
                "actionType": "speak",
                "publicText": _public_call_reply(call_type),
                "npcStatus": "speaking",
                "reasonCode": "rule_public_call_response",
            }
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
        metrics: NpcRuntimeMetrics | None = None,
    ) -> None:
        self._settings = settings
        self._llm_executor = llm_executor
        self._rule_executor = rule_executor
        self._metrics = metrics or NpcRuntimeMetrics(settings=settings)

    async def decide(self, context: NpcDecisionContext) -> NpcDecisionRun:
        failures: list[str] = []
        preflight_reason = self._metrics.preflight_failure_reason(context)
        llm_telemetry: LlmRunTelemetry | None = None
        llm_guard_reason: str | None = None
        if preflight_reason is None:
            self._metrics.record_attempt()
            try:
                llm_result = await self._llm_executor.decide(context)
                self._metrics.record_success(context=context, telemetry=llm_result.telemetry)
                return NpcDecisionRun(
                    status="created",
                    executorKind=LLM_EXECUTOR_KIND,
                    executorVersion=LLM_EXECUTOR_VERSION,
                    fallbackUsed=False,
                    candidate=llm_result.candidate,
                    failures=failures,
                    **_llm_observability_fields(
                        settings=self._settings,
                        metrics=self._metrics,
                        telemetry=llm_result.telemetry,
                        error_code=None,
                    ),
                )
            except LlmNoActionDecision as err:
                self._metrics.record_no_action(context=context, telemetry=err.telemetry)
                return NpcDecisionRun(
                    status="silent",
                    executorKind=LLM_EXECUTOR_KIND,
                    executorVersion=LLM_EXECUTOR_VERSION,
                    fallbackUsed=False,
                    guardReason=err.reason_code,
                    failures=failures,
                    **_llm_observability_fields(
                        settings=self._settings,
                        metrics=self._metrics,
                        telemetry=err.telemetry,
                        error_code=None,
                    ),
                )
            except Exception as err:
                failure_reason = _failure_reason(err)
                llm_telemetry = _llm_telemetry_from_error(err)
                llm_guard_reason = _guard_reason(err)
                self._metrics.record_failure(
                    failure_reason,
                    context=context,
                    guard_rejected=llm_guard_reason is not None,
                    telemetry=llm_telemetry,
                )
        else:
            failure_reason = preflight_reason
        failures.append(f"{LLM_EXECUTOR_KIND}:{failure_reason}")
        if not self._settings.rule_fallback_enabled:
            return NpcDecisionRun(
                status="rejected",
                executorKind=LLM_EXECUTOR_KIND,
                executorVersion=LLM_EXECUTOR_VERSION,
                fallbackUsed=False,
                fallbackReason=failure_reason,
                guardReason=llm_guard_reason,
                failures=failures,
                **_llm_observability_fields(
                    settings=self._settings,
                    metrics=self._metrics,
                    telemetry=llm_telemetry,
                    error_code=failure_reason,
                ),
            )
        self._metrics.record_fallback()
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
                    fallbackFromExecutorKind=LLM_EXECUTOR_KIND,
                    failures=failures,
                    **_llm_observability_fields(
                        settings=self._settings,
                        metrics=self._metrics,
                        telemetry=llm_telemetry,
                        error_code=fallback_reason,
                    ),
                )
            return NpcDecisionRun(
                status="fallback",
                executorKind=RULE_EXECUTOR_KIND,
                executorVersion=RULE_EXECUTOR_VERSION,
                fallbackUsed=True,
                fallbackReason=fallback_reason,
                fallbackFromExecutorKind=LLM_EXECUTOR_KIND,
                candidate=candidate,
                failures=failures,
                **_llm_observability_fields(
                    settings=self._settings,
                    metrics=self._metrics,
                    telemetry=llm_telemetry,
                    error_code=fallback_reason,
                ),
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
                **_llm_observability_fields(
                    settings=self._settings,
                    metrics=self._metrics,
                    telemetry=llm_telemetry,
                    error_code=failure_reason,
                ),
            )

    def metrics_snapshot(self):
        return self._metrics.snapshot()


def create_default_router(settings: Settings) -> NpcExecutorRouter:
    provider = OpenAICompatibleProvider(settings)
    return NpcExecutorRouter(
        settings=settings,
        llm_executor=LlmExecutorV1(settings=settings, provider=provider),
        rule_executor=RuleExecutorV1(settings=settings),
    )


def _failure_reason(err: Exception) -> str:
    if isinstance(err, LlmExecutorError | OpenAIProviderError | NpcGuardError | ExecutorUnavailable):
        return err.reason_code
    message = str(err).strip()
    if not message:
        return err.__class__.__name__
    return f"{err.__class__.__name__}:{message}"[:200]


def _guard_reason(err: Exception) -> str | None:
    if isinstance(err, LlmExecutorError):
        return err.guard_reason
    if isinstance(err, NpcGuardError):
        return err.reason_code
    return None


def _llm_telemetry_from_error(err: Exception) -> LlmRunTelemetry | None:
    if isinstance(err, LlmExecutorError):
        return err.telemetry
    return None


def _llm_observability_fields(
    *,
    settings: Settings,
    metrics: NpcRuntimeMetrics,
    telemetry: LlmRunTelemetry | None,
    error_code: str | None,
) -> dict[str, Any]:
    return {
        "llmErrorCode": error_code,
        "llmLatencyMs": telemetry.latency_ms if telemetry else None,
        "llmTokenUsage": telemetry.token_usage if telemetry else None,
        "llmEstimatedCostMicrousd": telemetry.estimated_cost_microusd if telemetry else None,
        "llmModel": telemetry.model if telemetry else settings.openai.model,
        "llmProviderName": telemetry.provider_name if telemetry else settings.openai.provider_name,
        "llmCanaryEnabled": settings.llm_runtime.canary_enabled,
        "llmCircuitOpenUntil": metrics.current_circuit_open_until(),
        "policyVersion": settings.npc_policy_version,
        "promptVersion": telemetry.prompt_version if telemetry else settings.npc_prompt_version,
    }


def _empty_llm_telemetry(settings: Settings, *, latency_ms: int) -> LlmRunTelemetry:
    return LlmRunTelemetry(
        latency_ms=latency_ms,
        token_usage=LlmTokenUsage(),
        estimated_cost_microusd=0,
        model=settings.openai.model,
        provider_name=settings.openai.provider_name,
        prompt_version=settings.npc_prompt_version,
    )


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))


def _public_call_reply(call_type: str) -> str:
    if call_type == "rules_help":
        return "我收到规则求助了：请大家继续在公开房间里围绕论题发言，我只做现场提醒，不给正式裁决。"
    if call_type == "issue_summary":
        return "我先把现场焦点收束一下：请双方继续围绕核心争议补证据、拆逻辑。"
    if call_type == "pause_review":
        return "我收到暂停复核请求了。当前我先公开提醒节奏，是否暂停仍以房间机制为准。"
    if call_type == "report_issue":
        return "我收到现场问题反馈了。请大家回到论题本身，避免人身攻击和跑题。"
    return "收到公开请求，我会继续观察现场节奏。"
