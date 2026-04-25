from __future__ import annotations

from typing import Any

from .callback_client import (
    CallbackClientConfig,
    callback_final_failed,
    callback_final_report,
    callback_phase_failed,
    callback_phase_report,
)
from .infra.artifacts import LocalArtifactStore, S3CompatibleArtifactStore
from .runtime_types import CallbackReportFn
from .settings import Settings


def _build_s3_client(*, settings: Settings) -> Any:
    try:
        import boto3  # type: ignore[import-not-found]
        from botocore.config import Config  # type: ignore[import-not-found]
    except ImportError as err:
        raise RuntimeError("artifact_store_s3_dependency_missing") from err

    kwargs: dict[str, Any] = {}
    if settings.artifact_store_endpoint_url:
        kwargs["endpoint_url"] = settings.artifact_store_endpoint_url
    if settings.artifact_store_region:
        kwargs["region_name"] = settings.artifact_store_region
    if settings.artifact_store_force_path_style:
        kwargs["config"] = Config(s3={"addressing_style": "path"})
    return boto3.client("s3", **kwargs)


def build_artifact_store(*, settings: Settings) -> LocalArtifactStore | S3CompatibleArtifactStore:
    if settings.artifact_store_provider == "s3_compatible":
        return S3CompatibleArtifactStore(
            bucket=settings.artifact_store_bucket,
            prefix=settings.artifact_store_prefix,
            client=_build_s3_client(settings=settings),
            force_path_style=settings.artifact_store_force_path_style,
            endpoint_configured=bool(settings.artifact_store_endpoint_url),
        )
    return LocalArtifactStore(root_dir=settings.artifact_store_root)


def bind_callback_phase_report(
    *,
    cfg: CallbackClientConfig,
    callback_phase_report_impl=callback_phase_report,
) -> CallbackReportFn:
    async def _bound(case_id: int, payload: dict[str, Any]) -> None:
        await callback_phase_report_impl(
            cfg=cfg,
            case_id=case_id,
            payload=payload,
        )

    return _bound


def bind_callback_final_report(
    *,
    cfg: CallbackClientConfig,
    callback_final_report_impl=callback_final_report,
) -> CallbackReportFn:
    async def _bound(case_id: int, payload: dict[str, Any]) -> None:
        await callback_final_report_impl(
            cfg=cfg,
            case_id=case_id,
            payload=payload,
        )

    return _bound


def bind_callback_phase_failed(
    *,
    cfg: CallbackClientConfig,
    callback_phase_failed_impl=callback_phase_failed,
) -> CallbackReportFn:
    async def _bound(case_id: int, payload: dict[str, Any]) -> None:
        await callback_phase_failed_impl(
            cfg=cfg,
            case_id=case_id,
            payload=payload,
        )

    return _bound


def bind_callback_final_failed(
    *,
    cfg: CallbackClientConfig,
    callback_final_failed_impl=callback_final_failed,
) -> CallbackReportFn:
    async def _bound(case_id: int, payload: dict[str, Any]) -> None:
        await callback_final_failed_impl(
            cfg=cfg,
            case_id=case_id,
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
