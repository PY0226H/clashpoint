from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.applications.replay_audit_ops import (
    build_replay_report_payload,
    build_replay_report_summary,
    serialize_alert_item,
    serialize_dispatch_receipt,
    serialize_outbox_event,
)


def test_serialize_alert_item_should_map_core_fields() -> None:
    now = datetime.now(timezone.utc)
    transition = SimpleNamespace(
        from_status="raised",
        to_status="acked",
        actor="ops-user",
        reason="checked",
        changed_at=now,
    )
    alert = SimpleNamespace(
        alert_id="alert-1",
        job_id=11,
        scope_id=22,
        trace_id="trace-11",
        alert_type="final_contract_violation",
        severity="critical",
        title="title",
        message="message",
        details={"missing": ["winner"]},
        status="acked",
        created_at=now,
        updated_at=now,
        acknowledged_at=now,
        resolved_at=None,
        transitions=[transition],
    )

    payload = serialize_alert_item(alert)

    assert payload["alertId"] == "alert-1"
    assert payload["caseId"] == 11
    assert payload["severity"] == "critical"
    assert payload["status"] == "acked"
    assert payload["transitions"][0]["toStatus"] == "acked"


def test_serialize_outbox_event_and_receipt_should_keep_shape() -> None:
    now = datetime.now(timezone.utc)
    outbox = SimpleNamespace(
        event_id="evt-1",
        channel="judge_alert",
        scope_id=5,
        job_id=8,
        trace_id="trace-8",
        alert_id="alert-8",
        status="raised",
        payload={"a": 1},
        delivery_status="pending",
        error_message=None,
        created_at=now,
        updated_at=now,
    )
    outbox_payload = serialize_outbox_event(outbox)
    assert outbox_payload["eventId"] == "evt-1"
    assert outbox_payload["deliveryStatus"] == "pending"

    receipt = SimpleNamespace(
        dispatch_type="phase",
        job_id=8,
        scope_id=5,
        session_id=99,
        trace_id="trace-8",
        idempotency_key="phase:8",
        rubric_version="v3",
        judge_policy_version="v3-default",
        topic_domain="tft",
        retrieval_profile="hybrid_v1",
        phase_no=1,
        phase_start_no=None,
        phase_end_no=None,
        message_start_id=1,
        message_end_id=2,
        message_count=2,
        status="reported",
        request={"k": "v"},
        response={"ok": True},
        created_at=now,
        updated_at=now,
    )
    receipt_payload = serialize_dispatch_receipt(receipt)
    assert receipt_payload["dispatchType"] == "phase"
    assert receipt_payload["status"] == "reported"
    assert receipt_payload["sessionId"] == 99


def test_build_replay_report_payload_and_summary_should_normalize_winner_and_count_alerts() -> None:
    now = datetime.now(timezone.utc)
    replay = SimpleNamespace(
        replayed_at=now,
        winner="draw",
        needs_draw_vote=True,
        provider="mock",
    )
    judge_workflow = {
        "judgeWorkflow": {
            "caseDossier": {
                "caseId": 701,
                "dispatchType": "final",
                "roleOrder": [
                    "clerk",
                    "recorder",
                    "claim_graph",
                    "evidence",
                    "panel",
                    "fairness_sentinel",
                    "chief_arbiter",
                    "opinion_writer",
                ],
            },
            "claimGraph": {
                "stats": {},
                "items": [],
                "unansweredClaimIds": [],
            },
            "evidenceBundle": {
                "entries": [],
                "sourceCitations": [],
                "conflictSources": [],
                "stats": {},
            },
            "panelBundle": {
                "topWinner": "draw",
                "disagreementRatio": 0.0,
                "judges": {},
            },
            "fairnessGate": {
                "decision": "blocked_to_draw",
                "reviewRequired": True,
                "reasons": [],
                "auditAlertIds": [],
            },
            "verdict": {
                "winner": "draw",
                "needsDrawVote": True,
                "reviewRequired": True,
                "decisionPath": [
                    "judge_panel",
                    "fairness_sentinel",
                    "chief_arbiter",
                ],
            },
            "opinion": {
                "debateSummary": "summary",
                "sideAnalysis": {},
                "verdictReason": "reason",
            },
        }
    }
    record = SimpleNamespace(
        job_id=701,
        trace_id="trace-701",
        status="reported",
        request={"caseId": 701},
        response={"provider": "mock", "errorCode": None},
        callback_status="reported",
        callback_error=None,
        report_summary={
            "dispatchType": "final",
            "payload": {"winner": "unknown", "needsDrawVote": True},
            "winner": "draw",
            "auditAlerts": [{"id": "a1"}],
            "callbackStatus": "reported",
            "callbackError": None,
            "judgeWorkflow": judge_workflow,
            "roleNodes": [
                {"seq": 1, "role": "clerk", "section": "caseDossier", "status": "completed"},
                {"seq": 2, "role": "recorder", "section": "claimGraph", "status": "completed"},
                {"seq": 3, "role": "claim_graph", "section": "claimGraph", "status": "completed"},
                {"seq": 4, "role": "evidence", "section": "evidenceBundle", "status": "completed"},
                {"seq": 5, "role": "panel", "section": "panelBundle", "status": "completed"},
                {
                    "seq": 6,
                    "role": "fairness_sentinel",
                    "section": "fairnessGate",
                    "status": "completed",
                },
                {"seq": 7, "role": "chief_arbiter", "section": "verdict", "status": "completed"},
                {"seq": 8, "role": "opinion_writer", "section": "opinion", "status": "completed"},
            ],
        },
        created_at=now,
        updated_at=now,
        replays=[replay],
    )

    payload = build_replay_report_payload(record)
    summary = build_replay_report_summary(record)

    assert payload["winner"] == "draw"
    assert payload["dispatchType"] == "final"
    assert payload["verdictContract"]["winner"] is None
    assert payload["replays"][0]["needsDrawVote"] is True
    assert summary["auditAlertCount"] == 1
    assert summary["replayCount"] == 1
    assert summary["callbackStatus"] == "reported"
