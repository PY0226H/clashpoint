from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.applications.bootstrap_review_trust_helpers import (
    build_review_case_risk_profile_for_runtime,
    build_review_trust_unified_priority_profile_for_runtime,
    build_trust_challenge_action_hints_for_runtime,
    build_trust_challenge_id_for_runtime,
    build_trust_challenge_priority_profile_for_runtime,
)


class BootstrapReviewTrustHelpersTests(unittest.TestCase):
    def test_review_and_trust_helpers_should_inject_runtime_dependencies(self) -> None:
        now = datetime(2026, 4, 24, 8, 30, tzinfo=timezone.utc)
        open_states = {"requested", "under_review"}

        def _normalize(value: datetime | None) -> datetime | None:
            return value

        with patch(
            "app.applications.bootstrap_review_trust_helpers.build_review_case_risk_profile_v3"
        ) as risk_profile:
            risk_profile.return_value = {"score": 12}

            result = build_review_case_risk_profile_for_runtime(
                workflow=object(),
                report_payload={"winner": "pro"},
                report_summary={"callbackStatus": "reported"},
                now=now,
                normalize_query_datetime=_normalize,
            )

        self.assertEqual(result, {"score": 12})
        risk_profile.assert_called_once()
        self.assertIs(risk_profile.call_args.kwargs["normalize_query_datetime"], _normalize)

        with patch(
            "app.applications.bootstrap_review_trust_helpers.build_trust_challenge_priority_profile_v3"
        ) as priority_profile:
            priority_profile.return_value = {"level": "high"}

            result = build_trust_challenge_priority_profile_for_runtime(
                workflow=object(),
                challenge_review={"challengeState": "requested"},
                report_payload={"winner": "draw"},
                report_summary={},
                now=now,
                normalize_query_datetime=_normalize,
                trust_challenge_open_states=open_states,
            )

        self.assertEqual(result, {"level": "high"})
        priority_profile.assert_called_once()
        self.assertIs(
            priority_profile.call_args.kwargs["trust_challenge_open_states"],
            open_states,
        )

        with patch(
            "app.applications.bootstrap_review_trust_helpers.build_trust_challenge_action_hints_v3"
        ) as action_hints:
            action_hints.return_value = ["trust.challenge.decide"]

            result = build_trust_challenge_action_hints_for_runtime(
                challenge_review={"challengeState": "requested"},
                priority_profile={"level": "high"},
                trust_challenge_open_states=open_states,
            )

        self.assertEqual(result, ["trust.challenge.decide"])
        action_hints.assert_called_once_with(
            challenge_review={"challengeState": "requested"},
            priority_profile={"level": "high"},
            trust_challenge_open_states=open_states,
        )

        with patch(
            "app.applications.bootstrap_review_trust_helpers.build_review_trust_unified_priority_profile_v3"
        ) as unified_profile:
            unified_profile.return_value = {"score": 88}

            result = build_review_trust_unified_priority_profile_for_runtime(
                risk_profile={"score": 30},
                trust_priority_profile={"score": 88},
                challenge_review={"challengeState": "requested"},
                trust_challenge_open_states=open_states,
            )

        self.assertEqual(result, {"score": 88})
        unified_profile.assert_called_once_with(
            risk_profile={"score": 30},
            trust_priority_profile={"score": 88},
            challenge_review={"challengeState": "requested"},
            trust_challenge_open_states=open_states,
        )

    def test_build_trust_challenge_id_should_use_positive_case_id_prefix(self) -> None:
        challenge_id = build_trust_challenge_id_for_runtime(case_id=42)

        self.assertRegex(challenge_id, r"^chlg-42-[0-9a-f]{12}$")

    def test_build_trust_challenge_id_should_clamp_negative_case_id(self) -> None:
        challenge_id = build_trust_challenge_id_for_runtime(case_id=-7)

        self.assertRegex(challenge_id, r"^chlg-0-[0-9a-f]{12}$")
