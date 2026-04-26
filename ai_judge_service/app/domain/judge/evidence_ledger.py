from __future__ import annotations

import hashlib
from typing import Any

CITATION_VERIFICATION_VERSION = "evidence-citation-verification-v1"
CITATION_VERIFICATION_STATUSES = {
    "passed",
    "warning",
    "blocked",
    "env_blocked",
}

_REAL_ENVIRONMENT_MODES = {
    "real",
    "prod",
    "production",
    "staging",
}
_LOCAL_REFERENCE_ENVIRONMENT_MODES = {
    "local",
    "local_reference",
    "local-reference",
}
_FORBIDDEN_CITATION_KEYS = {
    "apikey",
    "api_key",
    "bucket",
    "endpoint",
    "internalaudit",
    "internal_audit",
    "objectstorepath",
    "object_store_path",
    "privateaudit",
    "private_audit",
    "privatenote",
    "private_note",
    "provider",
    "providertoken",
    "provider_token",
    "rawnote",
    "raw_note",
    "rawprivate",
    "raw_private",
    "rawprompt",
    "raw_prompt",
    "rawtrace",
    "raw_trace",
    "secret",
    "storagepath",
    "storage_path",
    "systemprompt",
    "system_prompt",
    "token",
}
_ALLOWED_SOURCE_TYPES = {
    "document",
    "external_source",
    "knowledge_base",
    "local_reference",
    "manual_reference",
    "message_ref",
    "retrieval_chunk",
    "web",
}


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


def _safe_token(value: Any) -> str | None:
    token = str(value or "").strip()
    return token or None


def _lower_token(value: Any) -> str | None:
    token = _safe_token(value)
    return token.lower() if token is not None else None


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(row) for row in value if isinstance(row, dict)]


def _normalize_citation_key(value: Any) -> str:
    return str(value or "").replace("-", "_").replace(" ", "_").lower()


def _iter_forbidden_citation_key_hits(value: Any, *, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key or "")
            normalized = _normalize_citation_key(key_text)
            child_path = f"{path}.{key_text}"
            if normalized in _FORBIDDEN_CITATION_KEYS:
                hits.append(child_path)
            hits.extend(_iter_forbidden_citation_key_hits(child, path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_iter_forbidden_citation_key_hits(child, path=f"{path}[{index}]"))
    return hits


def _explicit_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    token = str(value or "").strip().lower()
    if token in {"1", "true", "yes", "y", "on"}:
        return True
    if token in {"0", "false", "no", "n", "off"}:
        return False
    return None


def _environment_mode_from_payload(
    *,
    payload: dict[str, Any],
    environment_mode: Any = None,
) -> str:
    bundle_meta = _dict_or_empty(payload.get("bundleMeta"))
    token = _lower_token(
        environment_mode
        or payload.get("environmentMode")
        or payload.get("environment_mode")
        or bundle_meta.get("environmentMode")
        or bundle_meta.get("environment_mode")
    )
    if token in _REAL_ENVIRONMENT_MODES:
        return token
    if token in _LOCAL_REFERENCE_ENVIRONMENT_MODES:
        return "local_reference"
    return "local_reference"


def _real_sample_ready_from_payload(
    *,
    payload: dict[str, Any],
    environment_mode: str,
    real_sample_ready: bool | None = None,
) -> bool:
    if real_sample_ready is not None:
        return bool(real_sample_ready)
    bundle_meta = _dict_or_empty(payload.get("bundleMeta"))
    for key in (
        "realSampleReady",
        "real_sample_ready",
        "realEnvEvidenceAvailable",
        "real_env_evidence_available",
    ):
        value = payload.get(key)
        if value is None:
            value = bundle_meta.get(key)
        parsed = _explicit_bool(value)
        if parsed is not None:
            return parsed
    return environment_mode in _REAL_ENVIRONMENT_MODES


def _append_reason(reason_codes: list[str], code: str) -> None:
    if code not in reason_codes:
        reason_codes.append(code)


def build_citation_verification_summary(
    evidence_payload: dict[str, Any] | None,
    *,
    verdict_evidence_refs: list[dict[str, Any]] | None = None,
    environment_mode: str | None = None,
    real_sample_ready: bool | None = None,
) -> dict[str, Any]:
    payload = _dict_or_empty(evidence_payload)
    entries = _list_of_dicts(payload.get("entries"))
    message_refs = _list_of_dicts(payload.get("messageRefs"))
    source_citations = _list_of_dicts(payload.get("sourceCitations"))
    refs_by_id = payload.get("refsById") if isinstance(payload.get("refsById"), dict) else {}
    sufficiency = _dict_or_empty(payload.get("evidenceSufficiency"))

    entry_by_id: dict[str, dict[str, Any]] = {}
    message_ref_ids: set[str] = set()
    for row in entries:
        evidence_id = _safe_token(row.get("evidenceId"))
        if not evidence_id:
            continue
        entry_by_id.setdefault(evidence_id, row)
        locator = _dict_or_empty(row.get("locator"))
        if str(row.get("kind") or "").strip() == "message_ref" and locator.get("messageId") is not None:
            message_ref_ids.add(evidence_id)
    for row in message_refs:
        evidence_id = _safe_token(row.get("evidenceId"))
        if evidence_id and row.get("messageId") is not None:
            message_ref_ids.add(evidence_id)

    approved_source_ref_ids: set[str] = set()
    weak_ref_ids: set[str] = set()
    forbidden_source_ids: set[str] = set()
    missing_ref_ids: set[str] = set()
    reason_codes: list[str] = []

    for row in source_citations:
        evidence_id = _safe_token(row.get("evidenceId"))
        source_id = _safe_token(row.get("sourceId"))
        source_type = _lower_token(row.get("sourceType") or row.get("source_type"))
        trace_field_present = any(
            _safe_token(row.get(key))
            for key in (
                "chunkId",
                "chunk_id",
                "documentId",
                "document_id",
                "sourceUrl",
                "source_url",
                "title",
                "uri",
            )
        )
        forbidden_hits = _iter_forbidden_citation_key_hits(row)
        if evidence_id and forbidden_hits:
            forbidden_source_ids.add(evidence_id)
        if source_type and source_type not in _ALLOWED_SOURCE_TYPES and evidence_id:
            forbidden_source_ids.add(evidence_id)
        if not evidence_id:
            missing_ref_ids.add(f"source:{len(missing_ref_ids) + 1}")
            continue
        if not source_id or not trace_field_present:
            weak_ref_ids.add(evidence_id)
            continue
        if evidence_id not in forbidden_source_ids:
            approved_source_ref_ids.add(evidence_id)

    referenced_ids: set[str] = set()
    for row in _list_of_dicts(verdict_evidence_refs):
        evidence_id = _safe_token(row.get("evidenceId"))
        if evidence_id:
            referenced_ids.add(evidence_id)
    for row in entries:
        evidence_id = _safe_token(row.get("evidenceId"))
        if evidence_id and bool(row.get("verdictReferenced")):
            referenced_ids.add(evidence_id)

    known_ids = set(entry_by_id) | {str(key) for key in refs_by_id.keys()}
    for evidence_id in sorted(referenced_ids):
        if evidence_id not in known_ids:
            missing_ref_ids.add(evidence_id)
            continue
        if evidence_id in message_ref_ids or evidence_id in approved_source_ref_ids:
            continue
        weak_ref_ids.add(evidence_id)

    for row in entries:
        evidence_id = _safe_token(row.get("evidenceId"))
        if not evidence_id:
            continue
        if _normalize_reliability_label(row.get("reliabilityLabel")) == "low" and (
            evidence_id in referenced_ids or not referenced_ids
        ):
            weak_ref_ids.add(evidence_id)

    if not entries:
        _append_reason(reason_codes, "citation_verifier_evidence_missing")
    if not message_ref_ids:
        _append_reason(reason_codes, "citation_verifier_message_refs_missing")
    if not source_citations:
        _append_reason(reason_codes, "citation_verifier_source_refs_missing")
    if missing_ref_ids:
        _append_reason(reason_codes, "citation_verifier_missing_evidence_refs")
    if weak_ref_ids:
        _append_reason(reason_codes, "citation_verifier_weak_citations")
    if forbidden_source_ids:
        _append_reason(reason_codes, "citation_verifier_forbidden_source_metadata")
    if sufficiency and bool(sufficiency.get("passed")) is False:
        _append_reason(reason_codes, "citation_verifier_evidence_sufficiency_failed")

    normalized_environment = _environment_mode_from_payload(
        payload=payload,
        environment_mode=environment_mode,
    )
    real_ready = _real_sample_ready_from_payload(
        payload=payload,
        environment_mode=normalized_environment,
        real_sample_ready=real_sample_ready,
    )
    if not real_ready:
        _append_reason(reason_codes, "citation_verifier_real_sample_env_blocked")

    if missing_ref_ids or forbidden_source_ids:
        status = "blocked"
    elif not real_ready:
        status = "env_blocked"
    elif weak_ref_ids or (sufficiency and bool(sufficiency.get("passed")) is False):
        status = "warning"
    else:
        status = "passed"

    return {
        "version": CITATION_VERIFICATION_VERSION,
        "status": status,
        "citationCount": len(message_ref_ids | approved_source_ref_ids),
        "messageRefCount": len(message_refs),
        "sourceRefCount": len(source_citations),
        "missingCitationCount": len(missing_ref_ids),
        "weakCitationCount": len(weak_ref_ids),
        "forbiddenSourceCount": len(forbidden_source_ids),
        "reasonCodes": reason_codes,
        "verdictRefCount": len(referenced_ids),
        "approvedCitationRefCount": len(message_ref_ids | approved_source_ref_ids),
        "environmentMode": normalized_environment,
        "realSampleReady": real_ready,
        "publicSummaryOnly": True,
        "decisionAuthority": "evidence_gate_only",
        "officialVerdictAuthority": False,
    }


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
        payload = {
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
        payload["citationVerification"] = build_citation_verification_summary(payload)
        return payload
