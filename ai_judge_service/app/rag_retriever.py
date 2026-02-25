from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import JudgeDispatchRequest

TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+")


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    title: str
    source_url: str
    content: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class RetrievedContext:
    chunk_id: str
    title: str
    source_url: str
    content: str
    score: float

    def to_payload_source(self) -> dict[str, Any]:
        return {
            "chunkId": self.chunk_id,
            "title": self.title,
            "sourceUrl": self.source_url,
            "score": round(self.score, 4),
        }


def _safe_text(value: Any, *, max_len: int = 4000) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text[:max_len]


def _tokenize(text: str) -> set[str]:
    out: set[str] = set()
    for token in TOKEN_RE.findall((text or "").lower()):
        token = token.strip()
        if len(token) < 2:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            out.add(token)
            # 兼容中文短语匹配，拆成 2-gram 提升召回率
            for idx in range(0, len(token) - 1):
                out.add(token[idx : idx + 2])
            continue
        out.add(token)
    return out


def _load_knowledge_file(path: str) -> list[KnowledgeChunk]:
    path = path.strip()
    if not path:
        return []
    file = Path(path)
    if not file.exists() or not file.is_file():
        return []

    try:
        payload = json.loads(file.read_text(encoding="utf-8"))
    except Exception:
        return []

    if not isinstance(payload, list):
        return []

    rows: list[KnowledgeChunk] = []
    for idx, row in enumerate(payload):
        if not isinstance(row, dict):
            continue
        chunk_id = _safe_text(
            row.get("chunk_id") or row.get("chunkId") or f"chunk-{idx + 1}",
            max_len=128,
        )
        title = _safe_text(row.get("title"), max_len=300) or chunk_id
        source_url = _safe_text(
            row.get("source_url") or row.get("sourceUrl"),
            max_len=1000,
        )
        content = _safe_text(row.get("content"), max_len=8000)
        if not content:
            continue
        raw_tags = row.get("tags")
        tags: tuple[str, ...]
        if isinstance(raw_tags, list):
            tags = tuple(
                v.strip().lower()
                for v in raw_tags
                if isinstance(v, str) and v.strip()
            )
        else:
            tags = tuple()
        rows.append(
            KnowledgeChunk(
                chunk_id=chunk_id,
                title=title,
                source_url=source_url,
                content=content,
                tags=tags,
            )
        )
    return rows


def _build_query_tokens(request: "JudgeDispatchRequest", query_message_limit: int) -> set[str]:
    topic = request.topic
    topic_text = " ".join(
        [
            topic.title,
            topic.category,
            topic.description,
            topic.stance_pro,
            topic.stance_con,
            topic.context_seed or "",
        ]
    )
    msg_count = max(0, query_message_limit)
    selected_messages = request.messages if msg_count == 0 else request.messages[-msg_count:]
    message_text = " ".join(msg.content for msg in selected_messages)
    return _tokenize(f"{topic_text}\n{message_text}")


def _score_chunk(chunk: KnowledgeChunk, query_tokens: set[str]) -> float:
    if not query_tokens:
        return 0.0
    chunk_tokens = _tokenize(
        " ".join([chunk.title, chunk.content, " ".join(chunk.tags)])
    )
    if not chunk_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(chunk_tokens))
    if overlap == 0:
        return 0.0

    coverage = overlap / max(1, len(query_tokens))
    density = overlap / max(1, len(chunk_tokens))
    return coverage * 0.75 + density * 0.25


def retrieve_contexts(
    request: "JudgeDispatchRequest",
    *,
    enabled: bool,
    knowledge_file: str,
    max_snippets: int,
    max_chars_per_snippet: int,
    query_message_limit: int,
) -> list[RetrievedContext]:
    if not enabled:
        return []

    limit = max(0, max_snippets)
    if limit == 0:
        return []

    out: list[RetrievedContext] = []
    seen_chunk_ids: set[str] = set()

    context_seed = _safe_text(request.topic.context_seed, max_len=max_chars_per_snippet)
    if context_seed:
        out.append(
            RetrievedContext(
                chunk_id="topic-context-seed",
                title="topic_context_seed",
                source_url="request.topic.context_seed",
                content=context_seed,
                score=1.0,
            )
        )
        seen_chunk_ids.add("topic-context-seed")
        if len(out) >= limit:
            return out

    chunks = _load_knowledge_file(knowledge_file)
    query_tokens = _build_query_tokens(request, query_message_limit)
    ranked: list[RetrievedContext] = []
    for chunk in chunks:
        score = _score_chunk(chunk, query_tokens)
        if score <= 0:
            continue
        ranked.append(
            RetrievedContext(
                chunk_id=chunk.chunk_id,
                title=chunk.title,
                source_url=chunk.source_url,
                content=_safe_text(chunk.content, max_len=max_chars_per_snippet),
                score=score,
            )
        )

    ranked.sort(key=lambda item: (-item.score, item.chunk_id))
    for item in ranked:
        if item.chunk_id in seen_chunk_ids:
            continue
        out.append(item)
        seen_chunk_ids.add(item.chunk_id)
        if len(out) >= limit:
            break

    return out


def summarize_retrieved_contexts(
    retrieved_contexts: list[RetrievedContext],
) -> list[dict[str, Any]]:
    return [item.to_payload_source() for item in retrieved_contexts]
