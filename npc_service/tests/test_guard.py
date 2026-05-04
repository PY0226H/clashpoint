from __future__ import annotations

import pytest
from app.guard import (
    NpcGuardError,
    NpcNoAction,
    assert_no_forbidden_fields,
    candidate_from_raw_output,
)

from helpers import make_context, make_settings


def test_guard_rejects_official_verdict_fields_at_any_depth() -> None:
    with pytest.raises(NpcGuardError) as err:
        assert_no_forbidden_fields({"actionType": "praise", "meta": {"winner": "pro"}})

    assert err.value.reason_code == "official_verdict_field_forbidden"


def test_candidate_from_raw_output_rejects_overlong_public_text() -> None:
    with pytest.raises(NpcGuardError) as err:
        candidate_from_raw_output(
            {
                "actionType": "speak",
                "publicText": "x" * 501,
            },
            context=make_context(),
            settings=make_settings(),
            executor_kind="llm_executor_v1",
            executor_version="llm_executor_v1",
        )

    assert err.value.reason_code == "public_text_too_long"


def test_candidate_from_raw_output_allows_explicit_no_action_signal() -> None:
    with pytest.raises(NpcNoAction) as err:
        candidate_from_raw_output(
            {
                "actionType": "no_action",
                "reasonCode": "stay_quiet",
            },
            context=make_context(),
            settings=make_settings(),
            executor_kind="llm_executor_v1",
            executor_version="llm_executor_v1",
        )

    assert err.value.reason_code == "llm_no_action"


def test_candidate_from_raw_output_builds_public_praise_candidate() -> None:
    candidate = candidate_from_raw_output(
        {
            "actionType": "praise",
            "publicText": "这段回应抓住了关键。",
            "targetMessageId": 1001,
            "effectKind": "sparkle",
            "npcStatus": "praising",
            "reasonCode": "strong_turn",
        },
        context=make_context(),
        settings=make_settings(),
        executor_kind="llm_executor_v1",
        executor_version="llm_executor_v1",
    )

    payload = candidate.model_dump(by_alias=True, exclude_none=True)

    assert candidate.action_type == "praise"
    assert candidate.target_message_id == 1001
    assert candidate.action_uid.startswith("npc_action:")
    assert payload == {
        "actionUid": candidate.action_uid,
        "sessionId": 77,
        "npcId": "virtual_judge_default",
        "actionType": "praise",
        "publicText": "这段回应抓住了关键。",
        "targetMessageId": 1001,
        "targetUserId": 42,
        "targetSide": "pro",
        "effectKind": "sparkle",
        "npcStatus": "praising",
        "reasonCode": "strong_turn",
        "sourceEventId": "evt-1",
        "sourceMessageId": 1001,
        "policyVersion": "npc_policy_test",
        "executorKind": "llm_executor_v1",
        "executorVersion": "llm_executor_v1",
    }
