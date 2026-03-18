from __future__ import annotations

from typing import Any

from .callback_client import (
    CallbackClientConfig,
    callback_failed,
    callback_final_report,
    callback_phase_report,
    callback_report,
)
from .dispatch_controller import CallbackFailedFn, CallbackReportFn


def bind_callback_report(
    *,
    cfg: CallbackClientConfig,
    callback_report_impl=callback_report,
) -> CallbackReportFn:
    async def _bound(job_id: int, payload: dict[str, Any]) -> None:
        await callback_report_impl(
            cfg=cfg,
            job_id=job_id,
            payload=payload,
        )

    return _bound


def bind_callback_failed(
    *,
    cfg: CallbackClientConfig,
    callback_failed_impl=callback_failed,
) -> CallbackFailedFn:
    async def _bound(job_id: int, error_message: str) -> None:
        await callback_failed_impl(
            cfg=cfg,
            job_id=job_id,
            error_message=error_message,
        )

    return _bound


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


def build_dispatch_callbacks(
    *,
    cfg: CallbackClientConfig,
    callback_report_impl=callback_report,
    callback_failed_impl=callback_failed,
) -> tuple[CallbackReportFn, CallbackFailedFn]:
    return (
        bind_callback_report(
            cfg=cfg,
            callback_report_impl=callback_report_impl,
        ),
        bind_callback_failed(
            cfg=cfg,
            callback_failed_impl=callback_failed_impl,
        ),
    )


def build_v3_dispatch_callbacks(
    *,
    cfg: CallbackClientConfig,
    callback_phase_report_impl=callback_phase_report,
    callback_final_report_impl=callback_final_report,
) -> tuple[CallbackReportFn, CallbackReportFn]:
    return (
        bind_callback_phase_report(
            cfg=cfg,
            callback_phase_report_impl=callback_phase_report_impl,
        ),
        bind_callback_final_report(
            cfg=cfg,
            callback_final_report_impl=callback_final_report_impl,
        ),
    )
