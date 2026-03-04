from __future__ import annotations

from typing import Awaitable, Callable

from .models import JudgeDispatchRequest, SubmitJudgeReportInput
from .openai_judge import OpenAiJudgeConfig, build_report_with_openai
from .rag_retriever import RetrievedContext
from .runtime_policy import PROVIDER_OPENAI, should_use_openai
from .scoring import build_report
from .settings import Settings

BuildOpenAiReportFn = Callable[..., Awaitable[SubmitJudgeReportInput]]
BuildMockReportFn = Callable[..., SubmitJudgeReportInput]


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
    if settings.provider == PROVIDER_OPENAI and not settings.openai_api_key.strip():
        if not settings.openai_fallback_to_mock:
            raise RuntimeError("openai runtime missing OPENAI_API_KEY")
        report = build_mock_report_fn(
            request,
            system_style_mode=settings.judge_style_mode,
        )
        report.payload["provider"] = "ai-judge-service-mock-missing-openai-key"
        report.payload["fallbackFrom"] = "openai"
        report.payload["fallbackReason"] = "missing OPENAI_API_KEY"
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
        )
        try:
            report = await build_report_with_openai_fn(
                request=request,
                effective_style_mode=effective_style_mode,
                style_mode_source=style_mode_source,
                cfg=cfg,
                retrieved_contexts=retrieved_contexts,
            )
            return report, True
        except Exception as err:
            if not settings.openai_fallback_to_mock:
                raise RuntimeError(f"openai runtime failed: {err}") from err
            report = build_mock_report_fn(
                request,
                system_style_mode=settings.judge_style_mode,
            )
            report.payload["provider"] = "ai-judge-service-mock-fallback"
            report.payload["fallbackFrom"] = "openai"
            report.payload["fallbackReason"] = str(err)[:500]
            return report, False

    report = build_mock_report_fn(
        request,
        system_style_mode=settings.judge_style_mode,
    )
    return report, False
