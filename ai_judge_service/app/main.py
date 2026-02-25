import asyncio
import os
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, Header, HTTPException

from .models import JudgeDispatchRequest, MarkJudgeJobFailedInput
from .openai_judge import OpenAiJudgeConfig, build_report_with_openai
from .rag_retriever import retrieve_contexts, summarize_retrieved_contexts
from .runtime_policy import PROVIDER_OPENAI, normalize_provider, parse_env_bool, should_use_openai
from .scoring import build_report, resolve_effective_style_mode


@dataclass(frozen=True)
class Settings:
    ai_internal_key: str
    chat_server_base_url: str
    report_path_template: str
    failed_path_template: str
    callback_timeout_secs: float
    process_delay_ms: int
    judge_style_mode: str
    provider: str
    openai_api_key: str
    openai_model: str
    openai_base_url: str
    openai_timeout_secs: float
    openai_temperature: float
    openai_max_retries: int
    openai_fallback_to_mock: bool
    rag_enabled: bool
    rag_knowledge_file: str
    rag_max_snippets: int
    rag_max_chars_per_snippet: int
    rag_query_message_limit: int


def _load_settings() -> Settings:
    provider = normalize_provider(os.getenv("AI_JUDGE_PROVIDER", "mock"))
    return Settings(
        ai_internal_key=os.getenv("AI_JUDGE_INTERNAL_KEY", "dev-ai-internal-key"),
        chat_server_base_url=os.getenv("CHAT_SERVER_BASE_URL", "http://127.0.0.1:6688"),
        report_path_template=os.getenv(
            "CHAT_SERVER_REPORT_PATH_TEMPLATE",
            "/api/internal/ai/judge/jobs/{job_id}/report",
        ),
        failed_path_template=os.getenv(
            "CHAT_SERVER_FAILED_PATH_TEMPLATE",
            "/api/internal/ai/judge/jobs/{job_id}/failed",
        ),
        callback_timeout_secs=float(os.getenv("CALLBACK_TIMEOUT_SECONDS", "8")),
        process_delay_ms=int(os.getenv("JUDGE_PROCESS_DELAY_MS", "0")),
        judge_style_mode=os.getenv("JUDGE_STYLE_MODE", "rational"),
        provider=provider,
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("AI_JUDGE_OPENAI_MODEL", "gpt-4.1-mini"),
        openai_base_url=os.getenv("AI_JUDGE_OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        openai_timeout_secs=float(os.getenv("AI_JUDGE_OPENAI_TIMEOUT_SECONDS", "25")),
        openai_temperature=float(os.getenv("AI_JUDGE_OPENAI_TEMPERATURE", "0.1")),
        openai_max_retries=int(os.getenv("AI_JUDGE_OPENAI_MAX_RETRIES", "2")),
        openai_fallback_to_mock=parse_env_bool(
            os.getenv("AI_JUDGE_OPENAI_FALLBACK_TO_MOCK"),
            default=True,
        ),
        rag_enabled=parse_env_bool(os.getenv("AI_JUDGE_RAG_ENABLED"), default=True),
        rag_knowledge_file=os.getenv("AI_JUDGE_RAG_KNOWLEDGE_FILE", ""),
        rag_max_snippets=int(os.getenv("AI_JUDGE_RAG_MAX_SNIPPETS", "4")),
        rag_max_chars_per_snippet=int(os.getenv("AI_JUDGE_RAG_MAX_CHARS_PER_SNIPPET", "280")),
        rag_query_message_limit=int(os.getenv("AI_JUDGE_RAG_QUERY_MESSAGE_LIMIT", "80")),
    )


SETTINGS = _load_settings()
app = FastAPI(title="AI Judge Service", version="0.2.0")


def _join_url(base: str, path: str) -> str:
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


def _require_internal_key(header_value: str | None) -> None:
    if not header_value:
        raise HTTPException(status_code=401, detail="missing x-ai-internal-key")
    if header_value.strip() != SETTINGS.ai_internal_key:
        raise HTTPException(status_code=401, detail="invalid x-ai-internal-key")


async def _callback_report(job_id: int, payload: dict) -> None:
    path = SETTINGS.report_path_template.format(job_id=job_id)
    url = _join_url(SETTINGS.chat_server_base_url, path)
    async with httpx.AsyncClient(timeout=SETTINGS.callback_timeout_secs) as client:
        resp = await client.post(
            url,
            headers={"x-ai-internal-key": SETTINGS.ai_internal_key},
            json=payload,
        )
    if resp.status_code // 100 != 2:
        raise RuntimeError(f"report callback failed: status={resp.status_code}, body={resp.text}")


async def _callback_failed(job_id: int, error_message: str) -> None:
    path = SETTINGS.failed_path_template.format(job_id=job_id)
    url = _join_url(SETTINGS.chat_server_base_url, path)
    body = MarkJudgeJobFailedInput(error_message=error_message).model_dump()
    async with httpx.AsyncClient(timeout=SETTINGS.callback_timeout_secs) as client:
        resp = await client.post(
            url,
            headers={"x-ai-internal-key": SETTINGS.ai_internal_key},
            json=body,
        )
    if resp.status_code // 100 != 2:
        raise RuntimeError(f"failed callback failed: status={resp.status_code}, body={resp.text}")


async def _build_report_by_runtime(
    request: JudgeDispatchRequest,
    effective_style_mode: str,
    style_mode_source: str,
):
    retrieved_contexts = retrieve_contexts(
        request,
        enabled=SETTINGS.rag_enabled,
        knowledge_file=SETTINGS.rag_knowledge_file,
        max_snippets=SETTINGS.rag_max_snippets,
        max_chars_per_snippet=SETTINGS.rag_max_chars_per_snippet,
        query_message_limit=SETTINGS.rag_query_message_limit,
    )
    if should_use_openai(SETTINGS.provider, SETTINGS.openai_api_key):
        cfg = OpenAiJudgeConfig(
            api_key=SETTINGS.openai_api_key,
            model=SETTINGS.openai_model,
            base_url=SETTINGS.openai_base_url,
            timeout_secs=SETTINGS.openai_timeout_secs,
            temperature=SETTINGS.openai_temperature,
            max_retries=SETTINGS.openai_max_retries,
        )
        try:
            return await build_report_with_openai(
                request=request,
                effective_style_mode=effective_style_mode,
                style_mode_source=style_mode_source,
                cfg=cfg,
                retrieved_contexts=retrieved_contexts,
            )
        except Exception as err:
            if not SETTINGS.openai_fallback_to_mock:
                raise RuntimeError(f"openai runtime failed: {err}") from err
            report = build_report(request, system_style_mode=SETTINGS.judge_style_mode)
            report.payload["provider"] = "ai-judge-service-mock-fallback"
            report.payload["fallbackFrom"] = "openai"
            report.payload["fallbackReason"] = str(err)[:500]
            report.payload["ragEnabled"] = SETTINGS.rag_enabled
            report.payload["ragUsedByModel"] = False
            report.payload["ragSnippetCount"] = len(retrieved_contexts)
            report.payload["ragSources"] = summarize_retrieved_contexts(retrieved_contexts)
            return report

    report = build_report(request, system_style_mode=SETTINGS.judge_style_mode)
    if SETTINGS.provider == PROVIDER_OPENAI and not SETTINGS.openai_api_key.strip():
        report.payload["provider"] = "ai-judge-service-mock-missing-openai-key"
        report.payload["fallbackFrom"] = "openai"
        report.payload["fallbackReason"] = "missing OPENAI_API_KEY"
    report.payload["ragEnabled"] = SETTINGS.rag_enabled
    report.payload["ragUsedByModel"] = False
    report.payload["ragSnippetCount"] = len(retrieved_contexts)
    report.payload["ragSources"] = summarize_retrieved_contexts(retrieved_contexts)
    return report


@app.get("/healthz")
async def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.post("/internal/judge/dispatch")
async def dispatch_judge_job(
    request: JudgeDispatchRequest,
    x_ai_internal_key: str | None = Header(default=None),
) -> dict:
    _require_internal_key(x_ai_internal_key)
    if SETTINGS.process_delay_ms > 0:
        await asyncio.sleep(SETTINGS.process_delay_ms / 1000.0)

    if not request.messages:
        await _callback_failed(request.job.job_id, "empty debate messages, cannot judge")
        return {"accepted": True, "jobId": request.job.job_id, "status": "marked_failed"}

    effective_style_mode, style_mode_source = resolve_effective_style_mode(
        request.job.style_mode,
        SETTINGS.judge_style_mode,
    )
    try:
        report = await _build_report_by_runtime(
            request,
            effective_style_mode=effective_style_mode,
            style_mode_source=style_mode_source,
        )
    except Exception as err:
        error_message = f"judge runtime failed: {err}"
        try:
            await _callback_failed(request.job.job_id, error_message)
        except Exception as callback_err:  # pragma: no cover
            raise HTTPException(
                status_code=502,
                detail=f"runtime failed and callback_failed failed: {callback_err}",
            ) from callback_err
        return {"accepted": True, "jobId": request.job.job_id, "status": "marked_failed"}

    try:
        await _callback_report(request.job.job_id, report.model_dump(mode="json"))
    except Exception as err:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"callback report failed: {err}") from err

    return {
        "accepted": True,
        "jobId": request.job.job_id,
        "winner": report.winner,
        "needsDrawVote": report.needs_draw_vote,
        "provider": report.payload.get("provider"),
    }
