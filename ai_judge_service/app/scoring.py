from .models import JudgeDispatchRequest, SubmitJudgeReportInput
from .scoring_core import DebateMessage, build_report_core


def build_report(request: JudgeDispatchRequest) -> SubmitJudgeReportInput:
    messages = [
        DebateMessage(
            message_id=msg.message_id,
            user_id=msg.user_id,
            side=msg.side,
            content=msg.content,
        )
        for msg in request.messages
    ]
    report = build_report_core(
        job_id=request.job.job_id,
        style_mode=request.job.style_mode,
        rejudge_triggered=request.job.rejudge_triggered,
        messages=messages,
        message_window_size=request.message_window_size,
        rubric_version=request.rubric_version,
    )
    return SubmitJudgeReportInput(**report)
