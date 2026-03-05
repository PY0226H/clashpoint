from __future__ import annotations

from typing import Awaitable, Callable

from .models import JudgeDispatchRequest, SubmitJudgeReportInput
from .openai_judge import OpenAiJudgeConfig, build_report_with_openai
from .rag_retriever import RetrievedContext
from .runtime_errors import (
    ERROR_JUDGE_TIMEOUT,
    ERROR_MODEL_OVERLOAD,
    JudgeRuntimeError,
    classify_openai_failure,
)
from .runtime_policy import PROVIDER_OPENAI, should_use_openai
from .scoring import build_report
from .settings import Settings

BuildOpenAiReportFn = Callable[..., Awaitable[SubmitJudgeReportInput]]
BuildMockReportFn = Callable[..., SubmitJudgeReportInput]


def _fault_nodes(settings: Settings) -> set[str]:
    return {
        str(node).strip().lower()
        for node in getattr(settings, "fault_injection_nodes", ())
        if str(node).strip()
    }


async def build_report_with_provider(
    *,
    request: JudgeDispatchRequest,
    effective_style_mode: str,
    style_mode_source: str,
    settings: Settings,
    retrieved_contexts: list[RetrievedContext],
    build_report_with_openai_fn: BuildOpenAiReportFn = build_report_with_openai,
    build_mock_report_fn: BuildMockReportFn = build_report,
) -> tuple[SubmitJudgeReportInput, bool]:
    injected = _fault_nodes(settings)
    if settings.provider == PROVIDER_OPENAI and not settings.openai_api_key.strip():
        error_code = ERROR_MODEL_OVERLOAD
        if not settings.openai_fallback_to_mock:
            raise JudgeRuntimeError(
                code=error_code,
                message="openai runtime missing OPENAI_API_KEY",
            )
        report = build_mock_report_fn(
            request,
            system_style_mode=settings.judge_style_mode,
        )
        report.payload["provider"] = "ai-judge-service-mock-missing-openai-key"
        report.payload["fallbackFrom"] = "openai"
        report.payload["fallbackReason"] = "missing OPENAI_API_KEY"
        report.payload["fallbackErrorCode"] = error_code
        return report, False

    if should_use_openai(settings.provider, settings.openai_api_key):
        cfg = OpenAiJudgeConfig(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            timeout_secs=settings.openai_timeout_secs,
            temperature=settings.openai_temperature,
            max_retries=settings.openai_max_retries,
            max_stage_agent_chunks=settings.stage_agent_max_chunks,
            reflection_enabled=settings.reflection_enabled,
            graph_v2_enabled=settings.graph_v2_enabled,
            reflection_policy=settings.reflection_policy,
            reflection_low_margin_threshold=settings.reflection_low_margin_threshold,
            fault_injection_nodes=settings.fault_injection_nodes,
        )
        try:
            if "provider_timeout" in injected:
                raise RuntimeError("fault injected provider timeout")
            if "provider_overload" in injected:
                raise RuntimeError("fault injected provider overload status=429")
            report = await build_report_with_openai_fn(
                request=request,
                effective_style_mode=effective_style_mode,
                style_mode_source=style_mode_source,
                cfg=cfg,
                retrieved_contexts=retrieved_contexts,
            )
            return report, True
        except Exception as err:
            if "provider_timeout" in injected:
                error_code = ERROR_JUDGE_TIMEOUT
            elif "provider_overload" in injected:
                error_code = ERROR_MODEL_OVERLOAD
            else:
                error_code = classify_openai_failure(str(err))
            if not settings.openai_fallback_to_mock:
                raise JudgeRuntimeError(
                    code=error_code,
                    message=f"openai runtime failed: {err}",
                ) from err
            report = build_mock_report_fn(
                request,
                system_style_mode=settings.judge_style_mode,
            )
            report.payload["provider"] = "ai-judge-service-mock-fallback"
            report.payload["fallbackFrom"] = "openai"
            report.payload["fallbackReason"] = str(err)[:500]
            report.payload["fallbackErrorCode"] = error_code
            return report, False

    report = build_mock_report_fn(
        request,
        system_style_mode=settings.judge_style_mode,
    )
    return report, False
