from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .token_budget import truncate_text_to_tokens


@dataclass(frozen=True)
class KnowledgeRecord:
    chunk_id: str
    title: str
    source_url: str
    content: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class MilvusIndexerConfig:
    input_file: str
    milvus_uri: str
    milvus_collection: str
    openai_api_key: str
    openai_base_url: str = "https://api.openai.com/v1"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_timeout_secs: float = 15.0
    batch_size: int = 16
    milvus_token: str = ""
    milvus_db_name: str = ""
    ensure_collection: bool = False
    metric_type: str = "COSINE"
    vector_field: str = "embedding"
    chunk_id_field: str = "chunk_id"
    title_field: str = "title"
    source_url_field: str = "source_url"
    content_field: str = "content"
    tags_field: str = "tags"
    embed_input_max_tokens: int = 2000
    tokenizer_model: str = "gpt-4.1-mini"
    tokenizer_fallback_encoding: str = "o200k_base"


def _safe_text(value: Any, *, max_len: int = 4000) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text[:max_len]


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def load_knowledge_records(path: str) -> list[KnowledgeRecord]:
    file = Path(path.strip())
    if not file.exists() or not file.is_file():
        return []
    try:
        payload = json.loads(file.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []

    records: list[KnowledgeRecord] = []
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
        if isinstance(raw_tags, list):
            tags = tuple(
                item.strip().lower() for item in raw_tags if isinstance(item, str) and item.strip()
            )
        else:
            tags = tuple()
        records.append(
            KnowledgeRecord(
                chunk_id=chunk_id,
                title=title,
                source_url=source_url,
                content=content,
                tags=tags,
            )
        )
    return records


def _build_embedding_input(
    record: KnowledgeRecord,
    *,
    embed_input_max_tokens: int = 0,
    tokenizer_model: str = "gpt-4.1-mini",
    tokenizer_fallback_encoding: str = "o200k_base",
) -> str:
    tags_text = " ".join(record.tags)
    base = f"{record.title}\n{record.content}\n{tags_text}".strip()
    token_budget = max(0, int(embed_input_max_tokens))
    if token_budget <= 0:
        return base
    return truncate_text_to_tokens(
        tokenizer_model,
        base,
        token_budget,
        fallback_encoding=tokenizer_fallback_encoding,
    ).text


def _iter_batches(items: list[KnowledgeRecord], batch_size: int) -> list[list[KnowledgeRecord]]:
    size = max(1, batch_size)
    out: list[list[KnowledgeRecord]] = []
    for idx in range(0, len(items), size):
        out.append(items[idx : idx + size])
    return out


def _embed_batch_with_openai(
    texts: list[str],
    *,
    cfg: MilvusIndexerConfig,
) -> list[list[float]]:
    if not texts:
        return []
    url = cfg.openai_base_url.rstrip("/") + "/embeddings"
    headers = {
        "Authorization": f"Bearer {cfg.openai_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": cfg.openai_embedding_model,
        "input": [text[:8000] for text in texts],
    }
    with httpx.Client(timeout=max(1.0, cfg.openai_timeout_secs)) as client:
        resp = client.post(url, headers=headers, json=body)
    if resp.status_code // 100 != 2:
        raise RuntimeError(
            f"openai embeddings failed: status={resp.status_code}, body={resp.text[:500]}"
        )
    payload = resp.json()
    items = payload.get("data")
    if not isinstance(items, list):
        raise RuntimeError("openai embeddings failed: invalid response data")

    vectors: list[list[float]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_vec = item.get("embedding")
        if not isinstance(raw_vec, list):
            continue
        vector = [_safe_float(v) for v in raw_vec]
        if not vector:
            continue
        vectors.append(vector)
    return vectors


def _new_milvus_client(cfg: MilvusIndexerConfig):
    try:
        from pymilvus import MilvusClient  # type: ignore
    except Exception as err:  # pragma: no cover
        raise RuntimeError("pymilvus is required for milvus indexing") from err

    return MilvusClient(
        uri=cfg.milvus_uri,
        token=cfg.milvus_token or None,
        db_name=cfg.milvus_db_name or None,
    )


def _ensure_collection_if_needed(client: Any, cfg: MilvusIndexerConfig, vector_dim: int) -> bool:
    if not cfg.ensure_collection:
        return False
    has_collection = client.has_collection(collection_name=cfg.milvus_collection)
    if has_collection:
        return False
    try:
        client.create_collection(
            collection_name=cfg.milvus_collection,
            dimension=vector_dim,
            metric_type=cfg.metric_type,
        )
    except TypeError:
        client.create_collection(
            collection_name=cfg.milvus_collection,
            dimension=vector_dim,
        )
    return True


def _upsert_rows(client: Any, cfg: MilvusIndexerConfig, rows: list[dict[str, Any]]) -> None:
    upsert_fn = getattr(client, "upsert", None)
    if callable(upsert_fn):
        upsert_fn(collection_name=cfg.milvus_collection, data=rows)
        return

    insert_fn = getattr(client, "insert", None)
    if callable(insert_fn):
        insert_fn(collection_name=cfg.milvus_collection, data=rows)
        return
    raise RuntimeError("milvus client has no upsert/insert method")


def import_knowledge_to_milvus(cfg: MilvusIndexerConfig) -> dict[str, Any]:
    if not cfg.input_file.strip():
        raise ValueError("input_file cannot be empty")
    if not cfg.milvus_uri.strip():
        raise ValueError("milvus_uri cannot be empty")
    if not cfg.milvus_collection.strip():
        raise ValueError("milvus_collection cannot be empty")
    if not cfg.openai_api_key.strip():
        raise ValueError("openai_api_key cannot be empty")

    records = load_knowledge_records(cfg.input_file)
    stats = {
        "totalRecords": len(records),
        "indexedRecords": 0,
        "batchCount": 0,
        "embeddingCallCount": 0,
        "collectionCreated": False,
    }
    if not records:
        return stats

    client = _new_milvus_client(cfg)
    collection_checked = False

    for batch in _iter_batches(records, cfg.batch_size):
        texts = [
            _build_embedding_input(
                item,
                embed_input_max_tokens=cfg.embed_input_max_tokens,
                tokenizer_model=cfg.tokenizer_model,
                tokenizer_fallback_encoding=cfg.tokenizer_fallback_encoding,
            )
            for item in batch
        ]
        embeddings = _embed_batch_with_openai(texts, cfg=cfg)
        stats["embeddingCallCount"] += 1
        if len(embeddings) != len(batch):
            raise RuntimeError(
                f"embedding size mismatch: expected={len(batch)}, got={len(embeddings)}"
            )

        if not collection_checked:
            stats["collectionCreated"] = _ensure_collection_if_needed(
                client,
                cfg,
                len(embeddings[0]),
            )
            collection_checked = True

        rows: list[dict[str, Any]] = []
        for item, vector in zip(batch, embeddings):
            rows.append(
                {
                    cfg.chunk_id_field: item.chunk_id,
                    cfg.title_field: item.title,
                    cfg.source_url_field: item.source_url,
                    cfg.content_field: item.content,
                    cfg.tags_field: list(item.tags),
                    cfg.vector_field: vector,
                }
            )

        _upsert_rows(client, cfg, rows)
        stats["batchCount"] += 1
        stats["indexedRecords"] += len(rows)

    return stats
