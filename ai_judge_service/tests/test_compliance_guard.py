import unittest
from datetime import datetime, timezone

from fastapi import HTTPException

from app.compliance_guard import validate_blinded_dispatch_request
from app.models import (
    DispatchJob,
    DispatchMessage,
    DispatchSession,
    DispatchTopic,
    JudgeDispatchRequest,
)


def _build_request(*, user_id: int | None = None, speaker_tag: str | None = "pro_1") -> JudgeDispatchRequest:
    now = datetime.now(timezone.utc)
    return JudgeDispatchRequest(
        job=DispatchJob(
            job_id=1,
            ws_id=1,
            session_id=2,
            requested_by=1,
            style_mode="rational",
            rejudge_triggered=False,
            requested_at=now,
        ),
        session=DispatchSession(
            status="judging",
            scheduled_start_at=now,
            actual_start_at=now,
            end_at=now,
        ),
        topic=DispatchTopic(
            title="topic",
            description="desc",
            category="game",
            stance_pro="pro",
            stance_con="con",
            context_seed=None,
        ),
        messages=[
            DispatchMessage(
                message_id=1,
                speaker_tag=speaker_tag,
                user_id=user_id,
                side="pro",
                content="test",
                created_at=now,
            )
        ],
        message_window_size=100,
        rubric_version="v1",
    )


class ComplianceGuardTests(unittest.TestCase):
    def test_validate_blinded_dispatch_request_should_allow_blinded_message(self) -> None:
        request = _build_request(user_id=None, speaker_tag="pro_1")
        validate_blinded_dispatch_request(request)

    def test_validate_blinded_dispatch_request_should_reject_user_id(self) -> None:
        request = _build_request(user_id=123, speaker_tag="pro_1")
        with self.assertRaises(HTTPException) as ctx:
            validate_blinded_dispatch_request(request)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "unblinded_user_id_in_messages")

    def test_validate_blinded_dispatch_request_should_reject_sensitive_speaker_tag(self) -> None:
        request = _build_request(user_id=None, speaker_tag="uid_99")
        with self.assertRaises(HTTPException) as ctx:
            validate_blinded_dispatch_request(request)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "unblinded_speaker_tag_in_messages")


if __name__ == "__main__":
    unittest.main()
