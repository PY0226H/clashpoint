from __future__ import annotations

from typing import TYPE_CHECKING

from .scoring_core import DebateMessage, build_report_core

STYLE_RATIONAL = "rational"
STYLE_ENTERTAINING = "entertaining"
STYLE_MIXED = "mixed"
VALID_STYLE_MODES = {STYLE_RATIONAL, STYLE_ENTERTAINING, STYLE_MIXED}

if TYPE_CHECKING:
    from .models import JudgeDispatchRequest, SubmitJudgeReportInput


def _normalize_style_mode(mode: str | None) -> str | None:
    if mode is None:
        return None
    value = mode.strip().lower()
    if value in VALID_STYLE_MODES:
        return value
    return None


def resolve_effective_style_mode(
    request_style_mode: str,
    system_style_mode: str | None,
) -> tuple[str, str]:
    normalized_system = _normalize_style_mode(system_style_mode)
    if system_style_mode is not None:
        if normalized_system is not None:
            return normalized_system, "system_config"
        return STYLE_RATIONAL, "system_config_fallback_default"

    normalized_request = _normalize_style_mode(request_style_mode)
    if normalized_request is not None:
        return normalized_request, "job_request"
    return STYLE_RATIONAL, "default"


def build_report(
    request: JudgeDispatchRequest,
    system_style_mode: str | None = None,
) -> SubmitJudgeReportInput:
    from .models import SubmitJudgeReportInput

    effective_style_mode, style_mode_source = resolve_effective_style_mode(
        request.job.style_mode,
        system_style_mode,
    )
    messages = [
        DebateMessage(
            message_id=msg.message_id,
            user_id=msg.user_id or 0,
            side=msg.side,
            content=msg.content,
        )
        for msg in request.messages
    ]
    report = build_report_core(
        job_id=request.job.job_id,
        style_mode=effective_style_mode,
        rejudge_triggered=request.job.rejudge_triggered,
        messages=messages,
        message_window_size=request.message_window_size,
        rubric_version=request.rubric_version,
    )
    report["payload"]["requestedStyleMode"] = request.job.style_mode
    report["payload"]["effectiveStyleMode"] = effective_style_mode
    report["payload"]["styleModeSource"] = style_mode_source
    return SubmitJudgeReportInput(**report)
