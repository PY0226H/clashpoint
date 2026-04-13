from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.applications import build_final_report_payload, validate_final_report_payload_contract
from app.models import FinalDispatchRequest


@dataclass
class _ReceiptRow:
    phase_no: int
    response: dict
    updated_at: datetime


def _build_phase_payload(*, pro: float, con: float, msg_offset: int) -> dict:
    return {
        "messageStartId": msg_offset + 1,
        "messageEndId": msg_offset + 2,
        "messageCount": 2,
        "agent3WeightedScore": {"pro": pro, "con": con},
        "agent2Score": {
            "pro": pro - 3,
            "con": con - 3,
            "hitItems": [f"pro:claim-{msg_offset}"],
            "missItems": [f"con:claim-{msg_offset}"],
        },
        "agent1Score": {
            "dimensions": {
                "pro": {"logic": pro, "evidence": pro - 1, "rebuttal": pro - 2, "expression": pro - 3},
                "con": {"logic": con, "evidence": con - 1, "rebuttal": con - 2, "expression": con - 3},
            },
            "evidenceRefs": {
                "pro": {"messageIds": [msg_offset + 1], "chunkIds": [f"chunk-pro-{msg_offset}"]},
                "con": {"messageIds": [msg_offset + 2], "chunkIds": [f"chunk-con-{msg_offset}"]},
            },
        },
        "proRetrievalBundle": {
            "items": [
                {
                    "chunkId": f"chunk-pro-{msg_offset}",
                    "title": "pro title",
                    "sourceUrl": "https://example.com/pro",
                    "score": 0.81,
                    "snippet": "pro snippet",
                }
            ]
        },
        "conRetrievalBundle": {
            "items": [
                {
                    "chunkId": f"chunk-con-{msg_offset}",
                    "title": "con title",
                    "sourceUrl": "https://example.com/con",
                    "score": 0.73,
                    "snippet": "con snippet",
                }
            ]
        },
        "errorCodes": [],
        "degradationLevel": 0,
    }


def test_build_final_report_payload_should_satisfy_contract() -> None:
    request = FinalDispatchRequest(
        job_id=9001,
        scope_id=1,
        session_id=301,
        phase_start_no=1,
        phase_end_no=2,
        rubric_version="v3",
        judge_policy_version="v3-default",
        topic_domain="tft",
        trace_id="trace-final-9001",
        idempotency_key="final:9001",
    )
    now = datetime.now(timezone.utc)
    phase_receipts = [
        _ReceiptRow(phase_no=1, response={"reportPayload": _build_phase_payload(pro=69, con=55, msg_offset=0)}, updated_at=now),
        _ReceiptRow(phase_no=2, response={"reportPayload": _build_phase_payload(pro=72, con=59, msg_offset=2)}, updated_at=now),
    ]

    payload = build_final_report_payload(
        request=request,
        phase_receipts=phase_receipts,
        judge_style_mode="mixed",
    )

    assert payload["winner"] == "pro"
    assert payload["degradationLevel"] == 0
    assert isinstance(payload["debateSummary"], str) and payload["debateSummary"]
    assert isinstance(payload["sideAnalysis"], dict)
    assert isinstance(payload["judgeTrace"], dict)
    assert validate_final_report_payload_contract(payload) == []


def test_build_final_report_payload_should_mark_incomplete_rollup() -> None:
    request = FinalDispatchRequest(
        job_id=9002,
        scope_id=1,
        session_id=302,
        phase_start_no=1,
        phase_end_no=2,
        rubric_version="v3",
        judge_policy_version="v3-default",
        topic_domain="tft",
        trace_id="trace-final-9002",
        idempotency_key="final:9002",
    )
    now = datetime.now(timezone.utc)
    payload = build_final_report_payload(
        request=request,
        phase_receipts=[
            _ReceiptRow(
                phase_no=1,
                response={"reportPayload": _build_phase_payload(pro=60, con=58, msg_offset=0)},
                updated_at=now,
            )
        ],
        judge_style_mode="rational",
    )

    assert "final_rollup_incomplete" in payload["errorCodes"]
    assert payload["degradationLevel"] == 1
    assert len(payload["auditAlerts"]) == 1
    assert payload["auditAlerts"][0]["type"] == "final_rollup_incomplete"


def test_validate_final_report_payload_contract_should_report_missing_items() -> None:
    missing = validate_final_report_payload_contract({"winner": "draw"})
    assert "debateSummary" in missing
    assert "sideAnalysis" in missing
    assert "verdictReason" in missing
    assert "judgeTrace" in missing
