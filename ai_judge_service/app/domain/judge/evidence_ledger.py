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
        citation_refs: list[dict[str, Any]] = []
        conflict_refs: list[dict[str, Any]] = []
        refs_by_id: dict[str, Any] = {}
        verdict_referenced_count = 0
        for idx, entry in enumerate(entries):
            evidence_id = str(entry.get("evidenceId") or "")
            kind = str(entry.get("kind") or "")
            locator = entry.get("locator") if isinstance(entry.get("locator"), dict) else {}
            if bool(entry.get("verdictReferenced")):
                verdict_referenced_count += 1
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
                citation_refs.append(
                    {
                        "evidenceId": evidence_id,
                        "phaseNo": entry.get("phaseNo"),
                        "side": entry.get("side"),
                        "chunkId": locator.get("chunkId"),
                        "sourceUrl": locator.get("sourceUrl"),
                    }
                )
            if bool(entry.get("conflict")):
                conflict_refs.append(
                    {
                        "evidenceId": evidence_id,
                        "kind": kind,
                        "phaseNo": entry.get("phaseNo"),
                        "side": entry.get("side"),
                    }
                )
        return {
            "pipelineVersion": "v2-evidence-ledger",
            "entries": entries,
            "refsById": refs_by_id,
            "messageRefs": message_refs,
            "citationRefs": citation_refs,
            "conflictRefs": conflict_refs,
            "stats": {
                "totalEntries": len(entries),
                "messageRefCount": len(message_refs),
                "citationRefCount": len(citation_refs),
                "conflictRefCount": len(conflict_refs),
                "verdictReferencedCount": verdict_referenced_count,
            },
        }
