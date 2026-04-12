from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from .lexical_retriever import (
    DEFAULT_BM25_CACHE_DIR,
    DEFAULT_LEXICAL_ENGINE,
    LEXICAL_TOKENIZER_PROFILE,
    LexicalDocument,
    LexicalSearchRequest,
    search_lexical,
)
from .reranker_engine import (
    DEFAULT_BGE_MODEL,
    RerankCandidate,
    RerankRequest,
    rerank_with_fallback,
)
from .token_budget import count_tokens, truncate_text_to_tokens

if TYPE_CHECKING:
    from .runtime_types import RuntimeRagRequest

TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+")
RAG_BACKEND_FILE = "file"
RAG_BACKEND_MILVUS = "milvus"


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


@dataclass(frozen=True)
class RagMilvusConfig:
    uri: str
    collection: str
    token: str = ""
    db_name: str = ""
    vector_field: str = "embedding"
    content_field: str = "content"
    title_field: str = "title"
    source_url_field: str = "source_url"
    chunk_id_field: str = "chunk_id"
    tags_field: str = "tags"
    metric_type: str = "COSINE"
    search_limit: int = 20


def _safe_text(value: Any, *, max_len: int = 4000) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text[:max_len]


def _truncate_snippet_text(
    *,
    text: str,
    max_chars_per_snippet: int,
    snippet_max_tokens: int,
    tokenizer_model: str,
    tokenizer_fallback_encoding: str,
) -> str:
    base = _safe_text(text, max_len=max_chars_per_snippet)
    token_budget = max(0, int(snippet_max_tokens))
    if token_budget <= 0 or not base:
        return base
    result = truncate_text_to_tokens(
        tokenizer_model,
        base,
        token_budget,
        fallback_encoding=tokenizer_fallback_encoding,
    )
    return result.text


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _clamp_int(value: int, *, minimum: int, maximum: int) -> int:
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def _clamp_weight(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


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
            tags = tuple(v.strip().lower() for v in raw_tags if isinstance(v, str) and v.strip())
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


def _build_query_text_raw(request: "RuntimeRagRequest", query_message_limit: int) -> str:
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
    return f"{topic_text}\n{message_text}"


def _build_query_text(
    request: "RuntimeRagRequest",
    query_message_limit: int,
    *,
    query_max_tokens: int,
    tokenizer_model: str,
    tokenizer_fallback_encoding: str,
) -> str:
    query_text = _build_query_text_raw(request, query_message_limit)
    token_budget = max(0, int(query_max_tokens))
    if token_budget <= 0:
        return query_text
    truncated = truncate_text_to_tokens(
        tokenizer_model,
        query_text,
        token_budget,
        fallback_encoding=tokenizer_fallback_encoding,
    )
    return truncated.text


def _build_query_tokens(
    request: "RuntimeRagRequest",
    query_message_limit: int,
    *,
    query_max_tokens: int,
    tokenizer_model: str,
    tokenizer_fallback_encoding: str,
) -> set[str]:
    return _tokenize(
        _build_query_text(
            request,
            query_message_limit,
            query_max_tokens=query_max_tokens,
            tokenizer_model=tokenizer_model,
            tokenizer_fallback_encoding=tokenizer_fallback_encoding,
        )
    )


def _score_chunk(chunk: KnowledgeChunk, query_tokens: set[str]) -> float:
    if not query_tokens:
        return 0.0
    chunk_tokens = _tokenize(" ".join([chunk.title, chunk.content, " ".join(chunk.tags)]))
    if not chunk_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(chunk_tokens))
    if overlap == 0:
        return 0.0

    coverage = overlap / max(1, len(query_tokens))
    density = overlap / max(1, len(chunk_tokens))
    return coverage * 0.75 + density * 0.25


def _rrf_fuse(
    candidates: list[list[RetrievedContext]],
    *,
    rrf_k: int = 60,
) -> list[RetrievedContext]:
    score_map: dict[str, float] = {}
    context_map: dict[str, RetrievedContext] = {}
    for rows in candidates:
        for rank, item in enumerate(rows):
            score_map[item.chunk_id] = score_map.get(item.chunk_id, 0.0) + (
                1.0 / (rrf_k + rank + 1)
            )
            previous = context_map.get(item.chunk_id)
            if previous is None or item.score > previous.score:
                context_map[item.chunk_id] = item

    fused: list[RetrievedContext] = []
    for chunk_id, score in score_map.items():
        item = context_map.get(chunk_id)
        if item is None:
            continue
        fused.append(
            RetrievedContext(
                chunk_id=item.chunk_id,
                title=item.title,
                source_url=item.source_url,
                content=item.content,
                score=score,
            )
        )
    fused.sort(key=lambda row: (-row.score, row.chunk_id))
    return fused


def _contexts_to_candidates(
    contexts: list[RetrievedContext],
) -> list[RerankCandidate]:
    out: list[RerankCandidate] = []
    for item in contexts:
        out.append(
            RerankCandidate(
                chunk_id=item.chunk_id,
                title=item.title,
                content=item.content,
                score=float(item.score),
                source_url=item.source_url,
            )
        )
    return out


def _candidates_to_contexts(
    candidates: list[RerankCandidate],
) -> list[RetrievedContext]:
    out: list[RetrievedContext] = []
    for item in candidates:
        out.append(
            RetrievedContext(
                chunk_id=item.chunk_id,
                title=item.title,
                source_url=item.source_url,
                content=item.content,
                score=float(item.score),
            )
        )
    return out


def parse_source_whitelist(raw: str | None) -> tuple[str, ...]:
    text = (raw or "").strip()
    if not text:
        return tuple()

    parts = re.split(r"[,\n;]+", text)
    normalized: list[str] = []
    seen: set[str] = set()
    for part in parts:
        item = part.strip().rstrip("/")
        if not item:
            continue
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(item)
    return tuple(normalized)


def parse_rag_backend(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if value == RAG_BACKEND_MILVUS:
        return RAG_BACKEND_MILVUS
    return RAG_BACKEND_FILE


def _source_allowed(source_url: str, whitelist_prefixes: tuple[str, ...]) -> bool:
    if not whitelist_prefixes:
        return True
    source = (source_url or "").strip().lower()
    if not source:
        return False
    for prefix in whitelist_prefixes:
        prefix_norm = prefix.strip().lower().rstrip("/")
        if not prefix_norm:
            continue
        if source == prefix_norm or source.startswith(prefix_norm + "/"):
            return True
    return False


def _score_rank(metric_type: str, distance: float, rank: int) -> float:
    if rank < 0:
        rank = 0
    metric = metric_type.strip().upper()
    if metric in {"L2", "EUCLIDEAN"}:
        return 1.0 / (1.0 + max(0.0, distance))
    return max(0.0, distance) + (1.0 / (rank + 1000.0))


def _embed_query_with_openai(
    *,
    query_text: str,
    openai_api_key: str,
    openai_base_url: str,
    openai_embedding_model: str,
    openai_timeout_secs: float,
    embed_input_max_tokens: int,
    tokenizer_model: str,
    tokenizer_fallback_encoding: str,
) -> list[float]:
    if not query_text.strip() or not openai_api_key.strip():
        return []

    token_budget = max(0, int(embed_input_max_tokens))
    prepared_query = query_text
    if token_budget > 0:
        prepared_query = truncate_text_to_tokens(
            tokenizer_model,
            query_text,
            token_budget,
            fallback_encoding=tokenizer_fallback_encoding,
        ).text

    url = openai_base_url.rstrip("/") + "/embeddings"
    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": openai_embedding_model,
        "input": prepared_query[:8000],
    }
    try:
        with httpx.Client(timeout=max(1.0, openai_timeout_secs)) as client:
            resp = client.post(url, headers=headers, json=body)
        if resp.status_code // 100 != 2:
            return []
        payload = resp.json()
        items = payload.get("data")
        if not isinstance(items, list) or not items:
            return []
        embedding = items[0].get("embedding")
        if not isinstance(embedding, list):
            return []
        out = [_safe_float(value) for value in embedding]
        return out if out else []
    except Exception:
        return []


def _fetch_milvus_candidates(
    *,
    query_embedding: list[float],
    cfg: RagMilvusConfig,
) -> list[dict[str, Any]]:
    if not query_embedding:
        return []
    try:
        from pymilvus import MilvusClient  # type: ignore
    except Exception:
        return []

    try:
        client = MilvusClient(
            uri=cfg.uri,
            token=cfg.token or None,
            db_name=cfg.db_name or None,
        )
        raw = client.search(
            collection_name=cfg.collection,
            data=[query_embedding],
            anns_field=cfg.vector_field,
            limit=max(1, cfg.search_limit),
            search_params={"metric_type": cfg.metric_type},
            output_fields=[
                cfg.chunk_id_field,
                cfg.title_field,
                cfg.source_url_field,
                cfg.content_field,
                cfg.tags_field,
            ],
        )
    except Exception:
        return []

    if not isinstance(raw, list) or not raw:
        return []
    first = raw[0]
    if not isinstance(first, list):
        return []
    return [row for row in first if isinstance(row, dict)]


def _context_from_milvus_row(
    row: dict[str, Any],
    *,
    cfg: RagMilvusConfig,
    rank: int,
    max_chars_per_snippet: int,
    snippet_max_tokens: int,
    tokenizer_model: str,
    tokenizer_fallback_encoding: str,
) -> RetrievedContext | None:
    entity = row.get("entity")
    fields = entity if isinstance(entity, dict) else row
    chunk_id = _safe_text(
        fields.get(cfg.chunk_id_field) or row.get("id") or f"milvus-{rank + 1}",
        max_len=128,
    )
    title = _safe_text(fields.get(cfg.title_field), max_len=300) or chunk_id
    source_url = _safe_text(fields.get(cfg.source_url_field), max_len=1000)
    content = _truncate_snippet_text(
        text=_safe_text(fields.get(cfg.content_field), max_len=max_chars_per_snippet),
        max_chars_per_snippet=max_chars_per_snippet,
        snippet_max_tokens=snippet_max_tokens,
        tokenizer_model=tokenizer_model,
        tokenizer_fallback_encoding=tokenizer_fallback_encoding,
    )
    if not content:
        return None
    distance = _safe_float(row.get("distance"), default=0.0)
    score = _score_rank(cfg.metric_type, distance, rank)
    return RetrievedContext(
        chunk_id=chunk_id,
        title=title,
        source_url=source_url,
        content=content,
        score=score,
    )


def _chunk_to_lexical_document(chunk: KnowledgeChunk) -> LexicalDocument:
    return LexicalDocument(
        chunk_id=chunk.chunk_id,
        title=chunk.title,
        source_url=chunk.source_url,
        content=chunk.content,
        tags=chunk.tags,
    )


def _retrieve_contexts_from_file(
    request: "RuntimeRagRequest",
    *,
    query_text: str,
    knowledge_file: str,
    max_snippets: int,
    max_chars_per_snippet: int,
    snippet_max_tokens: int,
    tokenizer_model: str,
    tokenizer_fallback_encoding: str,
    allowed_source_prefixes: tuple[str, ...] = (),
    lexical_engine: str = DEFAULT_LEXICAL_ENGINE,
    bm25_cache_dir: str = DEFAULT_BM25_CACHE_DIR,
    bm25_use_disk_cache: bool = True,
    bm25_fallback_to_simple: bool = True,
    diagnostics: dict[str, Any] | None = None,
) -> list[RetrievedContext]:
    diagnostics_payload: dict[str, Any] = diagnostics if isinstance(diagnostics, dict) else {}
    out: list[RetrievedContext] = []
    seen_chunk_ids: set[str] = set()

    context_seed = _truncate_snippet_text(
        text=_safe_text(request.topic.context_seed, max_len=max_chars_per_snippet),
        max_chars_per_snippet=max_chars_per_snippet,
        snippet_max_tokens=snippet_max_tokens,
        tokenizer_model=tokenizer_model,
        tokenizer_fallback_encoding=tokenizer_fallback_encoding,
    )
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
        if len(out) >= max_snippets:
            diagnostics_payload.update(
                {
                    "lexicalEngineConfigured": lexical_engine,
                    "lexicalEngineEffective": "disabled",
                    "lexicalIndexCacheHit": False,
                    "lexicalIndexBuildMs": 0.0,
                    "lexicalIndexLoadMs": 0.0,
                    "lexicalFallbackReason": None,
                    "lexicalDocCount": 0,
                    "lexicalTokenizerProfile": LEXICAL_TOKENIZER_PROFILE,
                }
            )
            return out

    chunks = _load_knowledge_file(knowledge_file)
    documents = [
        _chunk_to_lexical_document(chunk)
        for chunk in chunks
        if _source_allowed(chunk.source_url, allowed_source_prefixes)
    ]
    lexical_result = search_lexical(
        LexicalSearchRequest(
            knowledge_file=knowledge_file,
            documents=documents,
            query_text=query_text,
            top_k=max(0, max_snippets - len(out)),
            configured_engine=lexical_engine,
            bm25_cache_dir=bm25_cache_dir,
            bm25_use_disk_cache=bm25_use_disk_cache,
            fallback_to_simple=bm25_fallback_to_simple,
        )
    )
    document_map = {document.chunk_id: document for document in documents}
    diagnostics_payload.update(
        {
            "lexicalEngineConfigured": lexical_result.configured_engine,
            "lexicalEngineEffective": lexical_result.effective_engine,
            "lexicalIndexCacheHit": lexical_result.index_cache_hit,
            "lexicalIndexBuildMs": round(float(lexical_result.index_build_ms), 2),
            "lexicalIndexLoadMs": round(float(lexical_result.index_load_ms), 2),
            "lexicalFallbackReason": lexical_result.fallback_reason,
            "lexicalDocCount": lexical_result.doc_count,
            "lexicalTokenizerProfile": lexical_result.tokenizer_profile,
        }
    )
    if lexical_result.error_code:
        diagnostics_payload.setdefault("errorCode", lexical_result.error_code)

    ranked: list[RetrievedContext] = []
    for hit in lexical_result.hits:
        document = document_map.get(hit.chunk_id)
        if document is None:
            continue
        ranked.append(
            RetrievedContext(
                chunk_id=document.chunk_id,
                title=document.title,
                source_url=document.source_url,
                content=_truncate_snippet_text(
                    text=document.content,
                    max_chars_per_snippet=max_chars_per_snippet,
                    snippet_max_tokens=snippet_max_tokens,
                    tokenizer_model=tokenizer_model,
                    tokenizer_fallback_encoding=tokenizer_fallback_encoding,
                ),
                score=float(hit.score),
            )
        )

    for item in ranked:
        if item.chunk_id in seen_chunk_ids:
            continue
        out.append(item)
        seen_chunk_ids.add(item.chunk_id)
        if len(out) >= max_snippets:
            break
    return out


def _retrieve_contexts_from_milvus(
    request: "RuntimeRagRequest",
    *,
    query_text: str,
    max_snippets: int,
    max_chars_per_snippet: int,
    snippet_max_tokens: int,
    allowed_source_prefixes: tuple[str, ...],
    milvus_config: RagMilvusConfig,
    openai_api_key: str,
    openai_base_url: str,
    openai_embedding_model: str,
    openai_timeout_secs: float,
    embed_input_max_tokens: int,
    tokenizer_model: str,
    tokenizer_fallback_encoding: str,
) -> list[RetrievedContext]:
    out: list[RetrievedContext] = []
    seen_chunk_ids: set[str] = set()

    context_seed = _truncate_snippet_text(
        text=_safe_text(request.topic.context_seed, max_len=max_chars_per_snippet),
        max_chars_per_snippet=max_chars_per_snippet,
        snippet_max_tokens=snippet_max_tokens,
        tokenizer_model=tokenizer_model,
        tokenizer_fallback_encoding=tokenizer_fallback_encoding,
    )
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
        if len(out) >= max_snippets:
            return out

    embedding = _embed_query_with_openai(
        query_text=query_text,
        openai_api_key=openai_api_key,
        openai_base_url=openai_base_url,
        openai_embedding_model=openai_embedding_model,
        openai_timeout_secs=openai_timeout_secs,
        embed_input_max_tokens=embed_input_max_tokens,
        tokenizer_model=tokenizer_model,
        tokenizer_fallback_encoding=tokenizer_fallback_encoding,
    )
    rows = _fetch_milvus_candidates(query_embedding=embedding, cfg=milvus_config)
    for rank, row in enumerate(rows):
        item = _context_from_milvus_row(
            row,
            cfg=milvus_config,
            rank=rank,
            max_chars_per_snippet=max_chars_per_snippet,
            snippet_max_tokens=snippet_max_tokens,
            tokenizer_model=tokenizer_model,
            tokenizer_fallback_encoding=tokenizer_fallback_encoding,
        )
        if item is None:
            continue
        if not _source_allowed(item.source_url, allowed_source_prefixes):
            continue
        if item.chunk_id in seen_chunk_ids:
            continue
        out.append(item)
        seen_chunk_ids.add(item.chunk_id)
        if len(out) >= max_snippets:
            break

    return out


def _apply_rerank(
    *,
    query_text: str,
    contexts: list[RetrievedContext],
    limit: int,
    rerank_engine: str,
    rerank_model: str,
    rerank_batch_size: int,
    rerank_candidate_cap: int,
    rerank_timeout_ms: int,
    rerank_device: str,
    query_weight: float,
    base_weight: float,
) -> tuple[list[RetrievedContext], dict[str, Any], str | None]:
    request = RerankRequest(
        query_text=query_text,
        candidates=_contexts_to_candidates(contexts),
        top_n=max(0, int(limit)),
        configured_engine=rerank_engine,
        model_name=rerank_model.strip() or DEFAULT_BGE_MODEL,
        batch_size=rerank_batch_size,
        candidate_cap=rerank_candidate_cap,
        timeout_ms=rerank_timeout_ms,
        device=rerank_device,
        query_weight=query_weight,
        base_weight=base_weight,
    )
    result = rerank_with_fallback(request)
    diagnostics = {
        "rerankEngineConfigured": result.configured_engine,
        "rerankEngineEffective": result.effective_engine,
        "rerankModel": result.model_name,
        "rerankLatencyMs": round(float(result.latency_ms), 2),
        "rerankFallbackReason": result.fallback_reason,
        "candidateBeforeRerank": int(result.candidate_before),
        "candidateAfterRerank": int(result.candidate_after),
    }
    return _candidates_to_contexts(result.candidates), diagnostics, result.error_code


def retrieve_contexts(
    request: "RuntimeRagRequest",
    *,
    enabled: bool,
    knowledge_file: str,
    max_snippets: int,
    max_chars_per_snippet: int,
    query_message_limit: int,
    query_max_tokens: int = 1600,
    snippet_max_tokens: int = 180,
    tokenizer_model: str = "gpt-4.1-mini",
    tokenizer_fallback_encoding: str = "o200k_base",
    embed_input_max_tokens: int = 2000,
    allowed_source_prefixes: tuple[str, ...] = (),
    backend: str = RAG_BACKEND_FILE,
    milvus_config: RagMilvusConfig | None = None,
    openai_api_key: str = "",
    openai_base_url: str = "https://api.openai.com/v1",
    openai_embedding_model: str = "text-embedding-3-small",
    openai_timeout_secs: float = 8.0,
    hybrid_enabled: bool = False,
    rerank_enabled: bool = False,
    hybrid_rrf_k: int = 60,
    hybrid_vector_limit_multiplier: int = 1,
    hybrid_lexical_limit_multiplier: int = 2,
    lexical_engine: str = DEFAULT_LEXICAL_ENGINE,
    bm25_cache_dir: str = DEFAULT_BM25_CACHE_DIR,
    bm25_use_disk_cache: bool = True,
    bm25_fallback_to_simple: bool = True,
    rerank_query_weight: float = 0.7,
    rerank_base_weight: float = 0.3,
    rerank_engine: str = "bge",
    rerank_model: str = DEFAULT_BGE_MODEL,
    rerank_batch_size: int = 16,
    rerank_candidate_cap: int = 50,
    rerank_timeout_ms: int = 12000,
    rerank_device: str = "cpu",
    diagnostics: dict[str, Any] | None = None,
) -> list[RetrievedContext]:
    diagnostics_payload: dict[str, Any] = diagnostics if isinstance(diagnostics, dict) else {}
    rrf_k = _clamp_int(_safe_int(hybrid_rrf_k, default=60), minimum=1, maximum=500)
    vector_limit_multiplier = _clamp_int(
        _safe_int(hybrid_vector_limit_multiplier, default=1),
        minimum=1,
        maximum=8,
    )
    lexical_limit_multiplier = _clamp_int(
        _safe_int(hybrid_lexical_limit_multiplier, default=2),
        minimum=1,
        maximum=8,
    )
    rerank_query_w = _clamp_weight(float(rerank_query_weight))
    rerank_base_w = _clamp_weight(float(rerank_base_weight))
    if rerank_query_w == 0.0 and rerank_base_w == 0.0:
        rerank_query_w = 0.7
        rerank_base_w = 0.3
    diagnostics_tuning = {
        "rrfK": rrf_k,
        "vectorLimitMultiplier": vector_limit_multiplier,
        "lexicalLimitMultiplier": lexical_limit_multiplier,
        "rerankQueryWeight": round(rerank_query_w, 4),
        "rerankBaseWeight": round(rerank_base_w, 4),
    }
    if not enabled:
        diagnostics_payload.update(
            {
                "strategy": "disabled",
                "vectorCandidateCount": 0,
                "lexicalCandidateCount": 0,
                "fusedCandidateCount": 0,
                "rerankCandidateCount": 0,
                "finalCount": 0,
                "hybridApplied": False,
                "rerankApplied": False,
                "tuning": diagnostics_tuning,
                "lexicalEngineConfigured": lexical_engine,
                "lexicalEngineEffective": "disabled",
                "lexicalIndexCacheHit": False,
                "lexicalIndexBuildMs": 0.0,
                "lexicalIndexLoadMs": 0.0,
                "lexicalFallbackReason": None,
                "lexicalDocCount": 0,
                "lexicalTokenizerProfile": LEXICAL_TOKENIZER_PROFILE,
                "rerankEngineConfigured": rerank_engine,
                "rerankEngineEffective": "disabled",
                "rerankModel": rerank_model,
                "rerankLatencyMs": 0.0,
                "rerankFallbackReason": None,
                "candidateBeforeRerank": 0,
                "candidateAfterRerank": 0,
            }
        )
        return []

    limit = max(0, max_snippets)
    if limit == 0:
        diagnostics_payload.update(
            {
                "strategy": "limit_zero",
                "vectorCandidateCount": 0,
                "lexicalCandidateCount": 0,
                "fusedCandidateCount": 0,
                "rerankCandidateCount": 0,
                "finalCount": 0,
                "hybridApplied": False,
                "rerankApplied": False,
                "tuning": diagnostics_tuning,
                "lexicalEngineConfigured": lexical_engine,
                "lexicalEngineEffective": "disabled",
                "lexicalIndexCacheHit": False,
                "lexicalIndexBuildMs": 0.0,
                "lexicalIndexLoadMs": 0.0,
                "lexicalFallbackReason": None,
                "lexicalDocCount": 0,
                "lexicalTokenizerProfile": LEXICAL_TOKENIZER_PROFILE,
                "rerankEngineConfigured": rerank_engine,
                "rerankEngineEffective": "disabled",
                "rerankModel": rerank_model,
                "rerankLatencyMs": 0.0,
                "rerankFallbackReason": None,
                "candidateBeforeRerank": 0,
                "candidateAfterRerank": 0,
            }
        )
        return []

    selected_backend = parse_rag_backend(backend)
    raw_query_text = _build_query_text_raw(request, query_message_limit)
    query_text = _build_query_text(
        request,
        query_message_limit,
        query_max_tokens=query_max_tokens,
        tokenizer_model=tokenizer_model,
        tokenizer_fallback_encoding=tokenizer_fallback_encoding,
    )
    raw_query_tokens = count_tokens(
        tokenizer_model,
        raw_query_text,
        fallback_encoding=tokenizer_fallback_encoding,
    )
    final_query_tokens = count_tokens(
        tokenizer_model,
        query_text,
        fallback_encoding=tokenizer_fallback_encoding,
    )
    query_clipped = final_query_tokens < raw_query_tokens
    diagnostics_payload["queryTokenClip"] = {
        "enabled": int(query_max_tokens) > 0,
        "budget": max(0, int(query_max_tokens)),
        "rawTokens": raw_query_tokens,
        "finalTokens": final_query_tokens,
        "clipped": query_clipped,
    }
    if selected_backend == RAG_BACKEND_MILVUS and milvus_config is not None:
        vector_limit = max(limit, milvus_config.search_limit * vector_limit_multiplier)
        lexical_diagnostics: dict[str, Any] = {}
        vector_contexts = _retrieve_contexts_from_milvus(
            request,
            query_text=query_text,
            max_snippets=vector_limit,
            max_chars_per_snippet=max_chars_per_snippet,
            snippet_max_tokens=snippet_max_tokens,
            allowed_source_prefixes=allowed_source_prefixes,
            milvus_config=milvus_config,
            openai_api_key=openai_api_key,
            openai_base_url=openai_base_url,
            openai_embedding_model=openai_embedding_model,
            openai_timeout_secs=openai_timeout_secs,
            embed_input_max_tokens=embed_input_max_tokens,
            tokenizer_model=tokenizer_model,
            tokenizer_fallback_encoding=tokenizer_fallback_encoding,
        )
        lexical_contexts: list[RetrievedContext] = []
        if hybrid_enabled:
            lexical_contexts = _retrieve_contexts_from_file(
                request,
                query_text=query_text,
                knowledge_file=knowledge_file,
                max_snippets=max(limit * lexical_limit_multiplier, limit),
                max_chars_per_snippet=max_chars_per_snippet,
                snippet_max_tokens=snippet_max_tokens,
                tokenizer_model=tokenizer_model,
                tokenizer_fallback_encoding=tokenizer_fallback_encoding,
                allowed_source_prefixes=allowed_source_prefixes,
                lexical_engine=lexical_engine,
                bm25_cache_dir=bm25_cache_dir,
                bm25_use_disk_cache=bm25_use_disk_cache,
                bm25_fallback_to_simple=bm25_fallback_to_simple,
                diagnostics=lexical_diagnostics,
            )
            if lexical_diagnostics.get("errorCode"):
                diagnostics_payload.setdefault("errorCode", lexical_diagnostics["errorCode"])
        fused_contexts = (
            _rrf_fuse([vector_contexts, lexical_contexts], rrf_k=rrf_k)
            if hybrid_enabled and lexical_contexts
            else vector_contexts
        )
        rerank_candidates = fused_contexts
        rerank_meta: dict[str, Any] = {
            "rerankEngineConfigured": rerank_engine,
            "rerankEngineEffective": "disabled",
            "rerankModel": rerank_model,
            "rerankLatencyMs": 0.0,
            "rerankFallbackReason": None,
            "candidateBeforeRerank": len(fused_contexts),
            "candidateAfterRerank": min(limit, len(fused_contexts)),
        }
        rerank_error_code: str | None = None
        final_contexts = fused_contexts[:limit]
        if rerank_enabled:
            final_contexts, rerank_meta, rerank_error_code = _apply_rerank(
                query_text=query_text,
                contexts=fused_contexts,
                limit=limit,
                rerank_engine=rerank_engine,
                rerank_model=rerank_model,
                rerank_batch_size=rerank_batch_size,
                rerank_candidate_cap=rerank_candidate_cap,
                rerank_timeout_ms=rerank_timeout_ms,
                rerank_device=rerank_device,
                query_weight=rerank_query_w,
                base_weight=rerank_base_w,
            )
        if rerank_error_code:
            diagnostics_payload.setdefault("errorCode", rerank_error_code)
        diagnostics_payload.update(
            {
                "strategy": "milvus_hybrid" if hybrid_enabled else "milvus_vector_only",
                "vectorCandidateCount": len(vector_contexts),
                "lexicalCandidateCount": len(lexical_contexts),
                "fusedCandidateCount": len(fused_contexts),
                "rerankCandidateCount": len(rerank_candidates),
                "finalCount": len(final_contexts),
                "hybridApplied": hybrid_enabled and bool(lexical_contexts),
                "rerankApplied": rerank_enabled,
                "tuning": diagnostics_tuning,
                "lexicalEngineConfigured": lexical_diagnostics.get(
                    "lexicalEngineConfigured",
                    lexical_engine,
                )
                if hybrid_enabled
                else lexical_engine,
                "lexicalEngineEffective": lexical_diagnostics.get(
                    "lexicalEngineEffective",
                    "disabled",
                )
                if hybrid_enabled
                else "disabled",
                "lexicalIndexCacheHit": bool(lexical_diagnostics.get("lexicalIndexCacheHit", False))
                if hybrid_enabled
                else False,
                "lexicalIndexBuildMs": float(lexical_diagnostics.get("lexicalIndexBuildMs", 0.0))
                if hybrid_enabled
                else 0.0,
                "lexicalIndexLoadMs": float(lexical_diagnostics.get("lexicalIndexLoadMs", 0.0))
                if hybrid_enabled
                else 0.0,
                "lexicalFallbackReason": lexical_diagnostics.get("lexicalFallbackReason")
                if hybrid_enabled
                else None,
                "lexicalDocCount": int(lexical_diagnostics.get("lexicalDocCount", 0))
                if hybrid_enabled
                else 0,
                "lexicalTokenizerProfile": lexical_diagnostics.get(
                    "lexicalTokenizerProfile",
                    LEXICAL_TOKENIZER_PROFILE,
                )
                if hybrid_enabled
                else LEXICAL_TOKENIZER_PROFILE,
                **rerank_meta,
            }
        )
        return final_contexts

    lexical_diagnostics = {}
    lexical_limit = max(limit * lexical_limit_multiplier, limit) if rerank_enabled else limit
    lexical_contexts = _retrieve_contexts_from_file(
        request,
        query_text=query_text,
        knowledge_file=knowledge_file,
        max_snippets=lexical_limit,
        max_chars_per_snippet=max_chars_per_snippet,
        snippet_max_tokens=snippet_max_tokens,
        tokenizer_model=tokenizer_model,
        tokenizer_fallback_encoding=tokenizer_fallback_encoding,
        allowed_source_prefixes=allowed_source_prefixes,
        lexical_engine=lexical_engine,
        bm25_cache_dir=bm25_cache_dir,
        bm25_use_disk_cache=bm25_use_disk_cache,
        bm25_fallback_to_simple=bm25_fallback_to_simple,
        diagnostics=lexical_diagnostics,
    )
    if lexical_diagnostics.get("errorCode"):
        diagnostics_payload.setdefault("errorCode", lexical_diagnostics["errorCode"])
    rerank_meta = {
        "rerankEngineConfigured": rerank_engine,
        "rerankEngineEffective": "disabled",
        "rerankModel": rerank_model,
        "rerankLatencyMs": 0.0,
        "rerankFallbackReason": None,
        "candidateBeforeRerank": len(lexical_contexts),
        "candidateAfterRerank": min(limit, len(lexical_contexts)),
    }
    rerank_error_code: str | None = None
    final_contexts = lexical_contexts[:limit]
    if rerank_enabled:
        final_contexts, rerank_meta, rerank_error_code = _apply_rerank(
            query_text=query_text,
            contexts=lexical_contexts,
            limit=limit,
            rerank_engine=rerank_engine,
            rerank_model=rerank_model,
            rerank_batch_size=rerank_batch_size,
            rerank_candidate_cap=rerank_candidate_cap,
            rerank_timeout_ms=rerank_timeout_ms,
            rerank_device=rerank_device,
            query_weight=rerank_query_w,
            base_weight=rerank_base_w,
        )
    if rerank_error_code:
        diagnostics_payload.setdefault("errorCode", rerank_error_code)
    diagnostics_payload.update(
        {
            "strategy": "file_lexical",
            "vectorCandidateCount": 0,
            "lexicalCandidateCount": len(lexical_contexts),
            "fusedCandidateCount": len(lexical_contexts),
            "rerankCandidateCount": len(lexical_contexts),
            "finalCount": len(final_contexts),
            "hybridApplied": False,
            "rerankApplied": rerank_enabled,
            "tuning": diagnostics_tuning,
            "lexicalEngineConfigured": lexical_diagnostics.get(
                "lexicalEngineConfigured",
                lexical_engine,
            ),
            "lexicalEngineEffective": lexical_diagnostics.get(
                "lexicalEngineEffective",
                lexical_engine,
            ),
            "lexicalIndexCacheHit": bool(lexical_diagnostics.get("lexicalIndexCacheHit", False)),
            "lexicalIndexBuildMs": float(lexical_diagnostics.get("lexicalIndexBuildMs", 0.0)),
            "lexicalIndexLoadMs": float(lexical_diagnostics.get("lexicalIndexLoadMs", 0.0)),
            "lexicalFallbackReason": lexical_diagnostics.get("lexicalFallbackReason"),
            "lexicalDocCount": int(lexical_diagnostics.get("lexicalDocCount", 0)),
            "lexicalTokenizerProfile": lexical_diagnostics.get(
                "lexicalTokenizerProfile",
                LEXICAL_TOKENIZER_PROFILE,
            ),
            **rerank_meta,
        }
    )
    return final_contexts


def summarize_retrieved_contexts(
    retrieved_contexts: list[RetrievedContext],
) -> list[dict[str, Any]]:
    return [item.to_payload_source() for item in retrieved_contexts]
