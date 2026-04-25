from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass
from datetime import datetime, timezone

from app.applications.judge_trace_replay_routes import (
    ReplayContextDependencyPack,
    ReplayFinalizeDependencyPack,
    ReplayReadRouteError,
    ReplayReportDependencyPack,
    build_replay_post_route_payload,
    build_replay_report_payload_for_dispatch,
    build_replay_report_route_payload,
    build_replay_reports_list_payload,
    build_replay_reports_route_payload,
    build_replay_route_payload,
    build_trace_route_payload,
    build_trace_route_read_payload,
    build_trace_route_replay_items,
    choose_replay_dispatch_receipt,
    extract_replay_request_snapshot,
    finalize_replay_route_payload,
    normalize_replay_dispatch_type,
    resolve_replay_dispatch_context_for_case,
    resolve_replay_trace_id,
)


@dataclass
class _ReplayRow:
    created_at: datetime
    winner: str
    needs_draw_vote: bool
    provider: str


@dataclass
class _TraceReplayRow:
    replayed_at: datetime
    winner: str
    needs_draw_vote: bool
    provider: str


@dataclass
class _TraceRow:
    job_id: int
    trace_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    callback_status: str | None
    callback_error: str | None
    request: dict
    response: dict
    replays: list[_TraceReplayRow]
    report_summary: dict | None = None


@dataclass
class _Receipt:
    trace_id: str
    request: dict


class JudgeTraceReplayRoutesTests(unittest.TestCase):
    def test_normalize_replay_dispatch_type_should_validate_values(self) -> None:
        self.assertEqual(normalize_replay_dispatch_type("auto"), "auto")
        self.assertEqual(normalize_replay_dispatch_type(" FINAL "), "final")
        with self.assertRaises(ValueError):
            normalize_replay_dispatch_type("invalid")

    def test_choose_replay_dispatch_receipt_should_prefer_final_on_auto(self) -> None:
        final_receipt = object()
        phase_receipt = object()
        dispatch_type, receipt = choose_replay_dispatch_receipt(
            dispatch_type="auto",
            final_receipt=final_receipt,
            phase_receipt=phase_receipt,
        )
        self.assertEqual(dispatch_type, "final")
        self.assertIs(receipt, final_receipt)

        dispatch_type, receipt = choose_replay_dispatch_receipt(
            dispatch_type="auto",
            final_receipt=None,
            phase_receipt=phase_receipt,
        )
        self.assertEqual(dispatch_type, "phase")
        self.assertIs(receipt, phase_receipt)

    def test_extract_and_resolve_trace_id_should_use_receipt_or_snapshot(self) -> None:
        receipt = _Receipt(trace_id="trace-1", request={"traceId": "trace-2"})
        snapshot = extract_replay_request_snapshot(receipt)
        self.assertEqual(snapshot["traceId"], "trace-2")
        trace_id = resolve_replay_trace_id(receipt=receipt, request_snapshot=snapshot)
        self.assertEqual(trace_id, "trace-1")

        trace_id_fallback = resolve_replay_trace_id(
            receipt=_Receipt(trace_id="", request={"traceId": "trace-3"}),
            request_snapshot={"traceId": "trace-3"},
        )
        self.assertEqual(trace_id_fallback, "trace-3")

    def test_build_trace_route_replay_items_should_support_fact_and_trace_fallback(self) -> None:
        now = datetime.now(timezone.utc)
        fact_items = build_trace_route_replay_items(
            replay_records=[
                _ReplayRow(
                    created_at=now,
                    winner="pro",
                    needs_draw_vote=False,
                    provider="mock",
                )
            ],
            trace_record=None,
        )
        self.assertEqual(len(fact_items), 1)
        self.assertEqual(fact_items[0]["winner"], "pro")
        self.assertIn("replayedAt", fact_items[0])

        trace_record = _TraceRow(
            job_id=1001,
            trace_id="trace-1001",
            status="reported",
            created_at=now,
            updated_at=now,
            callback_status="reported",
            callback_error=None,
            request={},
            response={},
            replays=[
                _TraceReplayRow(
                    replayed_at=now,
                    winner="con",
                    needs_draw_vote=False,
                    provider="mock",
                )
            ],
        )
        trace_items = build_trace_route_replay_items(
            replay_records=[],
            trace_record=trace_record,
        )
        self.assertEqual(len(trace_items), 1)
        self.assertEqual(trace_items[0]["winner"], "con")

    def test_build_trace_route_payload_should_keep_summary_and_role_nodes(self) -> None:
        now = datetime.now(timezone.utc)
        record = _TraceRow(
            job_id=1002,
            trace_id="trace-1002",
            status="reported",
            created_at=now,
            updated_at=now,
            callback_status="reported",
            callback_error=None,
            request={"k": "v"},
            response={"ok": True},
            replays=[],
        )
        payload = build_trace_route_payload(
            record=record,
            report_summary={
                "payload": {"winner": "pro"},
                "roleNodes": [{"role": "clerk"}],
            },
            verdict_contract={"winner": "pro"},
            replay_items=[{"winner": "pro"}],
            case_chain_summary={"ledgerChain": {"complete": True}},
        )
        self.assertEqual(payload["caseId"], 1002)
        self.assertEqual(payload["roleNodes"][0]["role"], "clerk")
        self.assertEqual(payload["verdictContract"]["winner"], "pro")
        self.assertTrue(payload["caseChainSummary"]["ledgerChain"]["complete"])
        self.assertEqual(payload["replays"][0]["winner"], "pro")

    def test_build_replay_route_payload_should_return_stable_contract(self) -> None:
        now = datetime.now(timezone.utc)
        payload = build_replay_route_payload(
            case_id=1003,
            dispatch_type="final",
            replayed_at=now,
            report_payload={"winner": "pro"},
            verdict_contract={"winner": "pro"},
            winner="pro",
            needs_draw_vote=False,
            trace_id="trace-1003",
            judge_core_stage="replay_computed",
            judge_core_version="v1",
        )
        self.assertEqual(payload["caseId"], 1003)
        self.assertEqual(payload["dispatchType"], "final")
        self.assertEqual(payload["winner"], "pro")
        self.assertEqual(payload["traceId"], "trace-1003")
        self.assertEqual(payload["judgeCoreStage"], "replay_computed")

    def test_build_replay_reports_list_payload_should_keep_filter_shape(self) -> None:
        now = datetime.now(timezone.utc)
        payload = build_replay_reports_list_payload(
            items=[{"caseId": 1}],
            status="reported",
            winner="pro",
            callback_status="reported",
            trace_id="trace-1",
            created_after=now,
            created_before=now,
            has_audit_alert=False,
            limit=20,
            include_report=True,
        )
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["caseId"], 1)
        self.assertEqual(payload["filters"]["winner"], "pro")
        self.assertTrue(payload["filters"]["createdAfter"].endswith("+00:00"))

    def test_build_replay_report_route_payload_should_include_claim_ledger(self) -> None:
        record = _TraceRow(
            job_id=1004,
            trace_id="trace-1004",
            status="reported",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            callback_status="reported",
            callback_error=None,
            request={},
            response={},
            replays=[],
        )

        async def _get_claim_ledger_record(*, case_id: int, dispatch_type: str | None):
            self.assertEqual(case_id, 1004)
            self.assertIsNone(dispatch_type)
            return {"caseId": 1004}

        payload = asyncio.run(
            build_replay_report_route_payload(
                case_id=1004,
                get_trace=lambda _case_id: record,
                build_replay_report_payload=lambda _record: {"caseId": 1004},
                get_claim_ledger_record=_get_claim_ledger_record,
                serialize_claim_ledger_record=lambda _row, include_payload: {
                    "caseId": 1004,
                    "includePayload": include_payload,
                },
            )
        )
        self.assertEqual(payload["caseId"], 1004)
        self.assertEqual(payload["claimLedger"]["caseId"], 1004)
        self.assertTrue(payload["claimLedger"]["includePayload"])

    def test_build_replay_report_route_payload_should_raise_not_found(self) -> None:
        async def _get_claim_ledger_record(*, case_id: int, dispatch_type: str | None):
            del case_id, dispatch_type
            return None

        with self.assertRaises(ReplayReadRouteError) as ctx:
            asyncio.run(
                build_replay_report_route_payload(
                    case_id=1005,
                    get_trace=lambda _case_id: None,
                    build_replay_report_payload=lambda _record: {},
                    get_claim_ledger_record=_get_claim_ledger_record,
                    serialize_claim_ledger_record=lambda _row, include_payload: {
                        "includePayload": include_payload
                    },
                )
            )
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "judge_trace_not_found")

    def test_build_replay_reports_route_payload_should_build_query_and_items(self) -> None:
        now = datetime.now(timezone.utc)

        @dataclass
        class _TraceQuery:
            status: str | None
            winner: str | None
            callback_status: str | None
            trace_id: str | None
            created_after: datetime | None
            created_before: datetime | None
            has_audit_alert: bool | None
            limit: int

        recorded_query: _TraceQuery | None = None

        def _list_traces(*, query: _TraceQuery) -> list[dict[str, int]]:
            nonlocal recorded_query
            recorded_query = query
            return [{"caseId": 1}]

        payload = build_replay_reports_route_payload(
            status="reported",
            winner="pro",
            callback_status="reported",
            trace_id="trace-1",
            created_after=now,
            created_before=now,
            has_audit_alert=False,
            limit=10,
            include_report=False,
            normalize_query_datetime=lambda value: value,
            trace_query_cls=_TraceQuery,
            list_traces=_list_traces,
            build_replay_report_payload=lambda record: {"full": record["caseId"]},
            build_replay_report_summary=lambda record: {"summary": record["caseId"]},
            build_replay_reports_list_payload=lambda **kwargs: kwargs,
        )
        self.assertIsNotNone(recorded_query)
        assert recorded_query is not None
        self.assertEqual(recorded_query.status, "reported")
        self.assertEqual(recorded_query.limit, 10)
        self.assertEqual(payload["items"], [{"summary": 1}])
        self.assertFalse(payload["include_report"])

    def test_build_trace_route_read_payload_should_build_trace_payload(self) -> None:
        now = datetime.now(timezone.utc)
        trace_record = _TraceRow(
            job_id=1010,
            trace_id="trace-1010",
            status="reported",
            created_at=now,
            updated_at=now,
            callback_status="reported",
            callback_error=None,
            request={},
            response={},
            replays=[],
        )

        async def _list_replay_records(*, job_id: int, limit: int) -> list[_ReplayRow]:
            self.assertEqual(job_id, 1010)
            self.assertEqual(limit, 50)
            return []

        async def _build_case_chain_summary(*, job_id: int) -> dict:
            self.assertEqual(job_id, 1010)
            return {"caseId": job_id, "ledgerChain": {"complete": False}}

        payload = asyncio.run(
            build_trace_route_read_payload(
                case_id=1010,
                get_trace=lambda _case_id: trace_record,
                list_replay_records=_list_replay_records,
                build_trace_route_replay_items=lambda **kwargs: kwargs["replay_records"],
                build_verdict_contract=lambda report_payload: {"winner": report_payload.get("winner")},
                build_trace_route_payload=lambda **kwargs: {
                    "traceId": kwargs["record"].trace_id,
                    "verdictContract": kwargs["verdict_contract"],
                    "caseChainSummary": kwargs["case_chain_summary"],
                },
                build_case_chain_summary=_build_case_chain_summary,
            )
        )
        self.assertEqual(payload["traceId"], "trace-1010")
        self.assertEqual(payload["verdictContract"], {"winner": None})
        self.assertFalse(payload["caseChainSummary"]["ledgerChain"]["complete"])

    def test_build_trace_route_read_payload_should_raise_not_found(self) -> None:
        async def _list_replay_records(*, job_id: int, limit: int) -> list[_ReplayRow]:
            del job_id, limit
            return []

        with self.assertRaises(ReplayReadRouteError) as ctx:
            asyncio.run(
                build_trace_route_read_payload(
                    case_id=1011,
                    get_trace=lambda _case_id: None,
                    list_replay_records=_list_replay_records,
                    build_trace_route_replay_items=lambda **kwargs: kwargs["replay_records"],
                    build_verdict_contract=lambda report_payload: {"winner": report_payload.get("winner")},
                    build_trace_route_payload=lambda **kwargs: kwargs,
                )
            )
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "judge_trace_not_found")

    def test_resolve_replay_dispatch_context_for_case_should_choose_final_on_auto(self) -> None:
        final_receipt = _Receipt(trace_id="trace-final-1", request={"traceId": "req-trace-final"})
        phase_receipt = _Receipt(trace_id="trace-phase-1", request={"traceId": "req-trace-phase"})

        async def _get_dispatch_receipt(*, dispatch_type: str, job_id: int):
            self.assertEqual(job_id, 1201)
            if dispatch_type == "final":
                return final_receipt
            if dispatch_type == "phase":
                return phase_receipt
            return None

        payload = asyncio.run(
            resolve_replay_dispatch_context_for_case(
                case_id=1201,
                dispatch_type="auto",
                normalize_replay_dispatch_type=normalize_replay_dispatch_type,
                get_dispatch_receipt=_get_dispatch_receipt,
                choose_replay_dispatch_receipt=choose_replay_dispatch_receipt,
                extract_replay_request_snapshot=extract_replay_request_snapshot,
                resolve_replay_trace_id=resolve_replay_trace_id,
            )
        )

        self.assertEqual(payload["dispatchType"], "final")
        self.assertIs(payload["receipt"], final_receipt)
        self.assertEqual(payload["requestSnapshot"]["traceId"], "req-trace-final")
        self.assertEqual(payload["traceId"], "trace-final-1")

    def test_resolve_replay_dispatch_context_for_case_should_raise_for_invalid_dispatch_type(self) -> None:
        async def _get_dispatch_receipt(*, dispatch_type: str, job_id: int):
            del dispatch_type, job_id
            return None

        with self.assertRaises(ReplayReadRouteError) as ctx:
            asyncio.run(
                resolve_replay_dispatch_context_for_case(
                    case_id=1202,
                    dispatch_type="bad",
                    normalize_replay_dispatch_type=normalize_replay_dispatch_type,
                    get_dispatch_receipt=_get_dispatch_receipt,
                    choose_replay_dispatch_receipt=choose_replay_dispatch_receipt,
                    extract_replay_request_snapshot=extract_replay_request_snapshot,
                    resolve_replay_trace_id=resolve_replay_trace_id,
                )
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "invalid_dispatch_type")

    def test_finalize_replay_route_payload_should_persist_and_build_response(self) -> None:
        now = datetime.now(timezone.utc)
        callbox: dict[str, object] = {
            "register_start": None,
            "mark_replay": None,
            "workflow_replay": None,
            "upsert_claim_ledger": None,
            "append_replay_record": None,
        }

        async def _append_replay_record(**kwargs):
            callbox["append_replay_record"] = dict(kwargs)
            return _ReplayRow(
                created_at=now,
                winner=str(kwargs["winner"]),
                needs_draw_vote=bool(kwargs["needs_draw_vote"]),
                provider=str(kwargs["provider"]),
            )

        async def _workflow_mark_replay(**kwargs):
            callbox["workflow_replay"] = dict(kwargs)

        async def _upsert_claim_ledger_record(**kwargs):
            callbox["upsert_claim_ledger"] = dict(kwargs)

        payload = asyncio.run(
            finalize_replay_route_payload(
                case_id=1301,
                dispatch_type="final",
                trace_id="trace-1301",
                request_snapshot={"traceId": "trace-1301"},
                report_payload={
                    "agent3WeightedScore": {"pro": 61.2, "con": 38.8},
                },
                dependencies=ReplayFinalizeDependencyPack(
                    provider="mock",
                    get_trace=lambda _case_id: None,
                    trace_register_start=lambda **kwargs: callbox.__setitem__(
                        "register_start", dict(kwargs)
                    ),
                    trace_mark_replay=lambda **kwargs: callbox.__setitem__(
                        "mark_replay", dict(kwargs)
                    ),
                    append_replay_record=_append_replay_record,
                    workflow_mark_replay=_workflow_mark_replay,
                    upsert_claim_ledger_record=_upsert_claim_ledger_record,
                    build_verdict_contract=lambda report_payload: {
                        "winner": report_payload.get("winner")
                    },
                    build_replay_route_payload=lambda **kwargs: kwargs,
                    safe_float=lambda value, default=0.0: float(
                        default if value is None else value
                    ),
                    resolve_winner=lambda pro, con, margin: "pro"
                    if pro - con >= margin
                    else "draw",
                    draw_margin=0.8,
                    judge_core_stage="replay_computed",
                    judge_core_version="v1",
                ),
            )
        )

        self.assertEqual(payload["winner"], "pro")
        self.assertFalse(payload["needs_draw_vote"])
        self.assertEqual(payload["dispatch_type"], "final")
        self.assertEqual(payload["trace_id"], "trace-1301")
        self.assertEqual(payload["judge_core_stage"], "replay_computed")
        self.assertEqual(payload["judge_core_version"], "v1")

        self.assertIsNotNone(callbox["upsert_claim_ledger"])
        self.assertIsNotNone(callbox["append_replay_record"])
        self.assertIsNotNone(callbox["workflow_replay"])
        self.assertIsNotNone(callbox["register_start"])
        self.assertIsNotNone(callbox["mark_replay"])

    def test_build_replay_report_payload_for_dispatch_should_build_final_payload(self) -> None:
        final_request = type(
            "FinalReq",
            (),
            {
                "judge_policy_version": "v3-default",
                "rubric_version": "v3",
                "topic_domain": "tft",
                "session_id": 99,
                "case_id": 1302,
                "scope_id": 1,
                "trace_id": "trace-1302",
                "phase_start_no": 1,
                "phase_end_no": 2,
            },
        )()
        policy_profile = type(
            "PolicyProfile",
            (),
            {
                "prompt_registry_version": "prompt-v1",
                "tool_registry_version": "tool-v1",
                "fairness_thresholds": {"low_margin": 3},
            },
        )()
        callbox: dict[str, object] = {"ensure_ready": False}

        async def _ensure_registry_runtime_ready() -> None:
            callbox["ensure_ready"] = True

        async def _list_dispatch_receipts(**kwargs):
            self.assertEqual(kwargs["dispatch_type"], "phase")
            self.assertEqual(kwargs["session_id"], 99)
            return [{"jobId": 1}]

        async def _attach_judge_agent_runtime_trace(**kwargs):
            callbox["trace"] = dict(kwargs)

        payload = asyncio.run(
            build_replay_report_payload_for_dispatch(
                dispatch_type="final",
                request_snapshot={"traceId": "trace-1302"},
                dependencies=ReplayReportDependencyPack(
                    ensure_registry_runtime_ready=_ensure_registry_runtime_ready,
                    final_request_model_validate=lambda _snapshot: final_request,
                    phase_request_model_validate=lambda _snapshot: None,
                    validate_final_dispatch_request=lambda _req: None,
                    validate_phase_dispatch_request=lambda _req: None,
                    resolve_policy_profile=lambda **kwargs: policy_profile,
                    resolve_prompt_profile=lambda **kwargs: {
                        "version": kwargs["prompt_registry_version"]
                    },
                    resolve_tool_profile=lambda **kwargs: {
                        "version": kwargs["tool_registry_version"]
                    },
                    list_dispatch_receipts=_list_dispatch_receipts,
                    build_final_report_payload=lambda **kwargs: {"winner": "pro"},
                    resolve_panel_runtime_profiles=lambda **kwargs: {"judgeC": "panel-v1"},
                    build_phase_report_payload=lambda **kwargs: {"winner": "draw"},
                    attach_judge_agent_runtime_trace=_attach_judge_agent_runtime_trace,
                    attach_policy_trace_snapshot=lambda **kwargs: kwargs["report_payload"].update(
                        {"policyTrace": True}
                    ),
                    attach_report_attestation=lambda **kwargs: kwargs["report_payload"].update(
                        {"attested": kwargs["dispatch_type"]}
                    ),
                    validate_final_report_payload_contract=lambda _payload: [],
                    settings={"k": "v"},
                    gateway_runtime={"g": "r"},
                ),
            )
        )

        self.assertTrue(callbox["ensure_ready"])
        self.assertEqual(payload["winner"], "pro")
        self.assertTrue(payload["policyTrace"])
        self.assertEqual(payload["attested"], "final")
        self.assertEqual(callbox["trace"]["dispatch_type"], "final")

    def test_build_replay_report_payload_for_dispatch_should_raise_on_invalid_phase_request(self) -> None:
        async def _ensure_registry_runtime_ready() -> None:
            return None

        with self.assertRaises(ReplayReadRouteError) as ctx:
            asyncio.run(
                build_replay_report_payload_for_dispatch(
                    dispatch_type="phase",
                    request_snapshot={"bad": "snapshot"},
                    dependencies=ReplayReportDependencyPack(
                        ensure_registry_runtime_ready=_ensure_registry_runtime_ready,
                        final_request_model_validate=lambda _snapshot: None,
                        phase_request_model_validate=lambda _snapshot: (_ for _ in ()).throw(
                            ValueError("phase_model_error")
                        ),
                        validate_final_dispatch_request=lambda _req: None,
                        validate_phase_dispatch_request=lambda _req: None,
                        resolve_policy_profile=lambda **kwargs: {},
                        resolve_prompt_profile=lambda **kwargs: {},
                        resolve_tool_profile=lambda **kwargs: {},
                        list_dispatch_receipts=lambda **kwargs: [],
                        build_final_report_payload=lambda **kwargs: {},
                        resolve_panel_runtime_profiles=lambda **kwargs: {},
                        build_phase_report_payload=lambda **kwargs: {},
                        attach_judge_agent_runtime_trace=lambda **kwargs: None,
                        attach_policy_trace_snapshot=lambda **kwargs: None,
                        attach_report_attestation=lambda **kwargs: None,
                        validate_final_report_payload_contract=lambda _payload: [],
                        settings={},
                        gateway_runtime={},
                    ),
                )
            )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("replay_invalid_phase_request", str(ctx.exception.detail))

    def test_build_replay_post_route_payload_should_orchestrate_context_report_and_finalize(
        self,
    ) -> None:
        now = datetime.now(timezone.utc)
        phase_receipt = _Receipt(trace_id="trace-1701", request={"traceId": "trace-1701"})
        callbox: dict[str, object] = {
            "report_called": None,
            "finalize_called": None,
        }

        async def _get_dispatch_receipt(*, dispatch_type: str, job_id: int):
            self.assertEqual(job_id, 1701)
            if dispatch_type == "phase":
                return phase_receipt
            return None

        phase_request = type(
            "PhaseReq",
            (),
            {
                "judge_policy_version": "v3-default",
                "rubric_version": "v3",
                "topic_domain": "tft",
                "case_id": 1701,
                "scope_id": 1,
                "session_id": 88,
                "trace_id": "trace-1701",
                "phase_no": 2,
            },
        )()

        async def _build_phase_report_payload(**kwargs):
            callbox["report_called"] = dict(kwargs)
            return {
                "agent3WeightedScore": {"pro": 61.2, "con": 38.8},
            }

        async def _append_replay_record(**kwargs):
            callbox["finalize_called"] = dict(kwargs)
            return _ReplayRow(
                created_at=now,
                winner=str(kwargs["winner"]),
                needs_draw_vote=bool(kwargs["needs_draw_vote"]),
                provider=str(kwargs["provider"]),
            )

        payload = asyncio.run(
            build_replay_post_route_payload(
                case_id=1701,
                dispatch_type="phase",
                context_dependencies=ReplayContextDependencyPack(
                    normalize_replay_dispatch_type=normalize_replay_dispatch_type,
                    get_dispatch_receipt=_get_dispatch_receipt,
                    choose_replay_dispatch_receipt=choose_replay_dispatch_receipt,
                    extract_replay_request_snapshot=extract_replay_request_snapshot,
                    resolve_replay_trace_id=resolve_replay_trace_id,
                ),
                report_dependencies=ReplayReportDependencyPack(
                    ensure_registry_runtime_ready=lambda: asyncio.sleep(0),
                    final_request_model_validate=lambda _snapshot: None,
                    phase_request_model_validate=lambda _snapshot: phase_request,
                    validate_final_dispatch_request=lambda _req: None,
                    validate_phase_dispatch_request=lambda _req: None,
                    resolve_policy_profile=lambda **kwargs: type(
                        "PolicyProfile",
                        (),
                        {
                            "prompt_registry_version": "prompt-v1",
                            "tool_registry_version": "tool-v1",
                            "fairness_thresholds": {"low_margin": 3.0},
                        },
                    )(),
                    resolve_prompt_profile=lambda **kwargs: {},
                    resolve_tool_profile=lambda **kwargs: {},
                    list_dispatch_receipts=lambda **kwargs: [],
                    build_final_report_payload=lambda **kwargs: {},
                    resolve_panel_runtime_profiles=lambda **kwargs: {},
                    build_phase_report_payload=_build_phase_report_payload,
                    attach_judge_agent_runtime_trace=lambda **kwargs: asyncio.sleep(0),
                    attach_policy_trace_snapshot=lambda **kwargs: None,
                    attach_report_attestation=lambda **kwargs: None,
                    validate_final_report_payload_contract=lambda _payload: [],
                    settings={},
                    gateway_runtime={},
                ),
                finalize_dependencies=ReplayFinalizeDependencyPack(
                    provider="mock",
                    get_trace=lambda _case_id: None,
                    trace_register_start=lambda **kwargs: None,
                    trace_mark_replay=lambda **kwargs: None,
                    append_replay_record=_append_replay_record,
                    workflow_mark_replay=lambda **kwargs: asyncio.sleep(0),
                    upsert_claim_ledger_record=lambda **kwargs: asyncio.sleep(0),
                    build_verdict_contract=lambda report_payload: {
                        "winner": report_payload.get("winner")
                    },
                    build_replay_route_payload=lambda **kwargs: kwargs,
                    safe_float=lambda value, default=0.0: float(
                        default if value is None else value
                    ),
                    resolve_winner=lambda pro, con, margin: "pro"
                    if pro - con >= margin
                    else "draw",
                    draw_margin=0.8,
                    judge_core_stage="replay_computed",
                    judge_core_version="v1",
                ),
            )
        )

        self.assertEqual(payload["dispatch_type"], "phase")
        self.assertEqual(payload["trace_id"], "trace-1701")
        self.assertEqual(payload["winner"], "pro")
        self.assertIsNotNone(callbox["report_called"])
        self.assertIsNotNone(callbox["finalize_called"])

    def test_build_replay_post_route_payload_should_raise_on_invalid_dispatch_type(self) -> None:
        async def _get_dispatch_receipt(*, dispatch_type: str, job_id: int):
            del dispatch_type, job_id
            return None

        with self.assertRaises(ReplayReadRouteError) as ctx:
            asyncio.run(
                build_replay_post_route_payload(
                    case_id=1702,
                    dispatch_type="bad",
                    context_dependencies=ReplayContextDependencyPack(
                        normalize_replay_dispatch_type=normalize_replay_dispatch_type,
                        get_dispatch_receipt=_get_dispatch_receipt,
                        choose_replay_dispatch_receipt=choose_replay_dispatch_receipt,
                        extract_replay_request_snapshot=extract_replay_request_snapshot,
                        resolve_replay_trace_id=resolve_replay_trace_id,
                    ),
                    report_dependencies=ReplayReportDependencyPack(
                        ensure_registry_runtime_ready=lambda: asyncio.sleep(0),
                        final_request_model_validate=lambda _snapshot: None,
                        phase_request_model_validate=lambda _snapshot: None,
                        validate_final_dispatch_request=lambda _req: None,
                        validate_phase_dispatch_request=lambda _req: None,
                        resolve_policy_profile=lambda **kwargs: {},
                        resolve_prompt_profile=lambda **kwargs: {},
                        resolve_tool_profile=lambda **kwargs: {},
                        list_dispatch_receipts=lambda **kwargs: [],
                        build_final_report_payload=lambda **kwargs: {},
                        resolve_panel_runtime_profiles=lambda **kwargs: {},
                        build_phase_report_payload=lambda **kwargs: {},
                        attach_judge_agent_runtime_trace=lambda **kwargs: asyncio.sleep(0),
                        attach_policy_trace_snapshot=lambda **kwargs: None,
                        attach_report_attestation=lambda **kwargs: None,
                        validate_final_report_payload_contract=lambda _payload: [],
                        settings={},
                        gateway_runtime={},
                    ),
                    finalize_dependencies=ReplayFinalizeDependencyPack(
                        provider="mock",
                        get_trace=lambda _case_id: None,
                        trace_register_start=lambda **kwargs: None,
                        trace_mark_replay=lambda **kwargs: None,
                        append_replay_record=lambda **kwargs: asyncio.sleep(0),
                        workflow_mark_replay=lambda **kwargs: asyncio.sleep(0),
                        upsert_claim_ledger_record=lambda **kwargs: asyncio.sleep(0),
                        build_verdict_contract=lambda report_payload: report_payload,
                        build_replay_route_payload=lambda **kwargs: kwargs,
                        safe_float=lambda value, default=0.0: float(
                            default if value is None else value
                        ),
                        resolve_winner=lambda pro, con, margin: "draw",
                        draw_margin=0.8,
                        judge_core_stage="replay_computed",
                        judge_core_version="v1",
                    ),
                )
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "invalid_dispatch_type")


if __name__ == "__main__":
    unittest.main()
