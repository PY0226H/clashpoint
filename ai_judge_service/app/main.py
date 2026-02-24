import asyncio
import os
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, Header, HTTPException

from .models import JudgeDispatchRequest, MarkJudgeJobFailedInput
from .scoring import build_report


@dataclass(frozen=True)
class Settings:
    ai_internal_key: str
    chat_server_base_url: str
    report_path_template: str
    failed_path_template: str
    callback_timeout_secs: float
    process_delay_ms: int


def _load_settings() -> Settings:
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
    )


SETTINGS = _load_settings()
app = FastAPI(title="AI Judge Service (Mock)", version="0.1.0")


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

    report = build_report(request)
    try:
        await _callback_report(request.job.job_id, report.model_dump(mode="json"))
    except Exception as err:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"callback report failed: {err}") from err

    return {
        "accepted": True,
        "jobId": request.job.job_id,
        "winner": report.winner,
        "needsDrawVote": report.needs_draw_vote,
    }
