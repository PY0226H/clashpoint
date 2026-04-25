from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.domain.judge.claim_graph import build_claim_graph_payload
from app.domain.judge.evidence_ledger import EvidenceLedgerBuilder

from ..models import FinalDispatchRequest, PhaseDispatchRequest
from .judge_app_domain import (
    build_judge_role_domain_state,
    validate_judge_app_domain_payload,
)

_TEXT_REDACTION_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("nickname_signal", re.compile(r"(昵称|绰号|nickname|display\s*name)", re.IGNORECASE)),
    ("user_identity_signal", re.compile(r"(用户\s*id|user\s*id|uid|账号|account)", re.IGNORECASE)),
    ("payment_signal", re.compile(r"(充值|消费|余额|钱包|vip|付费|payment|wallet)", re.IGNORECASE)),
    ("reputation_signal", re.compile(r"(历史胜率|胜率|段位|rank|win\s*rate|elo)", re.IGNORECASE)),
)
_SENSITIVE_DOSSIER_KEYS = {
    "avatar",
    "balance",
    "displayname",
    "display_name",
    "nickname",
    "payment",
    "reputation",
    "uid",
    "userid",
    "user_id",
    "userprofile",
    "user_profile",
    "vip",
    "wallet",
    "winrate",
    "win_rate",
}


def _safe_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_str(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _datetime_to_payload(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return _safe_str(value)


def _payload_from_message(message: Any) -> dict[str, Any]:
    if isinstance(message, dict):
        return dict(message)
    model_dump = getattr(message, "model_dump", None)
    if callable(model_dump):
        return dict(model_dump(mode="json"))
    return {
        "message_id": getattr(message, "message_id", None),
        "side": getattr(message, "side", None),
        "content": getattr(message, "content", None),
        "created_at": getattr(message, "created_at", None),
        "speaker_tag": getattr(message, "speaker_tag", None),
    }


def _message_id_from_payload(payload: dict[str, Any]) -> int | None:
    return _safe_int(payload.get("message_id") or payload.get("messageId"))


def _content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _redact_text(value: str) -> tuple[str, list[str]]:
    redacted = value
    reasons: list[str] = []
    for reason, pattern in _TEXT_REDACTION_RULES:
        if pattern.search(redacted):
            reasons.append(reason)
            redacted = pattern.sub("[REDACTED_IDENTITY_SIGNAL]", redacted)
    return redacted, reasons


def _iter_sensitive_key_hits(value: Any, *, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key or "")
            normalized = key_text.replace("-", "_").replace(" ", "_").lower()
            child_path = f"{path}.{key_text}"
            if normalized in _SENSITIVE_DOSSIER_KEYS:
                hits.append(child_path)
            hits.extend(_iter_sensitive_key_hits(child, path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_iter_sensitive_key_hits(child, path=f"{path}[{index}]"))
    return hits


def _expected_message_ids(
    *,
    start_id: int | None,
    end_id: int | None,
    expected_count: int | None,
) -> list[int]:
    if start_id is None or end_id is None or end_id < start_id:
        return []
    expected = list(range(start_id, end_id + 1))
    if expected_count is None or expected_count <= 0:
        return expected
    if len(expected) == expected_count:
        return expected
    return expected


def _coverage_guard(
    *,
    expected_ids: list[int],
    observed_ids: list[int],
    invalid_reply_links: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    expected_set = set(expected_ids)
    observed_set = set(observed_ids)
    missing_ids = [item for item in expected_ids if item not in observed_set]
    extra_ids = [item for item in observed_ids if expected_set and item not in expected_set]
    denominator = len(expected_ids) if expected_ids else len(observed_ids)
    if denominator <= 0:
        coverage_ratio = 1.0
    elif expected_ids:
        coverage_ratio = (len(expected_set & observed_set)) / float(denominator)
    else:
        coverage_ratio = 1.0
    invalid_links = list(invalid_reply_links or [])
    complete = not missing_ids and not extra_ids and not invalid_links
    return {
        "guard": "case_dossier_completeness_v1",
        "complete": complete,
        "status": "complete" if complete else "partial",
        "coverageRatio": round(max(0.0, min(1.0, coverage_ratio)), 4),
        "expectedMessageIds": expected_ids,
        "observedMessageIds": observed_ids,
        "missingMessageIds": missing_ids,
        "extraMessageIds": extra_ids,
        "invalidReplyLinks": invalid_links,
    }


@dataclass(frozen=True)
class ClerkRole:
    """生成可审计的收案与净化结果，只暴露脱敏后的裁判材料。"""

    def build_input_validation(
        self,
        *,
        request: PhaseDispatchRequest | FinalDispatchRequest,
        dispatch_type: str,
        report_payload: dict[str, Any] | None = None,
        expected_ids: list[int] | None = None,
        observed_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        request_payload = (
            request.model_dump(mode="json")
            if hasattr(request, "model_dump")
            else dict(getattr(request, "__dict__", {}))
        )
        sensitive_hits = _iter_sensitive_key_hits(request_payload)
        if isinstance(report_payload, dict):
            sensitive_hits.extend(_iter_sensitive_key_hits(report_payload))
        phase_valid = True
        if dispatch_type == "final":
            phase_valid = int(request.phase_start_no) <= int(request.phase_end_no)
        message_window_valid = True
        if dispatch_type == "phase":
            message_window_valid = (
                int(request.message_start_id) <= int(request.message_end_id)
                and int(request.message_count) == len(getattr(request, "messages", []) or [])
            )
        audit_reasons: list[str] = []
        if sensitive_hits:
            audit_reasons.append("sensitive_key_removed")
        if not phase_valid:
            audit_reasons.append("phase_range_invalid")
        if not message_window_valid:
            audit_reasons.append("message_window_incomplete")
        if expected_ids is not None and observed_ids is not None:
            missing = [item for item in expected_ids if item not in set(observed_ids)]
            if missing:
                audit_reasons.append("message_ids_missing")
        return {
            "status": "accepted" if phase_valid and message_window_valid else "blocked",
            "blocked": not (phase_valid and message_window_valid),
            "dispatchType": dispatch_type,
            "phaseRangeValid": phase_valid,
            "messageWindowValid": message_window_valid,
            "messageCountExpected": getattr(request, "message_count", None),
            "messageCountObserved": len(getattr(request, "messages", []) or []),
            "sensitiveFieldHits": sorted(set(sensitive_hits)),
            "auditReasons": audit_reasons,
        }

    def build_redaction_summary(
        self,
        *,
        message_rows: list[dict[str, Any]],
        sensitive_field_hits: list[str],
    ) -> dict[str, Any]:
        semantic_hits: list[dict[str, Any]] = []
        for row in message_rows:
            message_id = _message_id_from_payload(row)
            content = str(row.get("content") or "")
            _redacted, reasons = _redact_text(content)
            for reason in reasons:
                semantic_hits.append({"messageId": message_id, "reason": reason})
        redacted_message_ids = sorted(
            {
                int(item["messageId"])
                for item in semantic_hits
                if _safe_int(item.get("messageId")) is not None
            }
        )
        return {
            "status": "redacted" if sensitive_field_hits or semantic_hits else "clean",
            "identityFieldsRemoved": len(set(sensitive_field_hits)),
            "semanticRedactionCount": len(semantic_hits),
            "redactedMessageIds": redacted_message_ids,
            "semanticSignals": semantic_hits,
            "auditReasons": sorted(
                {
                    str(item.get("reason"))
                    for item in semantic_hits
                    if str(item.get("reason") or "").strip()
                }
            ),
        }


@dataclass(frozen=True)
class RecorderRole:
    def build_phase_transcript_snapshot(
        self,
        *,
        request: PhaseDispatchRequest,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        rows = [_payload_from_message(message) for message in request.messages]
        rows.sort(
            key=lambda row: (
                _datetime_to_payload(row.get("created_at") or row.get("createdAt")) or "",
                _message_id_from_payload(row) or 0,
            )
        )
        expected_ids = _expected_message_ids(
            start_id=int(request.message_start_id),
            end_id=int(request.message_end_id),
            expected_count=int(request.message_count),
        )
        message_digest: list[dict[str, Any]] = []
        turn_index: list[dict[str, Any]] = []
        reply_links: list[dict[str, Any]] = []
        last_by_side: dict[str, int] = {}
        for sequence, row in enumerate(rows, start=1):
            message_id = _message_id_from_payload(row)
            side = str(row.get("side") or "").strip().lower()
            content = str(row.get("content") or "")
            redacted_content, redaction_reasons = _redact_text(content)
            created_at = _datetime_to_payload(row.get("created_at") or row.get("createdAt"))
            speaker_tag = _safe_str(row.get("speaker_tag") or row.get("speakerTag"))
            message_digest.append(
                {
                    "messageId": message_id,
                    "side": side or None,
                    "speakerTag": speaker_tag,
                    "createdAt": created_at,
                    "contentHash": _content_hash(content),
                    "contentPreview": redacted_content[:160],
                    "redactionReasons": redaction_reasons,
                }
            )
            turn_index.append(
                {
                    "sequence": sequence,
                    "turnNo": sequence,
                    "phaseNo": int(request.phase_no),
                    "messageId": message_id,
                    "side": side or None,
                    "createdAt": created_at,
                }
            )
            if message_id is not None and side in {"pro", "con"}:
                opposite = "con" if side == "pro" else "pro"
                target_id = last_by_side.get(opposite)
                if target_id is not None:
                    reply_links.append(
                        {
                            "fromMessageId": message_id,
                            "toMessageId": target_id,
                            "linkType": "reply_to_previous_opponent",
                        }
                    )
                last_by_side[side] = message_id
        observed_ids = [
            int(item["messageId"])
            for item in message_digest
            if _safe_int(item.get("messageId")) is not None
        ]
        invalid_reply_links = [
            dict(item)
            for item in reply_links
            if item.get("fromMessageId") not in observed_ids
            or item.get("toMessageId") not in observed_ids
        ]
        completeness = _coverage_guard(
            expected_ids=expected_ids,
            observed_ids=observed_ids,
            invalid_reply_links=invalid_reply_links,
        )
        snapshot = {
            "version": "recorder_case_dossier_v1",
            "messageIds": observed_ids,
            "messageDigest": message_digest,
            "timeline": turn_index,
            "turnIndex": turn_index,
            "replyLinks": reply_links,
            "phaseWindows": [
                {
                    "phaseNo": int(request.phase_no),
                    "messageStartId": int(request.message_start_id),
                    "messageEndId": int(request.message_end_id),
                    "messageCount": int(request.message_count),
                }
            ],
            "coverageGuard": completeness,
        }
        return snapshot, completeness

    def build_final_transcript_snapshot(
        self,
        *,
        request: FinalDispatchRequest,
        report_payload: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        payload = report_payload if isinstance(report_payload, dict) else {}
        rows = payload.get("phaseRollupSummary")
        phase_rows = [dict(item) for item in rows if isinstance(item, dict)] if isinstance(rows, list) else []
        expected_phase_nos = list(range(int(request.phase_start_no), int(request.phase_end_no) + 1))
        observed_phase_nos = [
            int(item)
            for item in (_safe_int(row.get("phaseNo")) for row in phase_rows)
            if item is not None
        ]
        missing_phase_nos = [item for item in expected_phase_nos if item not in set(observed_phase_nos)]
        phase_windows = [
            {
                "phaseNo": _safe_int(row.get("phaseNo")),
                "messageStartId": _safe_int(row.get("messageStartId")),
                "messageEndId": _safe_int(row.get("messageEndId")),
                "messageCount": max(0, _safe_int(row.get("messageCount")) or 0),
            }
            for row in phase_rows
        ]
        total_messages = sum(int(row.get("messageCount") or 0) for row in phase_windows)
        denominator = len(expected_phase_nos) or len(observed_phase_nos)
        coverage_ratio = (
            1.0
            if denominator <= 0
            else (len(set(expected_phase_nos) & set(observed_phase_nos)) / float(denominator))
        )
        completeness = {
            "guard": "case_dossier_completeness_v1",
            "complete": not missing_phase_nos,
            "status": "complete" if not missing_phase_nos else "partial",
            "coverageRatio": round(max(0.0, min(1.0, coverage_ratio)), 4),
            "expectedPhaseNos": expected_phase_nos,
            "observedPhaseNos": observed_phase_nos,
            "missingPhaseNos": missing_phase_nos,
            "invalidReplyLinks": [],
        }
        snapshot = {
            "version": "recorder_case_dossier_v1",
            "messageIds": [],
            "messageDigest": [],
            "timeline": phase_windows,
            "turnIndex": [],
            "replyLinks": [],
            "phaseWindows": phase_windows,
            "phaseRollupSummary": phase_rows,
            "coverageGuard": completeness,
            "messageCount": total_messages,
        }
        return snapshot, completeness


def build_case_dossier_enrichment(
    *,
    request: PhaseDispatchRequest | FinalDispatchRequest,
    dispatch_type: str,
    report_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    recorder = RecorderRole()
    if dispatch_type == "phase" and isinstance(request, PhaseDispatchRequest):
        transcript_snapshot, completeness = recorder.build_phase_transcript_snapshot(
            request=request
        )
        message_rows = [_payload_from_message(message) for message in request.messages]
        phase = {"no": int(request.phase_no)}
        message_window = {
            "startId": int(request.message_start_id),
            "endId": int(request.message_end_id),
            "count": int(request.message_count),
        }
    elif isinstance(request, FinalDispatchRequest):
        transcript_snapshot, completeness = recorder.build_final_transcript_snapshot(
            request=request,
            report_payload=report_payload,
        )
        message_rows = []
        phase = {
            "startNo": int(getattr(request, "phase_start_no", 0) or 0),
            "endNo": int(getattr(request, "phase_end_no", 0) or 0),
        }
        message_window = {"count": int(transcript_snapshot.get("messageCount") or 0)}
    else:
        raise ValueError("case_dossier_dispatch_request_invalid")
    clerk = ClerkRole()
    input_validation = clerk.build_input_validation(
        request=request,
        dispatch_type=dispatch_type,
        report_payload=report_payload,
        expected_ids=completeness.get("expectedMessageIds"),
        observed_ids=completeness.get("observedMessageIds"),
    )
    redaction_summary = clerk.build_redaction_summary(
        message_rows=message_rows,
        sensitive_field_hits=list(input_validation.get("sensitiveFieldHits") or []),
    )
    return {
        "phase": phase,
        "messageWindow": message_window,
        "inputValidation": input_validation,
        "redactionSummary": redaction_summary,
        "transcriptSnapshot": transcript_snapshot,
        "completeness": completeness,
    }


def _phase_agent1_evidence_refs(payload: dict[str, Any], *, side: str) -> dict[str, list[Any]]:
    agent1 = payload.get("agent1Score") if isinstance(payload.get("agent1Score"), dict) else {}
    refs = agent1.get("evidenceRefs") if isinstance(agent1.get("evidenceRefs"), dict) else {}
    side_refs = refs.get(side) if isinstance(refs.get(side), dict) else {}
    return {
        "messageIds": list(side_refs.get("messageIds") or []),
        "chunkIds": list(side_refs.get("chunkIds") or []),
    }


@dataclass(frozen=True)
class EvidenceAgentRole:
    def build_phase_builder(
        self,
        *,
        request: PhaseDispatchRequest,
        report_payload: dict[str, Any],
    ) -> EvidenceLedgerBuilder:
        builder = EvidenceLedgerBuilder()
        for message in request.messages:
            row = _payload_from_message(message)
            builder.register_message_ref(
                phase_no=int(request.phase_no),
                side=str(row.get("side") or ""),
                message_id=_message_id_from_payload(row),
                reason="case_dossier_message_ref",
            )
        for side in ("pro", "con"):
            refs = _phase_agent1_evidence_refs(report_payload, side=side)
            for message_id in refs["messageIds"]:
                builder.register_message_ref(
                    phase_no=int(request.phase_no),
                    side=side,
                    message_id=message_id,
                    reason="agent1_evidence_ref",
                )
            for chunk_id in refs["chunkIds"]:
                builder.register_retrieval_chunk(
                    phase_no=int(request.phase_no),
                    side=side,
                    chunk_id=chunk_id,
                    reason="agent1_evidence_ref",
                )

            bundle_key = "proRetrievalBundle" if side == "pro" else "conRetrievalBundle"
            bundle = (
                report_payload.get(bundle_key)
                if isinstance(report_payload.get(bundle_key), dict)
                else {}
            )
            items = bundle.get("items") if isinstance(bundle.get("items"), list) else []
            for item in items:
                if not isinstance(item, dict):
                    continue
                builder.register_retrieval_chunk(
                    phase_no=int(request.phase_no),
                    side=side,
                    chunk_id=item.get("chunkId") or item.get("chunk_id"),
                    source_url=item.get("sourceUrl") or item.get("source_url"),
                    title=item.get("title"),
                    score=item.get("score"),
                    conflict=item.get("conflict"),
                    reason="retrieval_snapshot",
                )

        agent2 = (
            report_payload.get("agent2Score")
            if isinstance(report_payload.get("agent2Score"), dict)
            else {}
        )
        for path_type, rows in (
            ("agent2_hit", agent2.get("hitItems")),
            ("agent2_miss", agent2.get("missItems")),
        ):
            for item in rows if isinstance(rows, list) else []:
                side = str(item or "").split(":", 1)[0].strip().lower()
                if side not in {"pro", "con"}:
                    side = "pro" if path_type == "agent2_hit" else "con"
                builder.register_agent2_path_item(
                    phase_no=int(request.phase_no),
                    side=side,
                    path_type=path_type,
                    item=item,
                    reason="rebuttal_judge_signal",
                )
        return builder

    def build_phase_evidence_ledger(
        self,
        *,
        request: PhaseDispatchRequest,
        report_payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self.build_phase_builder(
            request=request,
            report_payload=report_payload,
        ).build_payload()


@dataclass(frozen=True)
class ClaimGraphRole:
    def build_phase_claim_graph(
        self,
        *,
        request: PhaseDispatchRequest,
        report_payload: dict[str, Any],
        evidence_ref_resolver: Any = None,
    ) -> dict[str, Any]:
        payload = build_claim_graph_payload(
            phase_payloads=[(int(request.phase_no), report_payload)],
            verdict_evidence_refs=[],
            evidence_ref_resolver=evidence_ref_resolver,
        )
        claim_graph = payload.get("claimGraph")
        return dict(claim_graph) if isinstance(claim_graph, dict) else _empty_claim_graph()

    def normalize_claim_graph(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        claim_graph = dict(payload) if isinstance(payload, dict) else _empty_claim_graph()
        claims = claim_graph.get("claims")
        if not isinstance(claims, list):
            claims = claim_graph.get("nodes") if isinstance(claim_graph.get("nodes"), list) else []
            claim_graph["claims"] = list(claims)
        edges = claim_graph.get("edges") if isinstance(claim_graph.get("edges"), list) else []
        claim_graph.setdefault("supportEdges", claim_graph.get("support_edges") or [])
        claim_graph.setdefault("support_edges", claim_graph.get("supportEdges") or [])
        claim_graph.setdefault("rebuttalEdges", claim_graph.get("rebuttal_edges") or edges)
        claim_graph.setdefault("rebuttal_edges", claim_graph.get("rebuttalEdges") or edges)
        unanswered = claim_graph.get("unansweredClaims")
        if not isinstance(unanswered, list):
            unanswered = claim_graph.get("unanswered_claims") if isinstance(claim_graph.get("unanswered_claims"), list) else []
            claim_graph["unansweredClaims"] = list(unanswered)
        claim_graph.setdefault("unanswered_claims", claim_graph.get("unansweredClaims") or [])
        claim_graph.setdefault("pivotalTurns", claim_graph.get("pivotal_turns") or [])
        claim_graph.setdefault("pivotal_turns", claim_graph.get("pivotalTurns") or [])
        claim_graph.setdefault("items", claim_graph.get("claims") or [])
        claim_graph.setdefault("unansweredClaimIds", [])
        claim_graph.setdefault("stats", {})
        claim_graph.setdefault(
            "agentMeta",
            {
                "ownerAgent": "claim_graph_agent",
                "decisionAuthority": "non_verdict",
                "officialVerdictAuthority": False,
            },
        )
        return claim_graph


def _empty_claim_graph() -> dict[str, Any]:
    return {
        "pipelineVersion": "v1-claim-graph-bootstrap",
        "claims": [],
        "nodes": [],
        "items": [],
        "supportEdges": [],
        "support_edges": [],
        "rebuttalEdges": [],
        "rebuttal_edges": [],
        "unansweredClaims": [],
        "unanswered_claims": [],
        "unansweredClaimIds": [],
        "pivotalTurns": [],
        "pivotal_turns": [],
        "stats": {},
        "agentMeta": {
            "ownerAgent": "claim_graph_agent",
            "decisionAuthority": "non_verdict",
            "officialVerdictAuthority": False,
        },
    }


def _normalize_evidence_ledger(payload: dict[str, Any] | None) -> dict[str, Any]:
    evidence = dict(payload) if isinstance(payload, dict) else EvidenceLedgerBuilder().build_payload()
    message_refs = evidence.get("messageRefs") if isinstance(evidence.get("messageRefs"), list) else []
    source_citations = (
        evidence.get("sourceCitations")
        if isinstance(evidence.get("sourceCitations"), list)
        else []
    )
    conflict_sources = (
        evidence.get("conflictSources")
        if isinstance(evidence.get("conflictSources"), list)
        else []
    )
    evidence.setdefault("messageRefs", message_refs)
    evidence.setdefault("message_refs", evidence.get("messageRefs") or [])
    evidence.setdefault("sourceCitations", source_citations)
    evidence.setdefault("source_citations", evidence.get("sourceCitations") or [])
    evidence.setdefault("conflictSources", conflict_sources)
    evidence.setdefault("conflict_sources", evidence.get("conflictSources") or [])
    evidence.setdefault("entries", evidence.get("entries") if isinstance(evidence.get("entries"), list) else [])
    evidence.setdefault("stats", {})
    reliability_notes = evidence.get("reliabilityNotes")
    if not isinstance(reliability_notes, dict):
        reliability_notes = {"level": "unknown", "lowReliabilityRatio": 0.0, "reviewSignals": []}
    evidence.setdefault("reliabilityNotes", reliability_notes)
    evidence.setdefault("reliability_notes", reliability_notes)
    sufficiency = evidence.get("evidenceSufficiency")
    if not isinstance(sufficiency, dict):
        sufficiency = {
            "passed": bool(evidence.get("entries")),
            "status": "sufficient" if evidence.get("entries") else "insufficient",
            "reviewSignals": [] if evidence.get("entries") else ["evidence_missing"],
        }
    evidence.setdefault("evidenceSufficiency", sufficiency)
    evidence.setdefault("evidence_sufficiency", sufficiency)
    bundle_meta = evidence.get("bundleMeta") if isinstance(evidence.get("bundleMeta"), dict) else {}
    bundle_meta.setdefault("ownerAgent", "evidence_agent")
    bundle_meta.setdefault("decisionAuthority", "non_verdict")
    bundle_meta.setdefault("officialVerdictAuthority", False)
    evidence["bundleMeta"] = bundle_meta
    evidence.pop("winner", None)
    return evidence


def _normalize_winner(value: Any) -> str | None:
    token = str(value or "").strip().lower()
    if token in {"pro", "con", "draw"}:
        return token
    return None


def _derive_winner_from_weighted_score(payload: dict[str, Any]) -> str | None:
    weighted = payload.get("agent3WeightedScore")
    if not isinstance(weighted, dict):
        return None
    try:
        pro_score = float(weighted.get("pro"))
        con_score = float(weighted.get("con"))
    except (TypeError, ValueError):
        return None
    if pro_score > con_score:
        return "pro"
    if con_score > pro_score:
        return "con"
    return "draw"


def _phase_claim_graph(payload: dict[str, Any]) -> dict[str, Any]:
    agent2 = payload.get("agent2Score")
    if not isinstance(agent2, dict):
        return {"stats": {}, "items": [], "unansweredClaimIds": []}
    hit_items = agent2.get("hitItems") if isinstance(agent2.get("hitItems"), list) else []
    miss_items = agent2.get("missItems") if isinstance(agent2.get("missItems"), list) else []
    items = [
        {"claimId": str(item), "status": "hit"}
        for item in hit_items
        if str(item or "").strip()
    ] + [
        {"claimId": str(item), "status": "miss"}
        for item in miss_items
        if str(item or "").strip()
    ]
    unanswered = [str(item) for item in miss_items if str(item or "").strip()]
    return {
        "stats": {
            "hitItems": len(hit_items),
            "missItems": len(miss_items),
            "totalClaims": len(items),
            "unansweredClaims": len(unanswered),
        },
        "items": items,
        "unansweredClaimIds": unanswered,
    }


def _phase_evidence_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    pro_bundle = payload.get("proRetrievalBundle")
    con_bundle = payload.get("conRetrievalBundle")
    pro_items = pro_bundle.get("items") if isinstance(pro_bundle, dict) else []
    con_items = con_bundle.get("items") if isinstance(con_bundle, dict) else []
    entries = [
        item
        for item in [*(pro_items if isinstance(pro_items, list) else []), *(con_items if isinstance(con_items, list) else [])]
        if isinstance(item, dict)
    ]
    return {
        "entries": entries,
        "sourceCitations": [],
        "conflictSources": [],
        "stats": {
            "entryCount": len(entries),
        },
    }


def _phase_panel_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    weighted = payload.get("agent3WeightedScore")
    pro_score = weighted.get("pro") if isinstance(weighted, dict) else None
    con_score = weighted.get("con") if isinstance(weighted, dict) else None
    winner = _derive_winner_from_weighted_score(payload)
    judges = {
        "phasePanel": {
            "winner": winner,
            "proScore": pro_score,
            "conScore": con_score,
            "reason": "phase_weighted_score",
        }
    }
    return {
        "topWinner": winner,
        "disagreementRatio": 0.0,
        "judges": judges,
    }


def _extract_final_panel_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    verdict_ledger = payload.get("verdictLedger")
    if not isinstance(verdict_ledger, dict):
        return {
            "topWinner": _normalize_winner(payload.get("winner")),
            "disagreementRatio": 0.0,
            "judges": {},
        }
    panel_decisions = verdict_ledger.get("panelDecisions")
    if not isinstance(panel_decisions, dict):
        return {
            "topWinner": _normalize_winner(payload.get("winner")),
            "disagreementRatio": 0.0,
            "judges": {},
        }
    return {
        "topWinner": _normalize_winner(
            panel_decisions.get("topWinner") or payload.get("winner")
        ),
        "disagreementRatio": float(panel_decisions.get("panelDisagreementRatio") or 0.0),
        "judges": (
            panel_decisions.get("judges")
            if isinstance(panel_decisions.get("judges"), dict)
            else {}
        ),
    }


def _extract_final_fairness_gate(payload: dict[str, Any]) -> dict[str, Any]:
    verdict_ledger = payload.get("verdictLedger")
    arbitration = (
        verdict_ledger.get("arbitration")
        if isinstance(verdict_ledger, dict) and isinstance(verdict_ledger.get("arbitration"), dict)
        else {}
    )
    gate_decision = str(arbitration.get("gateDecision") or "").strip().lower()
    review_required = bool(payload.get("reviewRequired"))
    if gate_decision not in {"pass_through", "blocked_to_draw"}:
        gate_decision = "blocked_to_draw" if review_required else "pass_through"

    audit_alert_ids = [
        str(item.get("alertId"))
        for item in (payload.get("auditAlerts") if isinstance(payload.get("auditAlerts"), list) else [])
        if isinstance(item, dict) and str(item.get("alertId") or "").strip()
    ]
    fairness_summary = payload.get("fairnessSummary")
    reasons = (
        fairness_summary.get("reviewReasons")
        if isinstance(fairness_summary, dict)
        and isinstance(fairness_summary.get("reviewReasons"), list)
        else []
    )
    if not reasons and review_required:
        reasons = (
            payload.get("errorCodes")
            if isinstance(payload.get("errorCodes"), list)
            else []
        )
    return {
        "decision": gate_decision,
        "reviewRequired": review_required,
        "reasons": [str(item) for item in reasons if str(item or "").strip()],
        "auditAlertIds": audit_alert_ids,
    }


def _extract_final_verdict(payload: dict[str, Any]) -> dict[str, Any]:
    verdict_ledger = payload.get("verdictLedger")
    arbitration = (
        verdict_ledger.get("arbitration")
        if isinstance(verdict_ledger, dict) and isinstance(verdict_ledger.get("arbitration"), dict)
        else {}
    )
    decision_path = arbitration.get("decisionPath")
    if not isinstance(decision_path, list) or not decision_path:
        decision_path = ["judge_panel", "fairness_sentinel", "chief_arbiter"]
    return {
        "winner": _normalize_winner(payload.get("winner")),
        "needsDrawVote": bool(payload.get("needsDrawVote")),
        "reviewRequired": bool(payload.get("reviewRequired")),
        "decisionPath": [str(item) for item in decision_path if str(item or "").strip()],
    }


def _extract_final_message_count(payload: dict[str, Any]) -> int:
    rows = payload.get("phaseRollupSummary")
    if not isinstance(rows, list):
        return 0
    total = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            total += max(0, int(row.get("messageCount") or 0))
        except (TypeError, ValueError):
            continue
    return total


def build_phase_judge_workflow_payload(
    *,
    request: PhaseDispatchRequest,
    report_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = report_payload if isinstance(report_payload, dict) else {}
    winner = _normalize_winner(payload.get("winner")) or _derive_winner_from_weighted_score(payload)
    review_required = bool(payload.get("reviewRequired"))
    case_dossier_enrichment = build_case_dossier_enrichment(
        request=request,
        dispatch_type="phase",
        report_payload=payload,
    )
    evidence_agent = EvidenceAgentRole()
    evidence_builder = evidence_agent.build_phase_builder(
        request=request,
        report_payload=payload,
    )
    claim_graph = ClaimGraphRole().build_phase_claim_graph(
        request=request,
        report_payload=payload,
        evidence_ref_resolver=lambda phase_no, side, message_ids, chunk_ids: (
            evidence_builder.resolve_reference_ids(
                phase_no=phase_no,
                side=side,
                message_ids=message_ids,
                chunk_ids=chunk_ids,
            )
        ),
    )
    evidence_ledger = evidence_builder.build_payload()
    state = build_judge_role_domain_state(
        case_id=request.case_id,
        dispatch_type="phase",
        trace_id=request.trace_id,
        scope_id=request.scope_id,
        session_id=request.session_id,
        phase_start_no=request.phase_no,
        phase_end_no=request.phase_no,
        message_count=request.message_count,
        judge_policy_version=request.judge_policy_version,
        rubric_version=request.rubric_version,
        topic_domain=request.topic_domain,
        claim_graph=claim_graph,
        evidence_bundle=evidence_ledger,
        panel_bundle=_phase_panel_bundle(payload),
        fairness_gate={
            "decision": "blocked_to_draw" if review_required else "pass_through",
            "reviewRequired": review_required,
        },
        verdict={
            "winner": winner,
            "needsDrawVote": bool(payload.get("needsDrawVote")),
            "reviewRequired": review_required,
        },
        opinion={
            "debateSummary": payload.get("debateSummary"),
            "sideAnalysis": (
                payload.get("sideAnalysis")
                if isinstance(payload.get("sideAnalysis"), dict)
                else {}
            ),
            "verdictReason": payload.get("verdictReason"),
        },
        case_dossier_enrichment=case_dossier_enrichment,
    )
    judge_payload = state.to_payload()
    validate_judge_app_domain_payload(judge_payload)
    return judge_payload


def build_final_judge_workflow_payload(
    *,
    request: FinalDispatchRequest,
    report_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = report_payload if isinstance(report_payload, dict) else {}
    phase_start_no = int(request.phase_start_no)
    phase_end_no = int(request.phase_end_no)
    case_dossier_enrichment = build_case_dossier_enrichment(
        request=request,
        dispatch_type="final",
        report_payload=payload,
    )
    state = build_judge_role_domain_state(
        case_id=request.case_id,
        dispatch_type="final",
        trace_id=request.trace_id,
        scope_id=request.scope_id,
        session_id=request.session_id,
        phase_start_no=phase_start_no,
        phase_end_no=phase_end_no,
        message_count=_extract_final_message_count(payload),
        judge_policy_version=request.judge_policy_version,
        rubric_version=request.rubric_version,
        topic_domain=request.topic_domain,
        claim_graph=ClaimGraphRole().normalize_claim_graph(
            payload.get("claimGraph")
            if isinstance(payload.get("claimGraph"), dict)
            else None
        ),
        evidence_bundle=_normalize_evidence_ledger(
            payload.get("evidenceLedger")
            if isinstance(payload.get("evidenceLedger"), dict)
            else None
        ),
        panel_bundle=_extract_final_panel_bundle(payload),
        fairness_gate=_extract_final_fairness_gate(payload),
        verdict=_extract_final_verdict(payload),
        opinion={
            "debateSummary": payload.get("debateSummary"),
            "sideAnalysis": (
                payload.get("sideAnalysis")
                if isinstance(payload.get("sideAnalysis"), dict)
                else {}
            ),
            "verdictReason": payload.get("verdictReason"),
        },
        case_dossier_enrichment=case_dossier_enrichment,
    )
    judge_payload = state.to_payload()
    validate_judge_app_domain_payload(judge_payload)
    return judge_payload
