from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class CallbackClientConfig:
    ai_internal_key: str
    chat_server_base_url: str
    callback_timeout_secs: float
    phase_report_path_template: str = "/api/internal/ai/judge/v3/phase/jobs/{job_id}/report"
    final_report_path_template: str = "/api/internal/ai/judge/v3/final/jobs/{job_id}/report"
    phase_failed_path_template: str = "/api/internal/ai/judge/v3/phase/jobs/{job_id}/failed"
    final_failed_path_template: str = "/api/internal/ai/judge/v3/final/jobs/{job_id}/failed"


def join_url(base: str, path: str) -> str:
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


async def callback_phase_report(
    *,
    cfg: CallbackClientConfig,
    job_id: int,
    payload: dict,
) -> None:
    path = cfg.phase_report_path_template.format(job_id=job_id)
    await _post_callback(
        cfg=cfg,
        path=path,
        payload=payload,
        callback_name="phase report",
    )


async def callback_final_report(
    *,
    cfg: CallbackClientConfig,
    job_id: int,
    payload: dict,
) -> None:
    path = cfg.final_report_path_template.format(job_id=job_id)
    await _post_callback(
        cfg=cfg,
        path=path,
        payload=payload,
        callback_name="final report",
    )


async def callback_phase_failed(
    *,
    cfg: CallbackClientConfig,
    job_id: int,
    payload: dict,
) -> None:
    path = cfg.phase_failed_path_template.format(job_id=job_id)
    await _post_callback(
        cfg=cfg,
        path=path,
        payload=payload,
        callback_name="phase failed",
    )


async def callback_final_failed(
    *,
    cfg: CallbackClientConfig,
    job_id: int,
    payload: dict,
) -> None:
    path = cfg.final_failed_path_template.format(job_id=job_id)
    await _post_callback(
        cfg=cfg,
        path=path,
        payload=payload,
        callback_name="final failed",
    )


async def _post_callback(
    *,
    cfg: CallbackClientConfig,
    path: str,
    payload: dict,
    callback_name: str,
) -> None:
    url = join_url(cfg.chat_server_base_url, path)
    async with httpx.AsyncClient(timeout=cfg.callback_timeout_secs) as client:
        resp = await client.post(
            url,
            headers={"x-ai-internal-key": cfg.ai_internal_key},
            json=payload,
        )
    if resp.status_code // 100 != 2:
        raise RuntimeError(
            f"{callback_name} callback failed: status={resp.status_code}, body={resp.text}"
        )
