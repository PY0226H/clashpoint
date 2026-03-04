from __future__ import annotations

import re

from fastapi import HTTPException

from .models import JudgeDispatchRequest

_FORBIDDEN_SPEAKER_TAG_HINTS = (
    "user_id",
    "uid",
    "充值",
    "粉丝",
    "follower",
    "balance",
    "vip",
)


def validate_blinded_dispatch_request(request: JudgeDispatchRequest) -> None:
    """Ensure upstream payload is blinded before entering judge model runtime."""
    if not request.messages:
        return

    for msg in request.messages:
        if msg.user_id is not None:
            raise HTTPException(
                status_code=422,
                detail="unblinded_user_id_in_messages",
            )
        speaker_tag = (msg.speaker_tag or "").strip().lower()
        if not speaker_tag:
            continue
        for hint in _FORBIDDEN_SPEAKER_TAG_HINTS:
            if hint in speaker_tag:
                raise HTTPException(
                    status_code=422,
                    detail="unblinded_speaker_tag_in_messages",
                )
        if re.search(r"\\b(user|uid|follower|balance|vip)\\b", speaker_tag, re.IGNORECASE):
            raise HTTPException(
                status_code=422,
                detail="unblinded_speaker_tag_in_messages",
            )
