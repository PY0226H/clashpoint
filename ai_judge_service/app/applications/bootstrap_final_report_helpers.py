from __future__ import annotations

from typing import Any, Callable

from .judge_command_routes import (
    build_final_report_payload_for_dispatch as build_final_report_payload_for_dispatch_v3,
)


def build_final_report_payload_for_runtime(
    *,
    request: Any,
    phase_receipts: list[Any] | None,
    fairness_thresholds: dict[str, Any] | None,
    panel_runtime_profiles: dict[str, dict[str, Any]] | None,
    list_dispatch_receipts: Callable[..., list[Any]],
    build_final_report_payload: Callable[..., dict[str, Any]],
    judge_style_mode: str,
) -> dict[str, Any]:
    return build_final_report_payload_for_dispatch_v3(
        request=request,
        phase_receipts=phase_receipts,
        fairness_thresholds=fairness_thresholds,
        panel_runtime_profiles=panel_runtime_profiles,
        list_dispatch_receipts=list_dispatch_receipts,
        build_final_report_payload=build_final_report_payload,
        judge_style_mode=judge_style_mode,
    )
