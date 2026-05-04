from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .models import LlmTokenUsage, NpcDecisionContext, NpcRuntimeMetricsSnapshot
from .settings import Settings


@dataclass(frozen=True)
class LlmRunTelemetry:
    latency_ms: int
    token_usage: LlmTokenUsage
    estimated_cost_microusd: int
    model: str
    provider_name: str
    prompt_version: str


class NpcRuntimeMetrics:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings
        self._llm_attempt_total = 0
        self._llm_success_total = 0
        self._llm_fallback_total = 0
        self._llm_no_action_total = 0
        self._llm_guard_rejected_total = 0
        self._llm_error_total = 0
        self._llm_circuit_open_total = 0
        self._llm_consecutive_failure_count = 0
        self._llm_circuit_open_until: datetime | None = None
        self._llm_last_error_code: str | None = None
        self._llm_last_latency_ms: int | None = None
        self._llm_latency_total_ms = 0
        self._llm_prompt_tokens_total = 0
        self._llm_completion_tokens_total = 0
        self._llm_total_tokens_total = 0
        self._llm_estimated_cost_microusd_total = 0
        self._llm_estimated_cost_microusd_by_session: dict[int, int] = {}

    def preflight_failure_reason(self, context: NpcDecisionContext) -> str | None:
        if not self._settings.llm_enabled:
            return "llm_disabled"
        if not self._settings.openai.configured:
            return "llm_not_configured"
        now = datetime.now(timezone.utc)
        if self._llm_circuit_open_until is not None:
            if self._llm_circuit_open_until > now:
                return "llm_circuit_open"
            self._llm_circuit_open_until = None
        runtime = self._settings.llm_runtime
        if runtime.canary_enabled and context.session_id not in runtime.canary_session_ids:
            return "llm_canary_session_not_allowed"
        if (
            runtime.daily_cost_limit_microusd > 0
            and self._llm_estimated_cost_microusd_total >= runtime.daily_cost_limit_microusd
        ):
            return "llm_daily_cost_limit_exceeded"
        room_cost = self._llm_estimated_cost_microusd_by_session.get(context.session_id, 0)
        if runtime.room_cost_limit_microusd > 0 and room_cost >= runtime.room_cost_limit_microusd:
            return "llm_room_cost_limit_exceeded"
        return None

    def record_attempt(self) -> None:
        self._llm_attempt_total += 1

    def record_success(self, *, context: NpcDecisionContext, telemetry: LlmRunTelemetry) -> None:
        self._record_healthy_llm_call(context=context, telemetry=telemetry)
        self._llm_success_total += 1

    def record_no_action(self, *, context: NpcDecisionContext, telemetry: LlmRunTelemetry) -> None:
        self._record_healthy_llm_call(context=context, telemetry=telemetry)
        self._llm_no_action_total += 1

    def record_failure(
        self,
        reason_code: str,
        *,
        context: NpcDecisionContext,
        guard_rejected: bool,
        telemetry: LlmRunTelemetry | None,
    ) -> None:
        self._llm_error_total += 1
        self._llm_last_error_code = reason_code
        if guard_rejected:
            self._llm_guard_rejected_total += 1
        if telemetry is not None:
            self._record_llm_observability(context=context, telemetry=telemetry)
        self._llm_consecutive_failure_count += 1
        if self._llm_consecutive_failure_count >= self._settings.llm_runtime.circuit_failure_threshold:
            self._open_circuit()

    def record_fallback(self) -> None:
        self._llm_fallback_total += 1

    def snapshot(self) -> NpcRuntimeMetricsSnapshot:
        return NpcRuntimeMetricsSnapshot(
            llmAttemptTotal=self._llm_attempt_total,
            llmSuccessTotal=self._llm_success_total,
            llmFallbackTotal=self._llm_fallback_total,
            llmNoActionTotal=self._llm_no_action_total,
            llmGuardRejectedTotal=self._llm_guard_rejected_total,
            llmErrorTotal=self._llm_error_total,
            llmCircuitOpenTotal=self._llm_circuit_open_total,
            llmConsecutiveFailureCount=self._llm_consecutive_failure_count,
            llmCircuitOpenUntil=_iso_or_none(self._llm_circuit_open_until),
            llmLastErrorCode=self._llm_last_error_code,
            llmLastLatencyMs=self._llm_last_latency_ms,
            llmLatencyTotalMs=self._llm_latency_total_ms,
            llmPromptTokensTotal=self._llm_prompt_tokens_total,
            llmCompletionTokensTotal=self._llm_completion_tokens_total,
            llmTotalTokensTotal=self._llm_total_tokens_total,
            llmEstimatedCostMicrousdTotal=self._llm_estimated_cost_microusd_total,
            llmEstimatedCostMicrousdBySession={
                str(session_id): cost
                for session_id, cost in sorted(self._llm_estimated_cost_microusd_by_session.items())
            },
            llmModel=self._settings.openai.model,
            llmProviderName=self._settings.openai.provider_name,
            llmCanaryEnabled=self._settings.llm_runtime.canary_enabled,
            llmCanarySessionIds=list(self._settings.llm_runtime.canary_session_ids),
            policyVersion=self._settings.npc_policy_version,
            promptVersion=self._settings.npc_prompt_version,
        )

    def current_circuit_open_until(self) -> str | None:
        return _iso_or_none(self._llm_circuit_open_until)

    def _record_healthy_llm_call(
        self,
        *,
        context: NpcDecisionContext,
        telemetry: LlmRunTelemetry,
    ) -> None:
        self._llm_consecutive_failure_count = 0
        self._llm_circuit_open_until = None
        self._record_llm_observability(context=context, telemetry=telemetry)

    def _record_llm_observability(
        self,
        *,
        context: NpcDecisionContext,
        telemetry: LlmRunTelemetry,
    ) -> None:
        self._llm_last_latency_ms = telemetry.latency_ms
        self._llm_latency_total_ms += telemetry.latency_ms
        self._llm_prompt_tokens_total += telemetry.token_usage.prompt_tokens
        self._llm_completion_tokens_total += telemetry.token_usage.completion_tokens
        self._llm_total_tokens_total += telemetry.token_usage.total_tokens
        self._llm_estimated_cost_microusd_total += telemetry.estimated_cost_microusd
        self._llm_estimated_cost_microusd_by_session[context.session_id] = (
            self._llm_estimated_cost_microusd_by_session.get(context.session_id, 0)
            + telemetry.estimated_cost_microusd
        )

    def _open_circuit(self) -> None:
        cooldown = self._settings.llm_runtime.circuit_cooldown_secs
        self._llm_circuit_open_until = datetime.now(timezone.utc) + timedelta(seconds=cooldown)
        self._llm_circuit_open_total += 1


def build_llm_telemetry(
    raw: dict[str, Any],
    *,
    settings: Settings,
    latency_ms: int,
) -> LlmRunTelemetry:
    usage = _coerce_usage(raw.get("_openaiUsage"))
    return LlmRunTelemetry(
        latency_ms=latency_ms,
        token_usage=usage,
        estimated_cost_microusd=_estimate_cost_microusd(usage, settings=settings),
        model=str(raw.get("_openaiModel") or settings.openai.model),
        provider_name=str(raw.get("_openaiProviderName") or settings.openai.provider_name),
        prompt_version=str(raw.get("_openaiPromptVersion") or settings.npc_prompt_version),
    )


def _coerce_usage(value: object) -> LlmTokenUsage:
    if not isinstance(value, dict):
        return LlmTokenUsage()
    prompt_tokens = _coerce_non_negative_int(value.get("prompt_tokens", value.get("promptTokens")))
    completion_tokens = _coerce_non_negative_int(
        value.get("completion_tokens", value.get("completionTokens"))
    )
    total_tokens = _coerce_non_negative_int(value.get("total_tokens", value.get("totalTokens")))
    if total_tokens == 0:
        total_tokens = prompt_tokens + completion_tokens
    return LlmTokenUsage(
        promptTokens=prompt_tokens,
        completionTokens=completion_tokens,
        totalTokens=total_tokens,
    )


def _estimate_cost_microusd(usage: LlmTokenUsage, *, settings: Settings) -> int:
    return (
        usage.prompt_tokens * settings.openai.input_token_cost_microusd
        + usage.completion_tokens * settings.openai.output_token_cost_microusd
    )


def _coerce_non_negative_int(value: object) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _iso_or_none(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
