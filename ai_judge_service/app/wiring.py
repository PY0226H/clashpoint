from __future__ import annotations

from typing import Any

from .callback_client import (
    CallbackClientConfig,
    callback_final_failed,
    callback_final_report,
    callback_phase_failed,
    callback_phase_report,
)
from .runtime_types import CallbackReportFn


def bind_callback_phase_report(
    *,
    cfg: CallbackClientConfig,
    callback_phase_report_impl=callback_phase_report,
) -> CallbackReportFn:
    async def _bound(job_id: int, payload: dict[str, Any]) -> None:
        await callback_phase_report_impl(
            cfg=cfg,
            job_id=job_id,
            payload=payload,
        )

    return _bound


def bind_callback_final_report(
    *,
    cfg: CallbackClientConfig,
    callback_final_report_impl=callback_final_report,
) -> CallbackReportFn:
    async def _bound(job_id: int, payload: dict[str, Any]) -> None:
        await callback_final_report_impl(
            cfg=cfg,
            job_id=job_id,
            payload=payload,
        )

    return _bound


def bind_callback_phase_failed(
    *,
    cfg: CallbackClientConfig,
    callback_phase_failed_impl=callback_phase_failed,
) -> CallbackReportFn:
    async def _bound(job_id: int, payload: dict[str, Any]) -> None:
        await callback_phase_failed_impl(
            cfg=cfg,
            job_id=job_id,
            payload=payload,
        )

    return _bound


def bind_callback_final_failed(
    *,
    cfg: CallbackClientConfig,
    callback_final_failed_impl=callback_final_failed,
) -> CallbackReportFn:
    async def _bound(job_id: int, payload: dict[str, Any]) -> None:
        await callback_final_failed_impl(
            cfg=cfg,
            job_id=job_id,
            payload=payload,
        )

    return _bound


def build_v3_dispatch_callbacks(
    *,
    cfg: CallbackClientConfig,
    callback_phase_report_impl=callback_phase_report,
    callback_final_report_impl=callback_final_report,
    callback_phase_failed_impl=callback_phase_failed,
    callback_final_failed_impl=callback_final_failed,
) -> tuple[CallbackReportFn, CallbackReportFn, CallbackReportFn, CallbackReportFn]:
    return (
        bind_callback_phase_report(
            cfg=cfg,
            callback_phase_report_impl=callback_phase_report_impl,
        ),
        bind_callback_final_report(
            cfg=cfg,
            callback_final_report_impl=callback_final_report_impl,
        ),
        bind_callback_phase_failed(
            cfg=cfg,
            callback_phase_failed_impl=callback_phase_failed_impl,
        ),
        bind_callback_final_failed(
            cfg=cfg,
            callback_final_failed_impl=callback_final_failed_impl,
        ),
    )
