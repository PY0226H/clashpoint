from __future__ import annotations

import re
from typing import Any, Callable

_CLAIM_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+")
_SIDE_PREFIX_RE = re.compile(r"^(pro|con)\s*:\s*", re.IGNORECASE)
_COMMON_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "then",
    "from",
    "have",
    "has",
    "are",
    "was",
    "were",
    "is",
    "to",
    "of",
    "in",
    "a",
    "an",
    "or",
    "on",
    "as",
    "at",
    "it",
    "be",
    "we",
    "you",
    "they",
    "我",
    "你",
    "他",
    "她",
    "它",
    "我们",
    "你们",
    "他们",
    "是",
    "了",
    "和",
    "与",
    "在",
    "对",
    "并",
    "及",
    "的",
    "呢",
    "吗",
    "啊",
}


def _clean_claim_text(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    text = _SIDE_PREFIX_RE.sub("", text).strip()
    return " ".join(text.split())


def _normalize_claim_key(text: str) -> str:
    lowered = _clean_claim_text(text).lower()
    lowered = lowered.replace("（", "(").replace("）", ")")
    lowered = lowered.replace("，", ",").replace("。", ".").replace("；", ";")
    lowered = lowered.replace("：", ":").replace("！", "!").replace("？", "?")
    lowered = re.sub(r"[\s\-\_\.\,\:\;\!\?\(\)\[\]\"\'`]+", " ", lowered)
    return " ".join(lowered.split())[:180]


def _tokenize_claim_text(text: str) -> set[str]:
    tokens: set[str] = set()
    for token in _CLAIM_TOKEN_RE.findall(str(text or "").lower()):
        normalized = token.strip()
        if len(normalized) < 2:
            continue
        if normalized in _COMMON_STOPWORDS:
            continue
        tokens.add(normalized)
    return tokens


def _extract_prefixed_items(items: Any, *, side: str) -> list[str]:
    if not isinstance(items, list):
        return []
    normalized_side = side.strip().lower()
    outputs: list[str] = []
    for row in items:
        text = str(row or "").strip()
        if not text:
            continue
        if ":" in text:
            prefix, content = text.split(":", 1)
            if prefix.strip().lower() != normalized_side:
                continue
            cleaned = _clean_claim_text(content)
            if cleaned:
                outputs.append(cleaned)
            continue
        cleaned = _clean_claim_text(text)
        if cleaned:
            outputs.append(cleaned)
    return outputs


def _extract_summary_lines(payload: dict[str, Any], *, side: str) -> list[str]:
    bundle_key = "proSummaryGrounded" if side == "pro" else "conSummaryGrounded"
    summary = payload.get(bundle_key) if isinstance(payload.get(bundle_key), dict) else {}
    text = str(summary.get("text") or "").strip()
    if not text:
        return []
    lines = re.split(r"[\n;；。!！?？]", text)
    outputs: list[str] = []
    for line in lines:
        cleaned = _clean_claim_text(line)
        if not cleaned:
            continue
        outputs.append(cleaned)
        if len(outputs) >= 2:
            break
    return outputs


def _extract_agent2_audit_points(payload: dict[str, Any], *, side: str) -> list[str]:
    judge_trace = payload.get("judgeTrace") if isinstance(payload.get("judgeTrace"), dict) else {}
    agent2_audit = judge_trace.get("agent2Audit") if isinstance(judge_trace.get("agent2Audit"), dict) else {}
    paths = agent2_audit.get("paths") if isinstance(agent2_audit.get("paths"), dict) else {}
    side_path = paths.get(side) if isinstance(paths.get(side), dict) else {}
    points: list[str] = []
    for field in ("keyPoints", "hitPoints", "missPoints"):
        rows = side_path.get(field)
        if not isinstance(rows, list):
            continue
        for item in rows:
            cleaned = _clean_claim_text(item)
            if cleaned:
                points.append(cleaned)
    return points


def _collect_side_candidates(payload: dict[str, Any], *, side: str) -> list[tuple[str, str]]:
    outputs: list[tuple[str, str]] = []
    for text in _extract_agent2_audit_points(payload, side=side):
        outputs.append((text, "agent2_audit"))

    agent2 = payload.get("agent2Score") if isinstance(payload.get("agent2Score"), dict) else {}
    for key, source in (("hitItems", "agent2_hit"), ("missItems", "agent2_miss")):
        for text in _extract_prefixed_items(agent2.get(key), side=side):
            outputs.append((text, source))

    for text in _extract_summary_lines(payload, side=side):
        outputs.append((text, "summary_fallback"))

    deduped: list[tuple[str, str]] = []
    seen_keys: set[str] = set()
    for text, source in outputs:
        key = _normalize_claim_key(text)
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append((text, source))
        if len(deduped) >= 6:
            break
    return deduped


def _collect_side_evidence_refs(payload: dict[str, Any], *, side: str) -> tuple[list[int], list[str]]:
    agent1 = payload.get("agent1Score") if isinstance(payload.get("agent1Score"), dict) else {}
    refs = agent1.get("evidenceRefs") if isinstance(agent1.get("evidenceRefs"), dict) else {}
    side_ref = refs.get(side) if isinstance(refs.get(side), dict) else {}
    message_ids: list[int] = []
    chunk_ids: list[str] = []

    for raw in side_ref.get("messageIds") or []:
        try:
            message_id = int(raw)
        except (TypeError, ValueError):
            continue
        if message_id not in message_ids:
            message_ids.append(message_id)
        if len(message_ids) >= 8:
            break
    for raw in side_ref.get("chunkIds") or []:
        chunk_id = str(raw or "").strip()
        if not chunk_id:
            continue
        if chunk_id not in chunk_ids:
            chunk_ids.append(chunk_id)
        if len(chunk_ids) >= 8:
            break
    return message_ids, chunk_ids


def _is_claim_referenced_by_verdict(
    *,
    verdict_evidence_refs: list[dict[str, Any]],
    side: str,
    phase_no: int,
    message_ids: list[int],
    chunk_ids: list[str],
) -> bool:
    message_set = set(message_ids)
    chunk_set = set(chunk_ids)
    for item in verdict_evidence_refs:
        if not isinstance(item, dict):
            continue
        if str(item.get("side") or "").strip().lower() != side:
            continue
        try:
            item_phase_no = int(item.get("phaseNo"))
        except (TypeError, ValueError):
            item_phase_no = 0
        if item_phase_no != phase_no:
            continue
        try:
            message_id = int(item.get("messageId"))
        except (TypeError, ValueError):
            message_id = -1
        chunk_id = str(item.get("chunkId") or "").strip()
        if message_id in message_set or (chunk_id and chunk_id in chunk_set):
            return True
    return False


def _claim_overlap_score(left_tokens: set[str], right_tokens: set[str]) -> float:
    if not left_tokens or not right_tokens:
        return 0.0
    inter = left_tokens & right_tokens
    union = left_tokens | right_tokens
    if not union:
        return 0.0
    return len(inter) / float(len(union))


def _collect_core_claims(nodes: list[dict[str, Any]], *, side: str, limit: int = 6) -> list[dict[str, Any]]:
    scoped = [row for row in nodes if row.get("side") == side]
    scoped.sort(
        key=lambda row: (
            -int(row.get("supportCount") or 0),
            -int(row.get("evidenceRefCount") or 0),
            0 if bool(row.get("verdictReferenced")) else 1,
            str(row.get("claimId") or ""),
        )
    )
    outputs: list[dict[str, Any]] = []
    for row in scoped[: max(1, limit)]:
        outputs.append(
            {
                "claimId": row.get("claimId"),
                "text": row.get("text"),
                "phaseFirstNo": row.get("phaseFirstNo"),
                "supportCount": row.get("supportCount"),
                "evidenceRefCount": row.get("evidenceRefCount"),
            }
        )
    return outputs


def build_claim_graph_payload(
    *,
    phase_payloads: list[tuple[int, dict[str, Any]]],
    verdict_evidence_refs: list[dict[str, Any]],
    evidence_ref_resolver: Callable[[int, str, list[int], list[str]], list[str]] | None = None,
) -> dict[str, Any]:
    node_index_by_key: dict[tuple[str, str], int] = {}
    nodes: list[dict[str, Any]] = []
    sequence = 0

    for phase_no, payload in phase_payloads:
        if not isinstance(payload, dict):
            continue
        for side in ("pro", "con"):
            candidates = _collect_side_candidates(payload, side=side)
            if not candidates:
                continue
            message_ids, chunk_ids = _collect_side_evidence_refs(payload, side=side)
            evidence_ref_ids = (
                evidence_ref_resolver(int(phase_no), side, message_ids, chunk_ids)
                if evidence_ref_resolver is not None
                else []
            )
            verdict_referenced = _is_claim_referenced_by_verdict(
                verdict_evidence_refs=verdict_evidence_refs,
                side=side,
                phase_no=phase_no,
                message_ids=message_ids,
                chunk_ids=chunk_ids,
            )
            for text, source in candidates:
                key = _normalize_claim_key(text)
                if not key:
                    continue
                lookup_key = (side, key)
                existing_index = node_index_by_key.get(lookup_key)
                if existing_index is None:
                    sequence += 1
                    node = {
                        "claimId": f"cg-{side}-{sequence}",
                        "side": side,
                        "text": text,
                        "canonicalKey": key,
                        "tokenSet": _tokenize_claim_text(text),
                        "phaseFirstNo": phase_no,
                        "phaseNos": [phase_no],
                        "sources": [source],
                        "supportCount": 1,
                        "evidenceRefs": {
                            "messageIds": list(message_ids),
                            "chunkIds": list(chunk_ids),
                        },
                        "evidenceRefIds": list(evidence_ref_ids),
                        "evidenceRefCount": len(message_ids) + len(chunk_ids),
                        "verdictReferenced": verdict_referenced,
                        "addressed": False,
                        "responseClaimIds": [],
                    }
                    node_index_by_key[lookup_key] = len(nodes)
                    nodes.append(node)
                    continue

                node = nodes[existing_index]
                node["supportCount"] = int(node.get("supportCount") or 0) + 1
                if phase_no not in node["phaseNos"]:
                    node["phaseNos"].append(phase_no)
                if source not in node["sources"]:
                    node["sources"].append(source)
                refs = node.get("evidenceRefs") if isinstance(node.get("evidenceRefs"), dict) else {}
                existing_message_ids = refs.get("messageIds") if isinstance(refs.get("messageIds"), list) else []
                existing_chunk_ids = refs.get("chunkIds") if isinstance(refs.get("chunkIds"), list) else []
                for message_id in message_ids:
                    if message_id not in existing_message_ids:
                        existing_message_ids.append(message_id)
                for chunk_id in chunk_ids:
                    if chunk_id not in existing_chunk_ids:
                        existing_chunk_ids.append(chunk_id)
                refs["messageIds"] = existing_message_ids[:12]
                refs["chunkIds"] = existing_chunk_ids[:12]
                node["evidenceRefs"] = refs
                node["evidenceRefCount"] = len(existing_message_ids) + len(existing_chunk_ids)
                existing_ref_ids = (
                    node.get("evidenceRefIds") if isinstance(node.get("evidenceRefIds"), list) else []
                )
                for evidence_ref_id in evidence_ref_ids:
                    token = str(evidence_ref_id or "").strip()
                    if not token or token in existing_ref_ids:
                        continue
                    existing_ref_ids.append(token)
                node["evidenceRefIds"] = existing_ref_ids[:24]
                if verdict_referenced:
                    node["verdictReferenced"] = True

    pro_nodes = [row for row in nodes if row.get("side") == "pro"]
    con_nodes = [row for row in nodes if row.get("side") == "con"]

    edges: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for pro_node in pro_nodes:
        for con_node in con_nodes:
            pro_claim_id = str(pro_node.get("claimId") or "")
            con_claim_id = str(con_node.get("claimId") or "")
            if not pro_claim_id or not con_claim_id:
                continue
            pair = (pro_claim_id, con_claim_id)
            if pair in seen_pairs:
                continue
            pro_key = str(pro_node.get("canonicalKey") or "")
            con_key = str(con_node.get("canonicalKey") or "")
            overlap = _claim_overlap_score(
                pro_node.get("tokenSet") if isinstance(pro_node.get("tokenSet"), set) else set(),
                con_node.get("tokenSet") if isinstance(con_node.get("tokenSet"), set) else set(),
            )
            if pro_key and con_key and pro_key == con_key:
                basis = "canonical_match"
            elif overlap >= 0.45:
                basis = "token_overlap"
            else:
                continue

            seen_pairs.add(pair)
            edge = {
                "edgeId": f"edge-{len(edges) + 1}",
                "fromClaimId": pro_claim_id,
                "toClaimId": con_claim_id,
                "relation": "rebuttal_conflict",
                "basis": basis,
                "overlapScore": round(overlap, 4),
                "phaseHint": min(
                    int(pro_node.get("phaseFirstNo") or 0),
                    int(con_node.get("phaseFirstNo") or 0),
                ),
            }
            edges.append(edge)
            if len(edges) >= 48:
                break
        if len(edges) >= 48:
            break

    claim_lookup = {str(row.get("claimId") or ""): row for row in nodes}
    for edge in edges:
        from_id = str(edge.get("fromClaimId") or "")
        to_id = str(edge.get("toClaimId") or "")
        from_node = claim_lookup.get(from_id)
        to_node = claim_lookup.get(to_id)
        if from_node is None or to_node is None:
            continue
        from_node["addressed"] = True
        to_node["addressed"] = True
        if to_id not in from_node["responseClaimIds"]:
            from_node["responseClaimIds"].append(to_id)
        if from_id not in to_node["responseClaimIds"]:
            to_node["responseClaimIds"].append(from_id)

    normalized_nodes: list[dict[str, Any]] = []
    for row in nodes[:48]:
        normalized_nodes.append(
            {
                "claimId": row.get("claimId"),
                "side": row.get("side"),
                "text": row.get("text"),
                "phaseFirstNo": int(row.get("phaseFirstNo") or 0),
                "phaseNos": sorted({int(value) for value in row.get("phaseNos") or []}),
                "sources": list(row.get("sources") or []),
                "supportCount": int(row.get("supportCount") or 0),
                "evidenceRefs": row.get("evidenceRefs") if isinstance(row.get("evidenceRefs"), dict) else {"messageIds": [], "chunkIds": []},
                "evidenceRefIds": [
                    str(item).strip()
                    for item in (
                        row.get("evidenceRefIds") if isinstance(row.get("evidenceRefIds"), list) else []
                    )
                    if str(item).strip()
                ][:24],
                "evidenceRefCount": int(row.get("evidenceRefCount") or 0),
                "verdictReferenced": bool(row.get("verdictReferenced")),
                "addressed": bool(row.get("addressed")),
                "responseClaimIds": list(row.get("responseClaimIds") or []),
            }
        )

    unanswered_claims = [
        {
            "claimId": row.get("claimId"),
            "side": row.get("side"),
            "text": row.get("text"),
            "phaseFirstNo": row.get("phaseFirstNo"),
        }
        for row in normalized_nodes
        if not bool(row.get("addressed"))
    ]
    weak_supported_count = sum(1 for row in normalized_nodes if int(row.get("evidenceRefCount") or 0) <= 0)
    verdict_referenced_count = sum(1 for row in normalized_nodes if bool(row.get("verdictReferenced")))
    support_edges: list[dict[str, Any]] = []
    for row in normalized_nodes:
        claim_id = str(row.get("claimId") or "").strip()
        if not claim_id:
            continue
        for index, evidence_ref_id in enumerate(row.get("evidenceRefIds") or [], start=1):
            token = str(evidence_ref_id or "").strip()
            if not token:
                continue
            support_edges.append(
                {
                    "edgeId": f"support-{claim_id}-{index}",
                    "fromClaimId": claim_id,
                    "toEvidenceRefId": token,
                    "relation": "supported_by_evidence",
                }
            )
            if len(support_edges) >= 96:
                break
        if len(support_edges) >= 96:
            break
    rebuttal_edges = [dict(edge) for edge in edges]
    pivotal_turns = [
        {
            "claimId": row.get("claimId"),
            "side": row.get("side"),
            "phaseNo": row.get("phaseFirstNo"),
            "evidenceRefCount": row.get("evidenceRefCount"),
            "verdictReferenced": row.get("verdictReferenced"),
        }
        for row in normalized_nodes
        if bool(row.get("verdictReferenced")) or int(row.get("supportCount") or 0) > 1
    ][:12]
    stats = {
        "totalClaims": len(normalized_nodes),
        "proClaims": sum(1 for row in normalized_nodes if row.get("side") == "pro"),
        "conClaims": sum(1 for row in normalized_nodes if row.get("side") == "con"),
        "conflictEdges": len(edges),
        "supportEdges": len(support_edges),
        "rebuttalEdges": len(rebuttal_edges),
        "unansweredClaims": len(unanswered_claims),
        "weakSupportedClaims": weak_supported_count,
        "verdictReferencedClaims": verdict_referenced_count,
    }
    summary = {
        "coreClaims": {
            "pro": _collect_core_claims(normalized_nodes, side="pro"),
            "con": _collect_core_claims(normalized_nodes, side="con"),
        },
        "conflictPairs": [
            {
                "proClaimId": edge.get("fromClaimId"),
                "conClaimId": edge.get("toClaimId"),
                "basis": edge.get("basis"),
                "overlapScore": edge.get("overlapScore"),
            }
            for edge in edges[:12]
        ],
        "unansweredClaims": unanswered_claims[:12],
        "stats": stats,
    }
    claim_graph = {
        "pipelineVersion": "v1-claim-graph-bootstrap",
        "nodes": normalized_nodes,
        "items": normalized_nodes,
        "edges": edges,
        "claims": normalized_nodes,
        "supportEdges": support_edges,
        "support_edges": support_edges,
        "rebuttalEdges": rebuttal_edges,
        "rebuttal_edges": rebuttal_edges,
        "unansweredClaims": unanswered_claims[:12],
        "unanswered_claims": unanswered_claims[:12],
        "pivotalTurns": pivotal_turns,
        "pivotal_turns": pivotal_turns,
        "unansweredClaimIds": [
            str(item.get("claimId") or "") for item in unanswered_claims if str(item.get("claimId") or "")
        ],
        "stats": stats,
        "agentMeta": {
            "ownerAgent": "claim_graph_agent",
            "decisionAuthority": "non_verdict",
            "officialVerdictAuthority": False,
        },
    }
    return {
        "claimGraph": claim_graph,
        "claimGraphSummary": summary,
    }
