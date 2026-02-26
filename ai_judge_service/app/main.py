import asyncio

from fastapi import FastAPI, Header, HTTPException

from .callback_client import callback_failed, callback_report
from .dispatch_controller import process_dispatch_request
from .models import JudgeDispatchRequest
from .runtime_orchestrator import build_report_by_runtime
from .settings import (
    build_callback_client_config,
    build_dispatch_runtime_config,
    load_settings,
)


SETTINGS = load_settings()
app = FastAPI(title="AI Judge Service", version="0.2.0")
CALLBACK_CFG = build_callback_client_config(SETTINGS)
DISPATCH_RUNTIME_CFG = build_dispatch_runtime_config(SETTINGS)


def _require_internal_key(header_value: str | None) -> None:
    if not header_value:
        raise HTTPException(status_code=401, detail="missing x-ai-internal-key")
    if header_value.strip() != SETTINGS.ai_internal_key:
        raise HTTPException(status_code=401, detail="invalid x-ai-internal-key")


async def _build_report_by_runtime_adapter(
    request: JudgeDispatchRequest,
    effective_style_mode: str,
    style_mode_source: str,
):
    return await build_report_by_runtime(
        request=request,
        effective_style_mode=effective_style_mode,
        style_mode_source=style_mode_source,
        settings=SETTINGS,
    )


@app.get("/healthz")
async def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.post("/internal/judge/dispatch")
async def dispatch_judge_job(
    request: JudgeDispatchRequest,
    x_ai_internal_key: str | None = Header(default=None),
) -> dict:
    _require_internal_key(x_ai_internal_key)
    return await process_dispatch_request(
        request=request,
        runtime_cfg=DISPATCH_RUNTIME_CFG,
        build_report_by_runtime=_build_report_by_runtime_adapter,
        callback_report=lambda job_id, payload: callback_report(
            cfg=CALLBACK_CFG,
            job_id=job_id,
            payload=payload,
        ),
        callback_failed=lambda job_id, error_message: callback_failed(
            cfg=CALLBACK_CFG,
            job_id=job_id,
            error_message=error_message,
        ),
        sleep_fn=asyncio.sleep,
    )
