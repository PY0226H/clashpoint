from __future__ import annotations

import hashlib
from typing import Any


def _normalize_side(value: Any) -> str:
    side = str(value or "").strip().lower()
    if side in {"pro", "con"}:
        return side
    return "unknown"


def _short_hash(parts: list[str]) -> str:
    payload = "|".join(parts)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_reliability_label(value: Any) -> str:
    token = str(value or "").strip().lower()
    if token in {"high", "medium", "low"}:
        return token
    return "unknown"


class EvidenceLedgerBuilder:
    """Builds normalized evidence entities and stable evidence-id references."""

    def __init__(self) -> None:
        self._entries_by_id: dict[str, dict[str, Any]] = {}
        self._entry_order: list[str] = []
        self._locator_index: dict[tuple[int, str, str, str], str] = {}

    def _register_entry(
        self,
        *,
        evidence_id: str,
        kind: str,
        phase_no: int,
        side: str,
        locator: dict[str, Any],
        reliability_label: str,
        conflict: bool,
        reason: str,
    ) -> str:
        normalized_side = _normalize_side(side)
        entry = self._entries_by_id.get(evidence_id)
        if entry is None:
            entry = {
                "evidenceId": evidence_id,
                "kind": kind,
                "phaseNo": int(phase_no),
                "side": normalized_side,
                "locator": locator,
                "reliabilityLabel": reliability_label,
                "conflict": bool(conflict),
                "reasonHints": [reason] if reason else [],
                "verdictReferenced": False,
            }
            self._entries_by_id[evidence_id] = entry
            self._entry_order.append(evidence_id)
            return evidence_id

        if reason and reason not in entry["reasonHints"]:
            entry["reasonHints"].append(reason)
        if conflict:
            entry["conflict"] = True
        # 低可信度优先级更高，避免后续覆盖掉风险标记。
        if reliability_label == "low":
            entry["reliabilityLabel"] = "low"
        elif reliability_label == "medium" and entry["reliabilityLabel"] == "high":
            entry["reliabilityLabel"] = "medium"
        return evidence_id

    def register_message_ref(
        self,
        *,
        phase_no: int,
        side: str,
        message_id: Any,
        reason: str,
    ) -> str | None:
        try:
            normalized_message_id = int(message_id)
        except (TypeError, ValueError):
            return None
        normalized_side = _normalize_side(side)
        evidence_id = (
            f"ev-msg-{normalized_side}-p{int(phase_no)}-"
            f"{_short_hash([normalized_side, str(int(phase_no)), str(normalized_message_id)])}"
        )
        self._locator_index[(int(phase_no), normalized_side, "message", str(normalized_message_id))] = evidence_id
        return self._register_entry(
            evidence_id=evidence_id,
            kind="message_ref",
            phase_no=int(phase_no),
            side=normalized_side,
            locator={"messageId": normalized_message_id},
            reliability_label="high",
            conflict=False,
            reason=reason,
        )

    def register_retrieval_chunk(
        self,
        *,
        phase_no: int,
        side: str,
        chunk_id: Any,
        reason: str,
        source_url: Any = None,
        title: Any = None,
        score: Any = None,
        conflict: Any = False,
    ) -> str | None:
        normalized_chunk_id = str(chunk_id or "").strip()
        if not normalized_chunk_id:
            return None
        normalized_side = _normalize_side(side)
        normalized_phase_no = int(phase_no)
        score_value = _coerce_float(score)
        has_conflict = bool(conflict)
        if has_conflict:
            reliability_label = "low"
        elif score_value is not None and score_value >= 0.75:
            reliability_label = "high"
        else:
            reliability_label = "medium"
        evidence_id = (
            f"ev-chunk-{normalized_side}-p{normalized_phase_no}-"
            f"{_short_hash([normalized_side, str(normalized_phase_no), normalized_chunk_id])}"
        )
        self._locator_index[(normalized_phase_no, normalized_side, "chunk", normalized_chunk_id)] = evidence_id
        locator: dict[str, Any] = {"chunkId": normalized_chunk_id}
        source_text = str(source_url or "").strip()
        if source_text:
            locator["sourceUrl"] = source_text
        title_text = str(title or "").strip()
        if title_text:
            locator["title"] = title_text
        if score_value is not None:
            locator["score"] = round(score_value, 4)
        return self._register_entry(
            evidence_id=evidence_id,
            kind="retrieval_chunk",
            phase_no=normalized_phase_no,
            side=normalized_side,
            locator=locator,
            reliability_label=reliability_label,
            conflict=has_conflict,
            reason=reason,
        )

    def register_agent2_path_item(
        self,
        *,
        phase_no: int,
        side: str,
        path_type: str,
        item: Any,
        reason: str,
    ) -> str | None:
        content = str(item or "").strip()
        if not content:
            return None
        normalized_side = _normalize_side(side)
        normalized_type = str(path_type or "").strip().lower() or "agent2_path_item"
        is_miss = normalized_type.endswith("miss")
        evidence_id = (
            f"ev-path-{normalized_side}-p{int(phase_no)}-"
            f"{_short_hash([normalized_side, str(int(phase_no)), normalized_type, content])}"
        )
        return self._register_entry(
            evidence_id=evidence_id,
            kind=normalized_type,
            phase_no=int(phase_no),
            side=normalized_side,
            locator={"item": content},
            reliability_label="low" if is_miss else "medium",
            conflict=is_miss,
            reason=reason,
        )

    def resolve_reference_ids(
        self,
        *,
        phase_no: int,
        side: str,
        message_ids: list[int],
        chunk_ids: list[str],
    ) -> list[str]:
        normalized_side = _normalize_side(side)
        out: list[str] = []
        seen: set[str] = set()
        for message_id in message_ids:
            key = (int(phase_no), normalized_side, "message", str(int(message_id)))
            evidence_id = self._locator_index.get(key)
            if evidence_id and evidence_id not in seen:
                seen.add(evidence_id)
                out.append(evidence_id)
        for chunk_id in chunk_ids:
            key = (int(phase_no), normalized_side, "chunk", str(chunk_id))
            evidence_id = self._locator_index.get(key)
            if evidence_id and evidence_id not in seen:
                seen.add(evidence_id)
                out.append(evidence_id)
        return out

    def mark_verdict_referenced(self, evidence_id: str | None) -> None:
        token = str(evidence_id or "").strip()
        if not token:
            return
        entry = self._entries_by_id.get(token)
        if entry is None:
            return
        entry["verdictReferenced"] = True

    def build_payload(self) -> dict[str, Any]:
        entries = [dict(self._entries_by_id[evidence_id]) for evidence_id in self._entry_order]
        message_refs: list[dict[str, Any]] = []
        source_citations: list[dict[str, Any]] = []
        conflict_sources: list[dict[str, Any]] = []
        refs_by_id: dict[str, Any] = {}
        verdict_referenced_count = 0
        reliability_counts: dict[str, int] = {
            "high": 0,
            "medium": 0,
            "low": 0,
            "unknown": 0,
        }
        verdict_referenced_reliability_counts: dict[str, int] = {
            "high": 0,
            "medium": 0,
            "low": 0,
            "unknown": 0,
        }
        conflict_reason_counts: dict[str, int] = {}
        for idx, entry in enumerate(entries):
            evidence_id = str(entry.get("evidenceId") or "")
            kind = str(entry.get("kind") or "")
            locator = entry.get("locator") if isinstance(entry.get("locator"), dict) else {}
            reliability_label = _normalize_reliability_label(entry.get("reliabilityLabel"))
            reliability_counts[reliability_label] = int(reliability_counts.get(reliability_label, 0)) + 1
            if bool(entry.get("verdictReferenced")):
                verdict_referenced_count += 1
                verdict_referenced_reliability_counts[reliability_label] = (
                    int(verdict_referenced_reliability_counts.get(reliability_label, 0)) + 1
                )
            refs_by_id[evidence_id] = {
                "index": idx,
                "kind": kind,
                "phaseNo": entry.get("phaseNo"),
                "side": entry.get("side"),
            }
            if kind == "message_ref":
                message_refs.append(
                    {
                        "evidenceId": evidence_id,
                        "phaseNo": entry.get("phaseNo"),
                        "side": entry.get("side"),
                        "messageId": locator.get("messageId"),
                    }
                )
            if kind == "retrieval_chunk":
                chunk_id = str(locator.get("chunkId") or "").strip()
                source_url = str(locator.get("sourceUrl") or "").strip()
                source_id = f"src-{_short_hash([chunk_id, source_url])}"
                source_citations.append(
                    {
                        "sourceId": source_id,
                        "evidenceId": evidence_id,
                        "phaseNo": entry.get("phaseNo"),
                        "side": entry.get("side"),
                        "chunkId": chunk_id or None,
                        "sourceUrl": source_url or None,
                        "title": locator.get("title"),
                        "score": locator.get("score"),
                        "reliabilityLabel": reliability_label,
                    }
                )
            if bool(entry.get("conflict")):
                reason_hints = [
                    str(item).strip()
                    for item in (entry.get("reasonHints") or [])
                    if str(item).strip()
                ]
                primary_reason = reason_hints[0] if reason_hints else (kind or "unknown_conflict")
                conflict_reason_counts[primary_reason] = int(
                    conflict_reason_counts.get(primary_reason, 0)
                ) + 1
                conflict_sources.append(
                    {
                        "evidenceId": evidence_id,
                        "sourceId": (
                            f"src-{_short_hash([str(locator.get('chunkId') or ''), str(locator.get('sourceUrl') or '')])}"
                            if kind == "retrieval_chunk"
                            else None
                        ),
                        "kind": kind,
                        "phaseNo": entry.get("phaseNo"),
                        "side": entry.get("side"),
                        "reliabilityLabel": reliability_label,
                        "reasonHints": reason_hints,
                        "primaryReason": primary_reason,
                    }
                )
        low_count = int(reliability_counts.get("low", 0))
        medium_count = int(reliability_counts.get("medium", 0))
        high_count = int(reliability_counts.get("high", 0))
        total_entries = len(entries)
        citation_count = len(source_citations)
        message_ref_count = len(message_refs)
        low_ratio = round(low_count / float(max(1, total_entries)), 4)
        sufficient = total_entries > 0 and (message_ref_count > 0 or citation_count > 0) and low_ratio <= 0.5
        review_signals: list[str] = []
        if total_entries <= 0:
            review_signals.append("evidence_missing")
        if message_ref_count <= 0:
            review_signals.append("message_refs_missing")
        if citation_count <= 0:
            review_signals.append("source_citations_missing")
        if low_ratio > 0.5:
            review_signals.append("low_reliability_ratio_high")
        reliability_notes = {
            "level": (
                "high"
                if sufficient and high_count >= max(medium_count, low_count)
                else ("medium" if sufficient else "low")
            ),
            "lowReliabilityRatio": low_ratio,
            "reviewSignals": review_signals,
        }
        evidence_sufficiency = {
            "passed": sufficient,
            "status": "sufficient" if sufficient else "insufficient",
            "totalEntries": total_entries,
            "messageRefCount": message_ref_count,
            "sourceCitationCount": citation_count,
            "conflictSourceCount": len(conflict_sources),
            "reviewSignals": review_signals,
        }
        return {
            "pipelineVersion": "v3-evidence-bundle",
            "entries": entries,
            "refsById": refs_by_id,
            "messageRefs": message_refs,
            "message_refs": message_refs,
            "sourceCitations": source_citations,
            "source_citations": source_citations,
            "conflictSources": conflict_sources,
            "conflict_sources": conflict_sources,
            "reliabilityNotes": reliability_notes,
            "reliability_notes": reliability_notes,
            "evidenceSufficiency": evidence_sufficiency,
            "evidence_sufficiency": evidence_sufficiency,
            "stats": {
                "totalEntries": len(entries),
                "messageRefCount": len(message_refs),
                "sourceCitationCount": len(source_citations),
                "conflictSourceCount": len(conflict_sources),
                "verdictReferencedCount": verdict_referenced_count,
                "reliabilityCounts": reliability_counts,
                "verdictReferencedReliabilityCounts": verdict_referenced_reliability_counts,
                "conflictReasonCounts": conflict_reason_counts,
            },
            "bundleMeta": {
                "kind": "evidence_bundle",
                "ownerAgent": "evidence_agent",
                "decisionAuthority": "non_verdict",
                "officialVerdictAuthority": False,
            },
        }
