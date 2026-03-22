from __future__ import annotations

import re
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

DEFAULT_BGE_MODEL = "BAAI/bge-reranker-v2-m3"
VALID_RERANK_ENGINES = {"bge", "heuristic"}
VALID_RERANK_DEVICES = {"cpu", "cuda"}
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+")
_MODEL_CACHE: dict[tuple[str, str], object] = {}
_MODEL_LOCK = threading.Lock()


def normalize_rerank_engine(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    if value in VALID_RERANK_ENGINES:
        return value
    return "heuristic"


def normalize_rerank_device(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    if value in VALID_RERANK_DEVICES:
        return value
    return "cpu"


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
    for token in _TOKEN_RE.findall((text or "").lower()):
        normalized = token.strip()
        if len(normalized) < 2:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]+", normalized):
            out.add(normalized)
            for idx in range(0, len(normalized) - 1):
                out.add(normalized[idx : idx + 2])
            continue
        out.add(normalized)
    return out


@dataclass(frozen=True)
class RerankCandidate:
    chunk_id: str
    title: str
    content: str
    score: float
    source_url: str = ""


@dataclass(frozen=True)
class RerankRequest:
    query_text: str
    candidates: list[RerankCandidate]
    top_n: int
    configured_engine: str = "bge"
    model_name: str = DEFAULT_BGE_MODEL
    batch_size: int = 16
    candidate_cap: int = 50
    timeout_ms: int = 12000
    device: str = "cpu"
    max_query_chars: int = 512
    max_doc_chars: int = 1200
    query_weight: float = 0.7
    base_weight: float = 0.3


@dataclass(frozen=True)
class RerankResult:
    candidates: list[RerankCandidate]
    configured_engine: str
    effective_engine: str
    model_name: str
    latency_ms: float
    fallback_reason: str | None
    error_code: str | None
    candidate_before: int
    candidate_after: int


class Reranker(Protocol):
    def rerank(self, request: RerankRequest) -> RerankResult:
        ...


class HeuristicFallbackReranker:
    def rerank(self, request: RerankRequest) -> RerankResult:
        started = perf_counter()
        top_n = max(0, int(request.top_n))
        cap = _clamp_int(int(request.candidate_cap), minimum=1, maximum=400)
        pool = list(request.candidates[:cap])
        if top_n == 0 or not pool:
            return RerankResult(
                candidates=[],
                configured_engine=normalize_rerank_engine(request.configured_engine),
                effective_engine="heuristic",
                model_name="heuristic",
                latency_ms=(perf_counter() - started) * 1000.0,
                fallback_reason=None,
                error_code=None,
                candidate_before=len(pool),
                candidate_after=0,
            )

        query_tokens = _tokenize(request.query_text[: max(16, int(request.max_query_chars))])
        q_weight = _clamp_weight(float(request.query_weight))
        b_weight = _clamp_weight(float(request.base_weight))
        if q_weight == 0.0 and b_weight == 0.0:
            q_weight = 0.7
            b_weight = 0.3
        total = q_weight + b_weight
        if total > 0:
            q_weight = q_weight / total
            b_weight = b_weight / total

        max_base = max(1e-6, max((item.score for item in pool), default=1.0))
        rows: list[RerankCandidate] = []
        for item in pool:
            if query_tokens:
                doc_tokens = _tokenize(f"{item.title} {item.content}")
                overlap = len(query_tokens.intersection(doc_tokens)) / float(max(1, len(query_tokens)))
            else:
                overlap = 0.0
            base = item.score / max_base
            score = overlap * q_weight + min(1.0, max(0.0, base)) * b_weight
            rows.append(
                RerankCandidate(
                    chunk_id=item.chunk_id,
                    title=item.title,
                    content=item.content,
                    score=score,
                    source_url=item.source_url,
                )
            )
        rows.sort(key=lambda row: (-row.score, row.chunk_id))
        clipped = rows[:top_n]
        return RerankResult(
            candidates=clipped,
            configured_engine=normalize_rerank_engine(request.configured_engine),
            effective_engine="heuristic",
            model_name="heuristic",
            latency_ms=(perf_counter() - started) * 1000.0,
            fallback_reason=None,
            error_code=None,
            candidate_before=len(pool),
            candidate_after=len(clipped),
        )


class BgeCrossEncoderReranker:
    def _get_or_create_model(self, *, model_name: str, device: str) -> object:
        normalized_device = normalize_rerank_device(device)
        key = (model_name.strip(), normalized_device)
        with _MODEL_LOCK:
            cached = _MODEL_CACHE.get(key)
            if cached is not None:
                return cached

        try:
            import torch  # type: ignore
            from sentence_transformers import CrossEncoder  # type: ignore
        except Exception as err:
            raise RuntimeError("reranker_dependency_missing") from err

        if normalized_device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("reranker_cuda_unavailable")

        model = CrossEncoder(
            model_name,
            device=normalized_device,
            trust_remote_code=False,
        )
        with _MODEL_LOCK:
            _MODEL_CACHE[key] = model
        return model

    def rerank(self, request: RerankRequest) -> RerankResult:
        started = perf_counter()
        top_n = max(0, int(request.top_n))
        cap = _clamp_int(int(request.candidate_cap), minimum=1, maximum=400)
        batch_size = _clamp_int(int(request.batch_size), minimum=1, maximum=128)
        timeout_secs = max(0.1, int(request.timeout_ms) / 1000.0)
        max_query_chars = _clamp_int(int(request.max_query_chars), minimum=64, maximum=2000)
        max_doc_chars = _clamp_int(int(request.max_doc_chars), minimum=120, maximum=6000)
        pool = list(request.candidates[:cap])
        if top_n == 0 or not pool:
            return RerankResult(
                candidates=[],
                configured_engine="bge",
                effective_engine="bge",
                model_name=request.model_name,
                latency_ms=(perf_counter() - started) * 1000.0,
                fallback_reason=None,
                error_code=None,
                candidate_before=len(pool),
                candidate_after=0,
            )

        query_text = request.query_text[:max_query_chars]
        pairs: list[list[str]] = []
        for item in pool:
            doc_text = f"{item.title}\n{item.content}".strip()
            pairs.append([query_text, doc_text[:max_doc_chars]])

        model = self._get_or_create_model(model_name=request.model_name, device=request.device)

        def _predict() -> list[float]:
            values = model.predict(  # type: ignore[attr-defined]
                pairs,
                batch_size=batch_size,
                show_progress_bar=False,
            )
            return [float(value) for value in values]

        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_predict)
                scores = future.result(timeout=timeout_secs)
        except FutureTimeout as err:
            raise RuntimeError("reranker_timeout") from err
        except Exception as err:
            raise RuntimeError("reranker_inference_failed") from err

        rows: list[RerankCandidate] = []
        for item, score in zip(pool, scores):
            rows.append(
                RerankCandidate(
                    chunk_id=item.chunk_id,
                    title=item.title,
                    content=item.content,
                    score=float(score),
                    source_url=item.source_url,
                )
            )
        rows.sort(key=lambda row: (-row.score, row.chunk_id))
        clipped = rows[:top_n]
        return RerankResult(
            candidates=clipped,
            configured_engine="bge",
            effective_engine="bge",
            model_name=request.model_name,
            latency_ms=(perf_counter() - started) * 1000.0,
            fallback_reason=None,
            error_code=None,
            candidate_before=len(pool),
            candidate_after=len(clipped),
        )


def rerank_with_fallback(request: RerankRequest) -> RerankResult:
    configured = normalize_rerank_engine(request.configured_engine)
    normalized_request = RerankRequest(
        query_text=request.query_text,
        candidates=request.candidates,
        top_n=request.top_n,
        configured_engine=configured,
        model_name=request.model_name.strip() or DEFAULT_BGE_MODEL,
        batch_size=request.batch_size,
        candidate_cap=request.candidate_cap,
        timeout_ms=request.timeout_ms,
        device=normalize_rerank_device(request.device),
        max_query_chars=request.max_query_chars,
        max_doc_chars=request.max_doc_chars,
        query_weight=request.query_weight,
        base_weight=request.base_weight,
    )

    if configured == "heuristic":
        return HeuristicFallbackReranker().rerank(normalized_request)

    try:
        return BgeCrossEncoderReranker().rerank(normalized_request)
    except Exception as err:
        fallback = HeuristicFallbackReranker().rerank(normalized_request)
        return RerankResult(
            candidates=fallback.candidates,
            configured_engine=configured,
            effective_engine="heuristic",
            model_name=normalized_request.model_name,
            latency_ms=fallback.latency_ms,
            fallback_reason=str(err),
            error_code="rag_rerank_unavailable",
            candidate_before=fallback.candidate_before,
            candidate_after=fallback.candidate_after,
        )


__all__ = [
    "DEFAULT_BGE_MODEL",
    "RerankCandidate",
    "RerankRequest",
    "RerankResult",
    "VALID_RERANK_DEVICES",
    "VALID_RERANK_ENGINES",
    "normalize_rerank_device",
    "normalize_rerank_engine",
    "rerank_with_fallback",
]
