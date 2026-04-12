#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.rag_eval import RagEvalCase, compare_rag_profiles
from app.rag_retriever import RAG_BACKEND_FILE, parse_source_whitelist
from app.runtime_types import RagMessageContext, RagTopicContext, RuntimeRagRequest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run offline RAG quality baseline/profile comparison.",
    )
    parser.add_argument("--dataset-file", required=True, help="Path to eval dataset json file.")
    parser.add_argument(
        "--knowledge-file", required=True, help="Path to knowledge chunks json file."
    )
    parser.add_argument(
        "--profiles",
        default="hybrid_v1,hybrid_recall_v1,hybrid_precision_v1",
        help="Comma separated retrieval profiles to compare.",
    )
    parser.add_argument("--max-snippets", type=int, default=4)
    parser.add_argument("--max-chars-per-snippet", type=int, default=280)
    parser.add_argument("--query-message-limit", type=int, default=80)
    parser.add_argument(
        "--source-whitelist",
        default="",
        help="Optional source url whitelist prefixes.",
    )
    parser.add_argument(
        "--output-file",
        default="",
        help="Optional output json file path.",
    )
    return parser.parse_args()


def _load_cases(path: str) -> list[RagEvalCase]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("dataset root must be a json array")

    cases: list[RagEvalCase] = []
    for idx, row in enumerate(raw):
        if not isinstance(row, dict):
            continue
        request_payload = row.get("request")
        expected = row.get("expectedChunkIds") or row.get("expected_chunk_ids") or []
        if not isinstance(request_payload, dict):
            continue
        if not isinstance(expected, list):
            continue
        request = _build_rag_request(request_payload)
        case_id = str(row.get("caseId") or row.get("case_id") or f"case-{idx + 1}")
        expected_ids = tuple(
            str(chunk_id).strip() for chunk_id in expected if str(chunk_id).strip()
        )
        cases.append(
            RagEvalCase(
                case_id=case_id,
                request=request,
                expected_chunk_ids=expected_ids,
            )
        )
    return cases


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _build_rag_request(payload: dict[str, Any]) -> RuntimeRagRequest:
    topic_payload = payload.get("topic") if isinstance(payload.get("topic"), dict) else {}
    topic = RagTopicContext(
        title=str(topic_payload.get("title") or "unknown-topic"),
        category=str(topic_payload.get("category") or "default"),
        description=str(topic_payload.get("description") or ""),
        stance_pro=str(topic_payload.get("stance_pro") or topic_payload.get("stancePro") or "pro"),
        stance_con=str(topic_payload.get("stance_con") or topic_payload.get("stanceCon") or "con"),
        context_seed=topic_payload.get("context_seed") or topic_payload.get("contextSeed"),
    )

    messages_payload = payload.get("messages") if isinstance(payload.get("messages"), list) else []
    messages: list[RagMessageContext] = []
    for row in messages_payload:
        if not isinstance(row, dict):
            continue
        message_id = int(row.get("message_id") or row.get("messageId") or 0)
        if message_id <= 0:
            continue
        messages.append(
            RagMessageContext(
                message_id=message_id,
                side=str(row.get("side") or "pro"),
                content=str(row.get("content") or ""),
                created_at=_parse_datetime(row.get("created_at") or row.get("createdAt")),
                speaker_tag=row.get("speaker_tag") or row.get("speakerTag"),
                user_id=row.get("user_id") or row.get("userId"),
            )
        )
    retrieval_profile = str(
        payload.get("retrieval_profile") or payload.get("retrievalProfile") or "hybrid_v1"
    )
    return RuntimeRagRequest(
        topic=topic,
        messages=messages,
        retrieval_profile=retrieval_profile,
    )


def main() -> int:
    args = _parse_args()
    cases = _load_cases(args.dataset_file)
    if not cases:
        raise ValueError("no valid eval cases found")

    profiles = [item.strip() for item in args.profiles.split(",") if item.strip()]
    if not profiles:
        raise ValueError("profiles cannot be empty")

    base_kwargs: dict[str, Any] = {
        "enabled": True,
        "knowledge_file": args.knowledge_file,
        "max_snippets": max(1, args.max_snippets),
        "max_chars_per_snippet": max(120, args.max_chars_per_snippet),
        "query_message_limit": max(0, args.query_message_limit),
        "allowed_source_prefixes": parse_source_whitelist(args.source_whitelist),
        "backend": RAG_BACKEND_FILE,
    }
    payload = compare_rag_profiles(
        cases=cases,
        profile_names=profiles,
        base_retrieve_kwargs=base_kwargs,
    )
    out = json.dumps(payload, ensure_ascii=False, indent=2)
    print(out)

    if args.output_file.strip():
        Path(args.output_file).write_text(out + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
