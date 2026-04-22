from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.applications.case_read_routes import (
    CaseReadRouteError,
    build_case_claim_ledger_route_payload,
    build_case_courtroom_cases_route_payload,
    build_case_courtroom_drilldown_bundle_route_payload,
    build_case_courtroom_read_model_payload,
    build_case_courtroom_read_model_route_payload,
    build_case_evidence_claim_ops_queue_route_payload,
    build_case_overview_payload,
    build_case_overview_replay_items,
    build_case_overview_route_payload,
)


@dataclass
class _DummyReplayRecord:
    dispatch_type: str | None
    trace_id: str | None
    created_at: datetime
    winner: str | None
    needs_draw_vote: bool | None
    provider: str | None


@dataclass
class _DummyTraceReplay:
    replayed_at: datetime
    winner: str | None
    needs_draw_vote: bool | None
    provider: str | None


@dataclass
class _DummyTrace:
    trace_id: str
    replays: list[Any]


class CaseReadRoutesTests(unittest.TestCase):
    def test_build_case_overview_route_payload_should_raise_404_when_case_missing(self) -> None:
        with self.assertRaises(CaseReadRouteError) as ctx:
            asyncio.run(
                build_case_overview_route_payload(
                    case_id=9601,
                    workflow_get_job=lambda **kwargs: asyncio.sleep(0, result=None),
                    workflow_list_events=lambda **kwargs: asyncio.sleep(0, result=[]),
                    get_dispatch_receipt=lambda **kwargs: asyncio.sleep(0, result=None),
                    trace_get=lambda case_id: None,
                    list_replay_records=lambda **kwargs: asyncio.sleep(0, result=[]),
                    list_audit_alerts=lambda **kwargs: asyncio.sleep(0, result=[]),
                    get_claim_ledger_record=lambda **kwargs: asyncio.sleep(0, result=None),
                    build_verdict_contract=lambda report_payload: {},
                    build_case_evidence_view=lambda **kwargs: {},
                    build_judge_core_view=lambda **kwargs: None,
                    build_case_overview_replay_items=lambda **kwargs: [],
                    build_case_overview_payload=lambda **kwargs: {},
                    serialize_workflow_job=lambda item: {},
                    serialize_dispatch_receipt=lambda item: {},
                    serialize_alert_item=lambda item: {},
                )
            )
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "case_not_found")

    def test_build_case_overview_route_payload_should_build_payload(self) -> None:
        created_at = datetime(2026, 4, 21, 0, 0, tzinfo=timezone.utc)
        trace = _DummyTrace(
            trace_id="trace-9602",
            replays=[],
        )
        trace.status = "reported"
        trace.created_at = created_at
        trace.updated_at = created_at
        trace.report_summary = {"payload": {"winner": "pro"}, "callbackStatus": "reported"}
        trace.callback_status = "reported"
        trace.callback_error = None

        workflow_job = type("Job", (), {"job_id": 9602})()
        workflow_event = type(
            "Evt",
            (),
            {
                "event_seq": 1,
                "event_type": "judge.reported",
                "payload": {"status": "reported"},
                "created_at": created_at,
            },
        )()
        phase_receipt = type("Receipt", (), {"response": {"winner": "con"}})()
        final_receipt = type("Receipt", (), {"response": {"reportPayload": {"winner": "pro"}}})()

        payload = asyncio.run(
            build_case_overview_route_payload(
                case_id=9602,
                workflow_get_job=lambda **kwargs: asyncio.sleep(0, result=workflow_job),
                workflow_list_events=lambda **kwargs: asyncio.sleep(0, result=[workflow_event]),
                get_dispatch_receipt=lambda **kwargs: asyncio.sleep(
                    0,
                    result=(final_receipt if kwargs.get("dispatch_type") == "final" else phase_receipt),
                ),
                trace_get=lambda case_id: trace,
                list_replay_records=lambda **kwargs: asyncio.sleep(0, result=[]),
                list_audit_alerts=lambda **kwargs: asyncio.sleep(0, result=[{"alert_id": "a1"}]),
                get_claim_ledger_record=lambda **kwargs: asyncio.sleep(0, result={"dispatchType": "final"}),
                build_verdict_contract=lambda report_payload: {
                    "winner": report_payload.get("winner"),
                    "needsDrawVote": False,
                    "reviewRequired": False,
                },
                build_case_evidence_view=lambda **kwargs: {"hasCaseDossier": True},
                build_judge_core_view=lambda **kwargs: {"stage": "reported", "version": "v1"},
                build_case_overview_replay_items=lambda **kwargs: [{"traceId": "trace-9602"}],
                build_case_overview_payload=lambda **kwargs: dict(kwargs),
                serialize_workflow_job=lambda item: {"jobId": item.job_id},
                serialize_dispatch_receipt=lambda item: {"hasResponse": bool(getattr(item, "response", {}))},
                serialize_alert_item=lambda item: {"alertId": item["alert_id"]},
            )
        )

        self.assertEqual(payload["case_id"], 9602)
        self.assertEqual(payload["winner"], "pro")
        self.assertEqual(payload["latest_dispatch_type"], "final")
        self.assertEqual(payload["callback_status"], "reported")
        self.assertEqual(payload["workflow"]["jobId"], 9602)
        self.assertEqual(len(payload["events"]), 1)
        self.assertEqual(payload["alerts"][0]["alertId"], "a1")

    def test_build_case_claim_ledger_route_payload_should_raise_422_for_invalid_dispatch_type(
        self,
    ) -> None:
        with self.assertRaises(CaseReadRouteError) as ctx:
            asyncio.run(
                build_case_claim_ledger_route_payload(
                    case_id=9701,
                    dispatch_type="invalid",
                    limit=20,
                    list_claim_ledger_records=lambda **kwargs: asyncio.sleep(0, result=[]),
                    get_claim_ledger_record=lambda **kwargs: asyncio.sleep(0, result=None),
                    serialize_claim_ledger_record=lambda item, include_payload: {},
                )
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "invalid_dispatch_type")

    def test_build_case_claim_ledger_route_payload_should_build_auto_records_payload(self) -> None:
        primary = type(
            "Ledger",
            (),
            {"dispatch_type": "final", "trace_id": "trace-9702"},
        )()
        secondary = type(
            "Ledger",
            (),
            {"dispatch_type": "phase", "trace_id": "trace-9702-phase"},
        )()

        payload = asyncio.run(
            build_case_claim_ledger_route_payload(
                case_id=9702,
                dispatch_type="auto",
                limit=20,
                list_claim_ledger_records=lambda **kwargs: asyncio.sleep(
                    0,
                    result=[primary, secondary],
                ),
                get_claim_ledger_record=lambda **kwargs: asyncio.sleep(0, result=None),
                serialize_claim_ledger_record=lambda item, include_payload: {
                    "dispatchType": item.dispatch_type,
                    "traceId": item.trace_id,
                    "includePayload": bool(include_payload),
                },
            )
        )

        self.assertEqual(payload["caseId"], 9702)
        self.assertEqual(payload["dispatchType"], "final")
        self.assertEqual(payload["traceId"], "trace-9702")
        self.assertEqual(payload["count"], 2)
        self.assertTrue(payload["item"]["includePayload"])
        self.assertFalse(payload["items"][0]["includePayload"])
        self.assertEqual(payload["items"][1]["dispatchType"], "phase")

    def test_build_case_courtroom_read_model_route_payload_should_map_context_error(self) -> None:
        class _ContextErr(Exception):
            status_code = 404
            detail = "courtroom_case_not_found"

        async def _raise_context(**kwargs: Any) -> dict[str, Any]:
            raise _ContextErr()

        with self.assertRaises(CaseReadRouteError) as ctx:
            asyncio.run(
                build_case_courtroom_read_model_route_payload(
                    case_id=9801,
                    dispatch_type="auto",
                    include_events=False,
                    include_alerts=True,
                    alert_limit=200,
                    resolve_report_context_for_case=_raise_context,
                    workflow_get_job=lambda **kwargs: asyncio.sleep(0, result=None),
                    workflow_list_events=lambda **kwargs: asyncio.sleep(0, result=[]),
                    trace_get=lambda case_id: None,
                    get_claim_ledger_record=lambda **kwargs: asyncio.sleep(0, result=None),
                    build_verdict_contract=lambda payload: {},
                    build_case_evidence_view=lambda **kwargs: {},
                    build_courtroom_read_model_view=lambda **kwargs: {},
                    build_judge_core_view=lambda **kwargs: None,
                    list_audit_alerts=lambda **kwargs: asyncio.sleep(0, result=[]),
                    build_case_courtroom_read_model_payload=lambda **kwargs: {},
                    serialize_workflow_job=lambda job: {},
                    serialize_alert_item=lambda item: {},
                )
            )
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "courtroom_case_not_found")

    def test_build_case_courtroom_read_model_route_payload_should_build_payload(self) -> None:
        created_at = datetime(2026, 4, 21, 0, 2, tzinfo=timezone.utc)
        trace = _DummyTrace(trace_id="trace-9802", replays=[])
        trace.report_summary = {"callbackStatus": "reported", "callbackError": None}
        trace.callback_status = "reported"
        trace.callback_error = None

        workflow_job = type("Job", (), {"job_id": 9802})()
        workflow_event = type(
            "Evt",
            (),
            {
                "event_seq": 2,
                "event_type": "judge.reported",
                "payload": {"status": "reported"},
                "created_at": created_at,
            },
        )()

        payload = asyncio.run(
            build_case_courtroom_read_model_route_payload(
                case_id=9802,
                dispatch_type="auto",
                include_events=True,
                include_alerts=True,
                alert_limit=200,
                resolve_report_context_for_case=lambda **kwargs: asyncio.sleep(
                    0,
                    result={
                        "dispatchType": "final",
                        "traceId": "trace-9802",
                        "reportPayload": {"winner": "pro", "reviewRequired": False},
                        "responsePayload": {"callbackStatus": "reported"},
                    },
                ),
                workflow_get_job=lambda **kwargs: asyncio.sleep(0, result=workflow_job),
                workflow_list_events=lambda **kwargs: asyncio.sleep(0, result=[workflow_event]),
                trace_get=lambda case_id: trace,
                get_claim_ledger_record=lambda **kwargs: asyncio.sleep(0, result={"dispatchType": "final"}),
                build_verdict_contract=lambda report_payload: {"winner": report_payload.get("winner")},
                build_case_evidence_view=lambda **kwargs: {"hasCaseDossier": True},
                build_courtroom_read_model_view=lambda **kwargs: {"recorder": {"ok": True}},
                build_judge_core_view=lambda **kwargs: {"stage": "reported", "version": "v1"},
                list_audit_alerts=lambda **kwargs: asyncio.sleep(0, result=[{"alert_id": "alert-1"}]),
                build_case_courtroom_read_model_payload=lambda **kwargs: dict(kwargs),
                serialize_workflow_job=lambda job: {"jobId": job.job_id},
                serialize_alert_item=lambda item: {"alertId": item["alert_id"]},
            )
        )

        self.assertEqual(payload["case_id"], 9802)
        self.assertEqual(payload["dispatch_type"], "final")
        self.assertEqual(payload["trace_id"], "trace-9802")
        self.assertEqual(payload["workflow"]["jobId"], 9802)
        self.assertEqual(payload["callback_status"], "reported")
        self.assertEqual(payload["event_count"], 1)
        self.assertEqual(payload["alerts"][0]["alertId"], "alert-1")
        self.assertEqual(payload["courtroom"]["recorder"]["ok"], True)

    def test_build_case_courtroom_cases_route_payload_should_validate_query_values(self) -> None:
        with self.assertRaises(CaseReadRouteError) as ctx:
            asyncio.run(
                build_case_courtroom_cases_route_payload(
                    status=None,
                    dispatch_type="auto",
                    winner="invalid",
                    review_required=None,
                    risk_level=None,
                    sla_bucket=None,
                    updated_from=None,
                    updated_to=None,
                    sort_by="updated_at",
                    sort_order="desc",
                    scan_limit=500,
                    offset=0,
                    limit=50,
                    normalize_workflow_status=lambda value: value,
                    workflow_statuses={"queued", "review_required", "callback_reported"},
                    normalize_review_case_risk_level=lambda value: value,
                    review_case_risk_level_values={"low", "medium", "high"},
                    normalize_review_case_sla_bucket=lambda value: value,
                    review_case_sla_bucket_values={"healthy", "warning", "critical"},
                    normalize_query_datetime=lambda value: value,
                    normalize_courtroom_case_sort_by=lambda value: str(value or "").strip().lower(),
                    normalize_courtroom_case_sort_order=lambda value: str(value or "").strip().lower(),
                    courtroom_case_sort_fields={"updated_at", "risk_score", "case_id"},
                    workflow_list_jobs=lambda **kwargs: asyncio.sleep(0, result=[]),
                    resolve_report_context_for_case=lambda **kwargs: asyncio.sleep(0, result={}),
                    trace_get=lambda case_id: None,
                    build_review_case_risk_profile=lambda **kwargs: {},
                    build_verdict_contract=lambda payload: {},
                    build_case_evidence_view=lambda **kwargs: {},
                    build_courtroom_read_model_view=lambda **kwargs: {},
                    serialize_workflow_job=lambda job: {},
                    build_courtroom_read_model_light_summary=lambda **kwargs: {},
                    build_courtroom_case_sort_key=lambda **kwargs: tuple(),
                )
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "invalid_winner")

    def test_build_case_courtroom_cases_route_payload_should_build_items(self) -> None:
        created_at = datetime(2026, 4, 21, 0, 3, tzinfo=timezone.utc)
        job = type(
            "Job",
            (),
            {
                "job_id": 9902,
                "updated_at": created_at,
                "status": "review_required",
            },
        )()
        trace = _DummyTrace(trace_id="trace-9902", replays=[])
        trace.report_summary = {"callbackStatus": "reported", "callbackError": None}
        trace.callback_status = "reported"
        trace.callback_error = None

        payload = asyncio.run(
            build_case_courtroom_cases_route_payload(
                status="review_required",
                dispatch_type="auto",
                winner="draw",
                review_required=True,
                risk_level="high",
                sla_bucket="critical",
                updated_from=created_at,
                updated_to=created_at,
                sort_by="case_id",
                sort_order="desc",
                scan_limit=500,
                offset=0,
                limit=50,
                normalize_workflow_status=lambda value: str(value or "").strip().lower() or None,
                workflow_statuses={"queued", "review_required", "callback_reported"},
                normalize_review_case_risk_level=lambda value: str(value or "").strip().lower() or None,
                review_case_risk_level_values={"low", "medium", "high"},
                normalize_review_case_sla_bucket=lambda value: str(value or "").strip().lower() or None,
                review_case_sla_bucket_values={"healthy", "warning", "critical"},
                normalize_query_datetime=lambda value: value,
                normalize_courtroom_case_sort_by=lambda value: str(value or "").strip().lower(),
                normalize_courtroom_case_sort_order=lambda value: str(value or "").strip().lower(),
                courtroom_case_sort_fields={"updated_at", "risk_score", "case_id"},
                workflow_list_jobs=lambda **kwargs: asyncio.sleep(0, result=[job]),
                resolve_report_context_for_case=lambda **kwargs: asyncio.sleep(
                    0,
                    result={
                        "dispatchType": "final",
                        "traceId": "trace-9902",
                        "reportPayload": {
                            "winner": "draw",
                            "reviewRequired": True,
                            "needsDrawVote": True,
                        },
                        "responsePayload": {"callbackStatus": "reported"},
                    },
                ),
                trace_get=lambda case_id: trace,
                build_review_case_risk_profile=lambda **kwargs: {
                    "level": "high",
                    "slaBucket": "critical",
                    "riskScore": 98,
                },
                build_verdict_contract=lambda payload: {"winner": payload.get("winner")},
                build_case_evidence_view=lambda **kwargs: {"hasCaseDossier": True},
                build_courtroom_read_model_view=lambda **kwargs: {"recorder": {"ok": True}},
                serialize_workflow_job=lambda workflow_job: {
                    "jobId": workflow_job.job_id,
                    "status": workflow_job.status,
                },
                build_courtroom_read_model_light_summary=lambda **kwargs: {
                    "recorder": kwargs.get("courtroom_view", {}).get("recorder", {}),
                },
                build_courtroom_case_sort_key=lambda **kwargs: (
                    int(kwargs.get("item", {}).get("caseId", 0)),
                ),
            )
        )

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["returned"], 1)
        self.assertEqual(payload["errorCount"], 0)
        item = payload["items"][0]
        self.assertEqual(item["caseId"], 9902)
        self.assertEqual(item["winner"], "draw")
        self.assertTrue(item["reviewRequired"])
        self.assertEqual(item["riskProfile"]["level"], "high")
        self.assertEqual(payload["filters"]["dispatchType"], "auto")
        self.assertEqual(payload["filters"]["winner"], "draw")

    def test_build_case_courtroom_drilldown_bundle_route_payload_should_validate_sort_by(
        self,
    ) -> None:
        with self.assertRaises(CaseReadRouteError) as ctx:
            asyncio.run(
                build_case_courtroom_drilldown_bundle_route_payload(
                    status=None,
                    dispatch_type="auto",
                    winner=None,
                    review_required=None,
                    risk_level=None,
                    sla_bucket=None,
                    updated_from=None,
                    updated_to=None,
                    sort_by="bad-value",
                    sort_order="desc",
                    scan_limit=500,
                    offset=0,
                    limit=50,
                    claim_preview_limit=10,
                    evidence_preview_limit=10,
                    panel_preview_limit=10,
                    normalize_workflow_status=lambda value: value,
                    workflow_statuses={"queued", "review_required", "callback_reported"},
                    normalize_review_case_risk_level=lambda value: value,
                    review_case_risk_level_values={"low", "medium", "high"},
                    normalize_review_case_sla_bucket=lambda value: value,
                    review_case_sla_bucket_values={"normal", "warning", "urgent"},
                    normalize_query_datetime=lambda value: value,
                    normalize_courtroom_case_sort_by=lambda value: str(value or "").strip().lower(),
                    normalize_courtroom_case_sort_order=lambda value: str(value or "").strip().lower(),
                    courtroom_case_sort_fields={"updated_at", "risk_score", "case_id"},
                    workflow_list_jobs=lambda **kwargs: asyncio.sleep(0, result=[]),
                    resolve_report_context_for_case=lambda **kwargs: asyncio.sleep(0, result={}),
                    trace_get=lambda case_id: None,
                    build_review_case_risk_profile=lambda **kwargs: {},
                    build_verdict_contract=lambda payload: {},
                    build_case_evidence_view=lambda **kwargs: {},
                    build_courtroom_read_model_view=lambda **kwargs: {},
                    build_courtroom_drilldown_bundle_view=lambda **kwargs: {},
                    build_courtroom_drilldown_action_hints=lambda **kwargs: [],
                    serialize_workflow_job=lambda workflow_job: {},
                    build_courtroom_case_sort_key=lambda **kwargs: tuple(),
                )
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "invalid_courtroom_drilldown_sort_by")

    def test_build_case_courtroom_drilldown_bundle_route_payload_should_build_items(
        self,
    ) -> None:
        created_at = datetime(2026, 4, 21, 0, 4, tzinfo=timezone.utc)
        job = type(
            "Job",
            (),
            {
                "job_id": 9911,
                "updated_at": created_at,
                "status": "review_required",
            },
        )()
        trace = _DummyTrace(trace_id="trace-9911", replays=[])
        trace.report_summary = {"callbackStatus": "reported", "callbackError": None}
        trace.callback_status = "reported"
        trace.callback_error = None

        payload = asyncio.run(
            build_case_courtroom_drilldown_bundle_route_payload(
                status="review_required",
                dispatch_type="auto",
                winner="draw",
                review_required=True,
                risk_level="high",
                sla_bucket="urgent",
                updated_from=created_at,
                updated_to=created_at,
                sort_by="case_id",
                sort_order="desc",
                scan_limit=500,
                offset=0,
                limit=50,
                claim_preview_limit=5,
                evidence_preview_limit=5,
                panel_preview_limit=5,
                normalize_workflow_status=lambda value: str(value or "").strip().lower() or None,
                workflow_statuses={"queued", "review_required", "callback_reported"},
                normalize_review_case_risk_level=lambda value: str(value or "").strip().lower() or None,
                review_case_risk_level_values={"low", "medium", "high"},
                normalize_review_case_sla_bucket=lambda value: str(value or "").strip().lower() or None,
                review_case_sla_bucket_values={"normal", "warning", "urgent"},
                normalize_query_datetime=lambda value: value,
                normalize_courtroom_case_sort_by=lambda value: str(value or "").strip().lower(),
                normalize_courtroom_case_sort_order=lambda value: str(value or "").strip().lower(),
                courtroom_case_sort_fields={"updated_at", "risk_score", "case_id"},
                workflow_list_jobs=lambda **kwargs: asyncio.sleep(0, result=[job]),
                resolve_report_context_for_case=lambda **kwargs: asyncio.sleep(
                    0,
                    result={
                        "dispatchType": "final",
                        "traceId": "trace-9911",
                        "reportPayload": {
                            "winner": "draw",
                            "reviewRequired": True,
                            "needsDrawVote": True,
                        },
                        "responsePayload": {"callbackStatus": "reported"},
                    },
                ),
                trace_get=lambda case_id: trace,
                build_review_case_risk_profile=lambda **kwargs: {
                    "level": "high",
                    "slaBucket": "urgent",
                    "score": 96,
                },
                build_verdict_contract=lambda payload: {"winner": payload.get("winner")},
                build_case_evidence_view=lambda **kwargs: {"hasCaseDossier": True},
                build_courtroom_read_model_view=lambda **kwargs: {"recorder": {"ok": True}},
                build_courtroom_drilldown_bundle_view=lambda **kwargs: {
                    "claim": {"conflictPairCount": 2, "unansweredClaimCount": 1},
                    "evidence": {"decisiveEvidenceCount": 1},
                    "panel": {"pivotalMomentCount": 1},
                    "fairness": {"reviewRequired": True},
                    "opinion": {},
                    "governance": {},
                },
                build_courtroom_drilldown_action_hints=lambda **kwargs: [
                    "claim.resolve_conflict",
                    "review.queue.decide",
                ],
                serialize_workflow_job=lambda workflow_job: {
                    "caseId": workflow_job.job_id,
                    "status": workflow_job.status,
                },
                build_courtroom_case_sort_key=lambda **kwargs: (
                    int(kwargs.get("item", {}).get("caseId", 0)),
                ),
            )
        )

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["returned"], 1)
        self.assertEqual(payload["errorCount"], 0)
        self.assertEqual(payload["aggregations"]["totalConflictPairCount"], 2)
        self.assertEqual(payload["aggregations"]["totalUnansweredClaimCount"], 1)
        self.assertEqual(payload["aggregations"]["totalPivotalMomentCount"], 1)
        self.assertEqual(payload["filters"]["claimPreviewLimit"], 5)
        self.assertEqual(payload["filters"]["dispatchType"], "auto")
        item = payload["items"][0]
        self.assertEqual(item["caseId"], 9911)
        self.assertEqual(item["dispatchType"], "final")
        self.assertEqual(item["traceId"], "trace-9911")
        self.assertEqual(item["callbackStatus"], "reported")
        self.assertIn("claim.resolve_conflict", item["actionHints"])

    def test_build_case_evidence_claim_ops_queue_route_payload_should_validate_reliability(
        self,
    ) -> None:
        with self.assertRaises(CaseReadRouteError) as ctx:
            asyncio.run(
                build_case_evidence_claim_ops_queue_route_payload(
                    status=None,
                    dispatch_type="auto",
                    winner=None,
                    review_required=None,
                    risk_level=None,
                    sla_bucket=None,
                    reliability_level="invalid",
                    has_conflict=None,
                    has_unanswered_claim=None,
                    updated_from=None,
                    updated_to=None,
                    sort_by="updated_at",
                    sort_order="desc",
                    scan_limit=500,
                    offset=0,
                    limit=50,
                    normalize_workflow_status=lambda value: value,
                    workflow_statuses={"queued", "review_required", "callback_reported"},
                    normalize_review_case_risk_level=lambda value: value,
                    review_case_risk_level_values={"low", "medium", "high"},
                    normalize_review_case_sla_bucket=lambda value: value,
                    review_case_sla_bucket_values={"normal", "warning", "urgent"},
                    normalize_evidence_claim_reliability_level=lambda value: str(value or "").strip().lower() or None,
                    evidence_claim_reliability_level_values={"high", "medium", "low", "unknown"},
                    normalize_query_datetime=lambda value: value,
                    normalize_evidence_claim_queue_sort_by=lambda value: str(value or "").strip().lower(),
                    normalize_evidence_claim_queue_sort_order=lambda value: str(value or "").strip().lower(),
                    evidence_claim_queue_sort_fields={"updated_at", "risk_score", "case_id"},
                    workflow_list_jobs=lambda **kwargs: asyncio.sleep(0, result=[]),
                    resolve_report_context_for_case=lambda **kwargs: asyncio.sleep(0, result={}),
                    trace_get=lambda case_id: None,
                    build_review_case_risk_profile=lambda **kwargs: {},
                    build_verdict_contract=lambda payload: {},
                    build_case_evidence_view=lambda **kwargs: {},
                    build_courtroom_read_model_view=lambda **kwargs: {},
                    build_courtroom_read_model_light_summary=lambda **kwargs: {},
                    build_evidence_claim_ops_profile=lambda **kwargs: {},
                    build_evidence_claim_action_hints=lambda **kwargs: [],
                    serialize_workflow_job=lambda workflow_job: {},
                    build_evidence_claim_queue_sort_key=lambda **kwargs: tuple(),
                )
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "invalid_evidence_claim_reliability_level")

    def test_build_case_evidence_claim_ops_queue_route_payload_should_build_items(self) -> None:
        created_at = datetime(2026, 4, 21, 0, 5, tzinfo=timezone.utc)
        job = type(
            "Job",
            (),
            {
                "job_id": 9912,
                "updated_at": created_at,
                "status": "review_required",
            },
        )()
        trace = _DummyTrace(trace_id="trace-9912", replays=[])
        trace.report_summary = {"callbackStatus": "reported", "callbackError": None}
        trace.callback_status = "reported"
        trace.callback_error = None

        payload = asyncio.run(
            build_case_evidence_claim_ops_queue_route_payload(
                status="review_required",
                dispatch_type="auto",
                winner="draw",
                review_required=True,
                risk_level="high",
                sla_bucket="urgent",
                reliability_level="low",
                has_conflict=True,
                has_unanswered_claim=True,
                updated_from=created_at,
                updated_to=created_at,
                sort_by="case_id",
                sort_order="desc",
                scan_limit=500,
                offset=0,
                limit=50,
                normalize_workflow_status=lambda value: str(value or "").strip().lower() or None,
                workflow_statuses={"queued", "review_required", "callback_reported"},
                normalize_review_case_risk_level=lambda value: str(value or "").strip().lower() or None,
                review_case_risk_level_values={"low", "medium", "high"},
                normalize_review_case_sla_bucket=lambda value: str(value or "").strip().lower() or None,
                review_case_sla_bucket_values={"normal", "warning", "urgent"},
                normalize_evidence_claim_reliability_level=lambda value: str(value or "").strip().lower() or None,
                evidence_claim_reliability_level_values={"high", "medium", "low", "unknown"},
                normalize_query_datetime=lambda value: value,
                normalize_evidence_claim_queue_sort_by=lambda value: str(value or "").strip().lower(),
                normalize_evidence_claim_queue_sort_order=lambda value: str(value or "").strip().lower(),
                evidence_claim_queue_sort_fields={"updated_at", "risk_score", "case_id"},
                workflow_list_jobs=lambda **kwargs: asyncio.sleep(0, result=[job]),
                resolve_report_context_for_case=lambda **kwargs: asyncio.sleep(
                    0,
                    result={
                        "dispatchType": "final",
                        "traceId": "trace-9912",
                        "reportPayload": {
                            "winner": "draw",
                            "reviewRequired": True,
                            "needsDrawVote": True,
                        },
                        "responsePayload": {"callbackStatus": "reported"},
                    },
                ),
                trace_get=lambda case_id: trace,
                build_review_case_risk_profile=lambda **kwargs: {
                    "level": "high",
                    "slaBucket": "urgent",
                    "score": 95,
                },
                build_verdict_contract=lambda payload: {"winner": payload.get("winner")},
                build_case_evidence_view=lambda **kwargs: {"hasCaseDossier": True},
                build_courtroom_read_model_view=lambda **kwargs: {"recorder": {"ok": True}},
                build_courtroom_read_model_light_summary=lambda **kwargs: {
                    "claim": {"conflictPairCount": 1, "unansweredClaimCount": 1, "stats": {}},
                    "evidence": {
                        "decisiveEvidenceCount": 1,
                        "sourceCitationCount": 2,
                        "conflictSourceCount": 1,
                        "stats": {
                            "reliabilityCounts": {"high": 0, "medium": 0, "low": 1, "unknown": 0},
                            "verdictReferencedReliabilityCounts": {
                                "high": 0,
                                "medium": 0,
                                "low": 1,
                                "unknown": 0,
                            },
                            "verdictReferencedCount": 1,
                        },
                    },
                },
                build_evidence_claim_ops_profile=lambda **kwargs: {
                    "priorityScore": 88,
                    "priorityLevel": "high",
                    "hasConflict": True,
                    "hasUnansweredClaim": True,
                    "conflictPairCount": 1,
                    "unansweredClaimCount": 1,
                    "decisiveEvidenceCount": 1,
                    "reliability": {"level": "low", "score": 10},
                },
                build_evidence_claim_action_hints=lambda **kwargs: [
                    "claim.resolve_conflict",
                    "review.queue.decide",
                ],
                serialize_workflow_job=lambda workflow_job: {
                    "caseId": workflow_job.job_id,
                    "status": workflow_job.status,
                },
                build_evidence_claim_queue_sort_key=lambda **kwargs: (
                    int(kwargs.get("item", {}).get("caseId", 0)),
                ),
            )
        )

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["returned"], 1)
        self.assertEqual(payload["errorCount"], 0)
        self.assertEqual(payload["aggregations"]["riskLevelCounts"]["high"], 1)
        self.assertEqual(payload["aggregations"]["reliabilityLevelCounts"]["low"], 1)
        self.assertEqual(payload["aggregations"]["conflictCaseCount"], 1)
        self.assertEqual(payload["filters"]["reliabilityLevel"], "low")
        item = payload["items"][0]
        self.assertEqual(item["caseId"], 9912)
        self.assertEqual(item["dispatchType"], "final")
        self.assertEqual(item["traceId"], "trace-9912")
        self.assertEqual(item["claimEvidenceProfile"]["reliability"]["level"], "low")
        self.assertIn("claim.resolve_conflict", item["actionHints"])

    def test_build_case_overview_replay_items_should_prefer_replay_records(self) -> None:
        records = [
            _DummyReplayRecord(
                dispatch_type="final",
                trace_id="trace-final-9501",
                created_at=datetime(2026, 4, 20, 0, 0, tzinfo=timezone.utc),
                winner="pro",
                needs_draw_vote=False,
                provider="mock",
            )
        ]
        payload = build_case_overview_replay_items(
            replay_records=records,
            trace=None,
        )
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["dispatchType"], "final")
        self.assertEqual(payload[0]["traceId"], "trace-final-9501")

    def test_build_case_overview_replay_items_should_fallback_to_trace_replays(self) -> None:
        trace = _DummyTrace(
            trace_id="trace-case-9502",
            replays=[
                _DummyTraceReplay(
                    replayed_at=datetime(2026, 4, 20, 0, 1, tzinfo=timezone.utc),
                    winner="draw",
                    needs_draw_vote=True,
                    provider="mock",
                )
            ],
        )
        payload = build_case_overview_replay_items(
            replay_records=[],
            trace=trace,
        )
        self.assertEqual(len(payload), 1)
        self.assertIsNone(payload[0]["dispatchType"])
        self.assertEqual(payload[0]["traceId"], "trace-case-9502")

    def test_build_case_overview_payload_should_keep_contract_shape(self) -> None:
        payload = build_case_overview_payload(
            case_id=9503,
            workflow={"status": "callback_reported"},
            trace=None,
            receipts={"phase": None, "final": {"dispatchType": "final"}},
            latest_dispatch_type="final",
            report_payload={"winner": "pro"},
            verdict_contract={"winner": "pro"},
            case_evidence={"hasCaseDossier": True},
            winner="pro",
            needs_draw_vote=False,
            review_required=False,
            callback_status="reported",
            callback_error=None,
            judge_core={"stage": "reported", "version": "v1", "eventSeq": 2},
            events=[],
            alerts=[],
            replays=[],
        )
        self.assertEqual(payload["caseId"], 9503)
        self.assertEqual(payload["latestDispatchType"], "final")
        self.assertIn("caseEvidence", payload)
        self.assertIn("replays", payload)

    def test_build_case_courtroom_read_model_payload_should_keep_contract_shape(self) -> None:
        payload = build_case_courtroom_read_model_payload(
            case_id=9504,
            dispatch_type="final",
            trace_id="trace-final-9504",
            workflow={"status": "callback_reported"},
            judge_core={"stage": "reported", "version": "v1", "eventSeq": 3},
            callback_status="reported",
            callback_error=None,
            report_payload={
                "winner": "pro",
                "reviewRequired": False,
                "needsDrawVote": False,
                "debateSummary": "summary",
                "sideAnalysis": {"pro": "p", "con": "c"},
                "verdictReason": "reason",
            },
            courtroom={"recorder": {}, "claim": {}, "evidence": {}},
            events=[{"eventSeq": 1}],
            event_count=5,
            alerts=[{"alertId": "a1"}],
            include_events=False,
            include_alerts=True,
            alert_limit=200,
        )
        self.assertEqual(payload["caseId"], 9504)
        self.assertEqual(payload["dispatchType"], "final")
        self.assertEqual(payload["eventCount"], 5)
        self.assertEqual(payload["events"], [])
        self.assertEqual(payload["filters"]["alertLimit"], 200)
        self.assertTrue(payload["filters"]["includeAlerts"])


if __name__ == "__main__":
    unittest.main()
