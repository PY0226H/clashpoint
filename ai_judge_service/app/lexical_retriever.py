from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol

DEFAULT_LEXICAL_ENGINE = "bm25"
VALID_LEXICAL_ENGINES = {"bm25"}
DEFAULT_BM25_CACHE_DIR = str(Path(__file__).resolve().parent.parent / ".cache" / "bm25")
LEXICAL_TOKENIZER_PROFILE = "echoisle_zh_en_v1"
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+")
_INDEX_CACHE_VERSION = "v1"
_INDEX_CACHE: dict[tuple[str, str], "_Bm25IndexBundle"] = {}
_INDEX_LOCK = threading.Lock()


def normalize_lexical_engine(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    if value in VALID_LEXICAL_ENGINES:
        return value
    return DEFAULT_LEXICAL_ENGINE


@dataclass(frozen=True)
class LexicalDocument:
    chunk_id: str
    title: str
    source_url: str
    content: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class LexicalHit:
    chunk_id: str
    score: float


@dataclass(frozen=True)
class LexicalSearchRequest:
    knowledge_file: str
    documents: list[LexicalDocument]
    query_text: str
    top_k: int
    configured_engine: str = DEFAULT_LEXICAL_ENGINE
    bm25_cache_dir: str = DEFAULT_BM25_CACHE_DIR
    bm25_use_disk_cache: bool = True
    fallback_to_simple: bool = True


@dataclass(frozen=True)
class LexicalSearchResult:
    hits: list[LexicalHit]
    configured_engine: str
    effective_engine: str
    index_cache_hit: bool
    index_build_ms: float
    index_load_ms: float
    fallback_reason: str | None
    error_code: str | None
    doc_count: int
    tokenizer_profile: str


class LexicalRetriever(Protocol):
    def search(self, request: LexicalSearchRequest) -> LexicalSearchResult: ...


@dataclass(frozen=True)
class _Bm25IndexBundle:
    retriever: Any
    chunk_ids: tuple[str, ...]


def _tokenize_terms(text: str) -> list[str]:
    terms: list[str] = []
    for token in _TOKEN_RE.findall((text or "").lower()):
        normalized = token.strip()
        if len(normalized) < 2:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]+", normalized):
            terms.append(normalized)
            for idx in range(0, len(normalized) - 1):
                terms.append(normalized[idx : idx + 2])
            continue
        terms.append(normalized)
    return terms


def _build_document_terms(document: LexicalDocument) -> list[str]:
    weighted_parts = [
        document.title,
        document.title,
        " ".join(document.tags),
        " ".join(document.tags),
        document.content,
    ]
    terms: list[str] = []
    for part in weighted_parts:
        terms.extend(_tokenize_terms(part))
    return terms


def _chunk_ids(documents: list[LexicalDocument]) -> tuple[str, ...]:
    return tuple(document.chunk_id for document in documents)


def _signature_for_request(request: LexicalSearchRequest) -> str:
    file_path = Path(request.knowledge_file.strip()) if request.knowledge_file.strip() else None
    if file_path is not None and file_path.exists() and file_path.is_file():
        stat = file_path.stat()
        raw = (
            f"{file_path.resolve()}|{stat.st_mtime_ns}|{stat.st_size}|"
            f"{LEXICAL_TOKENIZER_PROFILE}|{_INDEX_CACHE_VERSION}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    payload = {
        "documents": [
            {
                "chunk_id": document.chunk_id,
                "title": document.title,
                "source_url": document.source_url,
                "content": document.content,
                "tags": list(document.tags),
            }
            for document in request.documents
        ],
        "tokenizer_profile": LEXICAL_TOKENIZER_PROFILE,
        "cache_version": _INDEX_CACHE_VERSION,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _load_meta(meta_file: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(meta_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


class SimpleFallbackLexicalRetriever:
    def search(self, request: LexicalSearchRequest) -> LexicalSearchResult:
        query_terms = set(_tokenize_terms(request.query_text))
        rows: list[LexicalHit] = []
        for document in request.documents:
            if not query_terms:
                score = 0.0
            else:
                doc_terms = set(_build_document_terms(document))
                overlap = len(query_terms.intersection(doc_terms))
                if overlap == 0:
                    continue
                coverage = overlap / max(1, len(query_terms))
                density = overlap / max(1, len(doc_terms))
                score = coverage * 0.75 + density * 0.25
            rows.append(LexicalHit(chunk_id=document.chunk_id, score=float(score)))
        rows.sort(key=lambda row: (-row.score, row.chunk_id))
        clipped = rows[: max(0, int(request.top_k))]
        return LexicalSearchResult(
            hits=clipped,
            configured_engine=normalize_lexical_engine(request.configured_engine),
            effective_engine="simple",
            index_cache_hit=False,
            index_build_ms=0.0,
            index_load_ms=0.0,
            fallback_reason=None,
            error_code=None,
            doc_count=len(request.documents),
            tokenizer_profile=LEXICAL_TOKENIZER_PROFILE,
        )


class ExternalLexicalRetriever:
    def search(self, request: LexicalSearchRequest) -> LexicalSearchResult:
        raise RuntimeError("external_lexical_backend_not_implemented")


class Bm25sLexicalRetriever:
    def _load_from_disk(
        self,
        *,
        save_dir: Path,
        expected_chunk_ids: tuple[str, ...],
    ) -> tuple[_Bm25IndexBundle | None, float]:
        started = perf_counter()
        meta = _load_meta(save_dir / "echoisle.meta.json")
        if meta is None:
            return None, 0.0
        if meta.get("tokenizerProfile") != LEXICAL_TOKENIZER_PROFILE:
            return None, 0.0
        if tuple(meta.get("chunkIds") or ()) != expected_chunk_ids:
            return None, 0.0
        try:
            import bm25s

            retriever = bm25s.BM25.load(save_dir, load_corpus=False, mmap=False)
        except Exception:
            return None, 0.0
        return (
            _Bm25IndexBundle(retriever=retriever, chunk_ids=expected_chunk_ids),
            (perf_counter() - started) * 1000.0,
        )

    def _save_to_disk(
        self,
        *,
        save_dir: Path,
        retriever: Any,
        chunk_ids: tuple[str, ...],
    ) -> None:
        save_dir.mkdir(parents=True, exist_ok=True)
        retriever.save(save_dir)
        meta = {
            "tokenizerProfile": LEXICAL_TOKENIZER_PROFILE,
            "chunkIds": list(chunk_ids),
            "cacheVersion": _INDEX_CACHE_VERSION,
        }
        (save_dir / "echoisle.meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _build_index(self, request: LexicalSearchRequest) -> tuple[_Bm25IndexBundle, float]:
        started = perf_counter()
        try:
            import bm25s
        except Exception as err:
            raise RuntimeError("bm25_dependency_missing") from err

        tokenized_documents = [_build_document_terms(document) for document in request.documents]
        retriever = bm25s.BM25(method="lucene")
        retriever.index(tokenized_documents, show_progress=False)
        return (
            _Bm25IndexBundle(retriever=retriever, chunk_ids=_chunk_ids(request.documents)),
            (perf_counter() - started) * 1000.0,
        )

    def _resolve_index(
        self, request: LexicalSearchRequest
    ) -> tuple[_Bm25IndexBundle, bool, float, float]:
        signature = _signature_for_request(request)
        cache_key = (signature, LEXICAL_TOKENIZER_PROFILE)
        with _INDEX_LOCK:
            cached = _INDEX_CACHE.get(cache_key)
        if cached is not None and cached.chunk_ids == _chunk_ids(request.documents):
            return cached, True, 0.0, 0.0

        load_ms = 0.0
        if request.bm25_use_disk_cache and request.documents:
            save_dir = Path(request.bm25_cache_dir).expanduser() / signature
            loaded, load_ms = self._load_from_disk(
                save_dir=save_dir,
                expected_chunk_ids=_chunk_ids(request.documents),
            )
            if loaded is not None:
                with _INDEX_LOCK:
                    _INDEX_CACHE[cache_key] = loaded
                return loaded, True, 0.0, load_ms

        bundle, build_ms = self._build_index(request)
        with _INDEX_LOCK:
            _INDEX_CACHE[cache_key] = bundle
        if request.bm25_use_disk_cache and request.documents:
            save_dir = Path(request.bm25_cache_dir).expanduser() / signature
            self._save_to_disk(
                save_dir=save_dir,
                retriever=bundle.retriever,
                chunk_ids=bundle.chunk_ids,
            )
        return bundle, False, build_ms, load_ms

    def search(self, request: LexicalSearchRequest) -> LexicalSearchResult:
        top_k = min(max(0, int(request.top_k)), len(request.documents))
        if top_k == 0 or not request.documents:
            return LexicalSearchResult(
                hits=[],
                configured_engine=normalize_lexical_engine(request.configured_engine),
                effective_engine="bm25",
                index_cache_hit=False,
                index_build_ms=0.0,
                index_load_ms=0.0,
                fallback_reason=None,
                error_code=None,
                doc_count=len(request.documents),
                tokenizer_profile=LEXICAL_TOKENIZER_PROFILE,
            )

        bundle, cache_hit, build_ms, load_ms = self._resolve_index(request)
        query_terms = [_tokenize_terms(request.query_text)]
        results, scores = bundle.retriever.retrieve(
            query_terms,
            k=top_k,
            show_progress=False,
        )
        rows: list[LexicalHit] = []
        doc_ids = results.tolist()[0] if len(results) else []
        doc_scores = scores.tolist()[0] if len(scores) else []
        for doc_id, score in zip(doc_ids, doc_scores):
            try:
                index = int(doc_id)
            except Exception:
                continue
            if index < 0 or index >= len(bundle.chunk_ids):
                continue
            rows.append(
                LexicalHit(
                    chunk_id=bundle.chunk_ids[index],
                    score=float(score),
                )
            )
        rows.sort(key=lambda row: (-row.score, row.chunk_id))
        return LexicalSearchResult(
            hits=rows,
            configured_engine=normalize_lexical_engine(request.configured_engine),
            effective_engine="bm25",
            index_cache_hit=cache_hit,
            index_build_ms=round(float(build_ms), 2),
            index_load_ms=round(float(load_ms), 2),
            fallback_reason=None,
            error_code=None,
            doc_count=len(request.documents),
            tokenizer_profile=LEXICAL_TOKENIZER_PROFILE,
        )


def search_lexical(request: LexicalSearchRequest) -> LexicalSearchResult:
    configured_engine = normalize_lexical_engine(request.configured_engine)
    normalized_request = LexicalSearchRequest(
        knowledge_file=request.knowledge_file,
        documents=request.documents,
        query_text=request.query_text,
        top_k=max(0, int(request.top_k)),
        configured_engine=configured_engine,
        bm25_cache_dir=request.bm25_cache_dir.strip() or DEFAULT_BM25_CACHE_DIR,
        bm25_use_disk_cache=bool(request.bm25_use_disk_cache),
        fallback_to_simple=bool(request.fallback_to_simple),
    )
    try:
        return Bm25sLexicalRetriever().search(normalized_request)
    except Exception as err:
        if not normalized_request.fallback_to_simple:
            return LexicalSearchResult(
                hits=[],
                configured_engine=configured_engine,
                effective_engine="bm25_failed",
                index_cache_hit=False,
                index_build_ms=0.0,
                index_load_ms=0.0,
                fallback_reason=str(err),
                error_code="rag_lexical_unavailable",
                doc_count=len(normalized_request.documents),
                tokenizer_profile=LEXICAL_TOKENIZER_PROFILE,
            )
        fallback = SimpleFallbackLexicalRetriever().search(normalized_request)
        return LexicalSearchResult(
            hits=fallback.hits,
            configured_engine=configured_engine,
            effective_engine="simple",
            index_cache_hit=False,
            index_build_ms=0.0,
            index_load_ms=0.0,
            fallback_reason=str(err),
            error_code="rag_lexical_unavailable",
            doc_count=len(normalized_request.documents),
            tokenizer_profile=LEXICAL_TOKENIZER_PROFILE,
        )


__all__ = [
    "Bm25sLexicalRetriever",
    "DEFAULT_BM25_CACHE_DIR",
    "DEFAULT_LEXICAL_ENGINE",
    "ExternalLexicalRetriever",
    "LEXICAL_TOKENIZER_PROFILE",
    "LexicalDocument",
    "LexicalHit",
    "LexicalRetriever",
    "LexicalSearchRequest",
    "LexicalSearchResult",
    "SimpleFallbackLexicalRetriever",
    "VALID_LEXICAL_ENGINES",
    "normalize_lexical_engine",
    "search_lexical",
]
