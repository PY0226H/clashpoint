from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.applications.trust_challenge_ops_queue_routes import (
    TrustChallengeOpsQueueRouteError,
    build_trust_challenge_ops_queue_route_payload,
)


@dataclass
class _Job:
    job_id: int
    updated_at: datetime


@dataclass
class _Trace:
    status: str
    callback_status: str | None
    callback_error: str | None
    updated_at: datetime
    report_summary: dict[str, Any]


@dataclass
class _RouteLikeError(Exception):
    status_code: int
    detail: Any


class TrustChallengeOpsQueueRoutesTests(unittest.TestCase):
    def test_route_should_raise_for_invalid_sort_by(self) -> None:
        async def _workflow_list_jobs(**kwargs: Any) -> list[_Job]:
            del kwargs
            return []

        with self.assertRaises(TrustChallengeOpsQueueRouteError) as ctx:
            asyncio.run(
                build_trust_challenge_ops_queue_route_payload(
                    status=None,
                    dispatch_type="auto",
                    challenge_state="open",
                    review_state=None,
                    priority_level=None,
                    sla_bucket=None,
                    has_open_alert=None,
                    sort_by="bad-sort",
                    sort_order="desc",
                    scan_limit=50,
                    offset=0,
                    limit=20,
                    normalize_workflow_status=lambda value: value,
                    workflow_statuses={"queued", "review_required", "callback_reported"},
                    normalize_trust_challenge_state_filter=lambda value: value,
                    case_fairness_challenge_states={"challenge_closed"},
                    normalize_trust_challenge_review_state=lambda value: value,
                    trust_challenge_review_state_values={"pending_review", "approved"},
                    normalize_trust_challenge_priority_level=lambda value: value,
                    trust_challenge_priority_level_values={"high", "medium", "low"},
                    normalize_trust_challenge_sla_bucket=lambda value: value,
                    trust_challenge_sla_bucket_values={"normal", "warning", "urgent", "unknown"},
                    normalize_trust_challenge_sort_by=lambda value: str(value or ""),
                    trust_challenge_sort_fields={"priority_score", "case_id"},
                    normalize_trust_challenge_sort_order=lambda value: str(value or ""),
                    trust_challenge_open_states={"under_internal_review"},
                    workflow_list_jobs=_workflow_list_jobs,
                    build_trust_phasea_bundle=lambda **kwargs: kwargs,
                    get_trace=lambda _job_id: None,
                    build_trust_challenge_priority_profile=lambda **kwargs: kwargs,
                    serialize_workflow_job=lambda _job: {},
                    build_trust_challenge_ops_queue_item=lambda **kwargs: kwargs,
                    build_trust_challenge_action_hints=lambda **kwargs: [],
                    build_trust_challenge_sort_key=lambda **kwargs: (0,),
                    build_trust_challenge_ops_queue_payload=lambda **kwargs: kwargs,
                    validate_trust_challenge_ops_queue_contract=lambda _payload: None,
                )
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "invalid_trust_sort_by")

    def test_route_should_build_filtered_payload(self) -> None:
        now = datetime.now(timezone.utc)
        jobs = [_Job(job_id=4001, updated_at=now), _Job(job_id=4002, updated_at=now)]

        async def _workflow_list_jobs(**kwargs: Any) -> list[_Job]:
            self.assertEqual(kwargs["dispatch_type"], None)
            return jobs

        async def _build_trust_phasea_bundle(*, case_id: int, dispatch_type: str) -> dict[str, Any]:
            self.assertEqual(dispatch_type, "auto")
            if case_id == 4001:
                return {
                    "context": {
                        "dispatchType": "final",
                        "traceId": "trace-4001",
                        "reportPayload": {},
                    },
                    "challengeReview": {
                        "challengeState": "under_internal_review",
                        "reviewState": "pending_review",
                        "activeChallengeId": "ch-4001",
                    },
                }
            raise _RouteLikeError(status_code=404, detail="trust_receipt_not_found")

        def _get_trace(job_id: int) -> _Trace | None:
            if job_id != 4001:
                return None
            return _Trace(
                status="reported",
                callback_status="reported",
                callback_error=None,
                updated_at=now,
                report_summary={},
            )

        payload = asyncio.run(
            build_trust_challenge_ops_queue_route_payload(
                status=None,
                dispatch_type="auto",
                challenge_state="open",
                review_state="pending_review",
                priority_level="high",
                sla_bucket="warning",
                has_open_alert=True,
                sort_by="priority_score",
                sort_order="desc",
                scan_limit=100,
                offset=0,
                limit=20,
                normalize_workflow_status=lambda value: value,
                workflow_statuses={"queued", "review_required", "callback_reported"},
                normalize_trust_challenge_state_filter=lambda value: value,
                case_fairness_challenge_states={"challenge_closed", "under_internal_review"},
                normalize_trust_challenge_review_state=lambda value: value,
                trust_challenge_review_state_values={"pending_review", "approved"},
                normalize_trust_challenge_priority_level=lambda value: value,
                trust_challenge_priority_level_values={"high", "medium", "low"},
                normalize_trust_challenge_sla_bucket=lambda value: value,
                trust_challenge_sla_bucket_values={"normal", "warning", "urgent", "unknown"},
                normalize_trust_challenge_sort_by=lambda value: str(value or "priority_score"),
                trust_challenge_sort_fields={"priority_score", "case_id"},
                normalize_trust_challenge_sort_order=lambda value: str(value or "desc"),
                trust_challenge_open_states={"under_internal_review", "challenge_requested"},
                workflow_list_jobs=_workflow_list_jobs,
                build_trust_phasea_bundle=_build_trust_phasea_bundle,
                get_trace=_get_trace,
                build_trust_challenge_priority_profile=lambda **kwargs: {
                    "level": "high",
                    "slaBucket": "warning",
                    "openAlertCount": 1,
                    "score": 88,
                },
                serialize_workflow_job=lambda job: {"caseId": int(job.job_id), "updatedAt": now.isoformat()},
                build_trust_challenge_ops_queue_item=lambda **kwargs: {
                    "caseId": kwargs["case_id"],
                    "challengeReview": {
                        "state": kwargs["challenge_review"]["challengeState"],
                        "activeChallengeId": kwargs["active_challenge_id"],
                    },
                    "workflow": kwargs["workflow"],
                    "priorityProfile": kwargs["priority_profile"],
                },
                build_trust_challenge_action_hints=lambda **kwargs: ["trust.challenge.decide"],
                build_trust_challenge_sort_key=lambda **kwargs: (
                    int(kwargs["item"]["priorityProfile"]["score"]),
                    int(kwargs["item"]["caseId"]),
                ),
                build_trust_challenge_ops_queue_payload=lambda **kwargs: {
                    "count": len(kwargs["items"]),
                    "returned": len(kwargs["page_items"]),
                    "summary": {
                        "openCount": len(kwargs["items"]),
                        "urgentCount": 0,
                        "highPriorityCount": len(kwargs["items"]),
                        "oldestOpenAgeMinutes": None,
                        "stateCounts": {"under_internal_review": len(kwargs["items"])},
                        "reviewStateCounts": {"pending_review": len(kwargs["items"])},
                        "priorityLevelCounts": {"high": len(kwargs["items"])},
                        "slaBucketCounts": {"warning": len(kwargs["items"])},
                        "reasonCodeCounts": {},
                        "actionHintCounts": {"trust.challenge.decide": len(kwargs["items"])},
                    },
                    "items": kwargs["page_items"],
                    "errors": kwargs["errors"],
                    "filters": kwargs["filters"],
                },
                validate_trust_challenge_ops_queue_contract=lambda _payload: None,
            )
        )

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["returned"], 1)
        self.assertEqual(payload["summary"]["highPriorityCount"], 1)
        self.assertEqual(payload["items"][0]["caseId"], 4001)
        self.assertEqual(payload["items"][0]["actionHints"], ["trust.challenge.decide"])
        self.assertEqual(payload["errors"][0]["caseId"], 4002)
        self.assertEqual(payload["errors"][0]["errorCode"], "trust_receipt_not_found")

    def test_route_should_raise_when_contract_validation_fails(self) -> None:
        async def _workflow_list_jobs(**kwargs: Any) -> list[_Job]:
            del kwargs
            return []

        def _validate_contract(_payload: dict[str, Any]) -> None:
            raise ValueError("trust_challenge_queue_missing_keys:items")

        with self.assertRaises(TrustChallengeOpsQueueRouteError) as ctx:
            asyncio.run(
                build_trust_challenge_ops_queue_route_payload(
                    status=None,
                    dispatch_type="auto",
                    challenge_state="open",
                    review_state=None,
                    priority_level=None,
                    sla_bucket=None,
                    has_open_alert=None,
                    sort_by="priority_score",
                    sort_order="desc",
                    scan_limit=50,
                    offset=0,
                    limit=20,
                    normalize_workflow_status=lambda value: value,
                    workflow_statuses={"queued", "review_required", "callback_reported"},
                    normalize_trust_challenge_state_filter=lambda value: value,
                    case_fairness_challenge_states={"challenge_closed"},
                    normalize_trust_challenge_review_state=lambda value: value,
                    trust_challenge_review_state_values={"pending_review", "approved"},
                    normalize_trust_challenge_priority_level=lambda value: value,
                    trust_challenge_priority_level_values={"high", "medium", "low"},
                    normalize_trust_challenge_sla_bucket=lambda value: value,
                    trust_challenge_sla_bucket_values={"normal", "warning", "urgent", "unknown"},
                    normalize_trust_challenge_sort_by=lambda value: str(value or "priority_score"),
                    trust_challenge_sort_fields={"priority_score", "case_id"},
                    normalize_trust_challenge_sort_order=lambda value: str(value or "desc"),
                    trust_challenge_open_states={"under_internal_review"},
                    workflow_list_jobs=_workflow_list_jobs,
                    build_trust_phasea_bundle=lambda **kwargs: kwargs,
                    get_trace=lambda _job_id: None,
                    build_trust_challenge_priority_profile=lambda **kwargs: kwargs,
                    serialize_workflow_job=lambda _job: {},
                    build_trust_challenge_ops_queue_item=lambda **kwargs: kwargs,
                    build_trust_challenge_action_hints=lambda **kwargs: [],
                    build_trust_challenge_sort_key=lambda **kwargs: (0,),
                    build_trust_challenge_ops_queue_payload=lambda **kwargs: kwargs,
                    validate_trust_challenge_ops_queue_contract=_validate_contract,
                )
            )

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(
            ctx.exception.detail["code"],
            "trust_challenge_ops_queue_contract_violation",
        )
        self.assertIn(
            "trust_challenge_queue_missing_keys:items",
            ctx.exception.detail["message"],
        )


if __name__ == "__main__":
    unittest.main()
