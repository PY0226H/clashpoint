from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .rag_profiles import DEFAULT_RETRIEVAL_PROFILE, resolve_retrieval_profile
from .rag_retriever import RetrievedContext, retrieve_contexts

RetrieveContextsFn = Callable[..., list[RetrievedContext]]


@dataclass(frozen=True)
class RagEvalCase:
    case_id: str
    request: Any
    expected_chunk_ids: tuple[str, ...]


@dataclass(frozen=True)
class RagEvalProfile:
    requested_name: str
    resolved_name: str
    fallback_reason: str | None
    retrieve_overrides: dict[str, Any]


@dataclass(frozen=True)
class RagEvalCaseResult:
    case_id: str
    expected_chunk_ids: tuple[str, ...]
    actual_chunk_ids: tuple[str, ...]
    hit_chunk_ids: tuple[str, ...]
    recall: float
    reciprocal_rank: float
    full_coverage: bool


@dataclass(frozen=True)
class RagEvalSummary:
    requested_profile: str
    resolved_profile: str
    profile_fallback_reason: str | None
    case_count: int
    avg_recall: float
    mrr: float
    hit_case_rate: float
    full_coverage_rate: float
    avg_hit_count: float
    cases: tuple[RagEvalCaseResult, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "requestedProfile": self.requested_profile,
            "resolvedProfile": self.resolved_profile,
            "profileFallbackReason": self.profile_fallback_reason,
            "caseCount": self.case_count,
            "avgRecall": round(self.avg_recall, 4),
            "mrr": round(self.mrr, 4),
            "hitCaseRate": round(self.hit_case_rate, 4),
            "fullCoverageRate": round(self.full_coverage_rate, 4),
            "avgHitCount": round(self.avg_hit_count, 4),
            "cases": [
                {
                    "caseId": row.case_id,
                    "expectedChunkIds": list(row.expected_chunk_ids),
                    "actualChunkIds": list(row.actual_chunk_ids),
                    "hitChunkIds": list(row.hit_chunk_ids),
                    "recall": round(row.recall, 4),
                    "reciprocalRank": round(row.reciprocal_rank, 4),
                    "fullCoverage": row.full_coverage,
                }
                for row in self.cases
            ],
        }


def build_eval_profile(name: str | None) -> RagEvalProfile:
    requested = (name or DEFAULT_RETRIEVAL_PROFILE).strip() or DEFAULT_RETRIEVAL_PROFILE
    resolved, fallback_reason = resolve_retrieval_profile(requested)
    overrides = {
        "hybrid_enabled": resolved.hybrid_enabled,
        "rerank_enabled": resolved.rerank_enabled,
        "hybrid_rrf_k": resolved.hybrid_rrf_k,
        "hybrid_vector_limit_multiplier": resolved.hybrid_vector_limit_multiplier,
        "hybrid_lexical_limit_multiplier": resolved.hybrid_lexical_limit_multiplier,
        "rerank_query_weight": resolved.rerank_query_weight,
        "rerank_base_weight": resolved.rerank_base_weight,
    }
    return RagEvalProfile(
        requested_name=requested,
        resolved_name=resolved.name,
        fallback_reason=fallback_reason,
        retrieve_overrides=overrides,
    )


def evaluate_rag_profile(
    *,
    cases: list[RagEvalCase],
    profile_name: str,
    base_retrieve_kwargs: dict[str, Any],
    retrieve_contexts_fn: RetrieveContextsFn = retrieve_contexts,
) -> RagEvalSummary:
    profile = build_eval_profile(profile_name)
    case_results: list[RagEvalCaseResult] = []
    recall_total = 0.0
    reciprocal_rank_total = 0.0
    hit_case_total = 0
    full_coverage_total = 0
    hit_count_total = 0

    for case in cases:
        expected = _normalize_chunk_ids(case.expected_chunk_ids)
        kwargs = dict(base_retrieve_kwargs)
        kwargs.update(profile.retrieve_overrides)
        contexts = retrieve_contexts_fn(case.request, **kwargs)
        actual = _normalize_chunk_ids([item.chunk_id for item in contexts])
        hits = tuple(chunk_id for chunk_id in actual if chunk_id in expected)
        expected_size = len(expected)
        recall = (len(hits) / expected_size) if expected_size > 0 else 1.0
        first_hit_rank = None
        for idx, chunk_id in enumerate(actual):
            if chunk_id in expected:
                first_hit_rank = idx + 1
                break
        reciprocal_rank = 1.0 / first_hit_rank if first_hit_rank else 0.0
        full_coverage = expected_size == 0 or len(hits) == expected_size

        case_results.append(
            RagEvalCaseResult(
                case_id=case.case_id,
                expected_chunk_ids=expected,
                actual_chunk_ids=actual,
                hit_chunk_ids=hits,
                recall=recall,
                reciprocal_rank=reciprocal_rank,
                full_coverage=full_coverage,
            )
        )

        recall_total += recall
        reciprocal_rank_total += reciprocal_rank
        hit_count_total += len(hits)
        if hits:
            hit_case_total += 1
        if full_coverage:
            full_coverage_total += 1

    case_count = len(cases)
    if case_count == 0:
        return RagEvalSummary(
            requested_profile=profile.requested_name,
            resolved_profile=profile.resolved_name,
            profile_fallback_reason=profile.fallback_reason,
            case_count=0,
            avg_recall=0.0,
            mrr=0.0,
            hit_case_rate=0.0,
            full_coverage_rate=0.0,
            avg_hit_count=0.0,
            cases=tuple(),
        )

    return RagEvalSummary(
        requested_profile=profile.requested_name,
        resolved_profile=profile.resolved_name,
        profile_fallback_reason=profile.fallback_reason,
        case_count=case_count,
        avg_recall=recall_total / case_count,
        mrr=reciprocal_rank_total / case_count,
        hit_case_rate=hit_case_total / case_count,
        full_coverage_rate=full_coverage_total / case_count,
        avg_hit_count=hit_count_total / case_count,
        cases=tuple(case_results),
    )


def compare_rag_profiles(
    *,
    cases: list[RagEvalCase],
    profile_names: list[str],
    base_retrieve_kwargs: dict[str, Any],
    retrieve_contexts_fn: RetrieveContextsFn = retrieve_contexts,
) -> dict[str, Any]:
    summaries = [
        evaluate_rag_profile(
            cases=cases,
            profile_name=name,
            base_retrieve_kwargs=base_retrieve_kwargs,
            retrieve_contexts_fn=retrieve_contexts_fn,
        )
        for name in profile_names
    ]
    ranked = sorted(
        summaries,
        key=lambda item: (
            item.mrr,
            item.avg_recall,
            item.full_coverage_rate,
            item.hit_case_rate,
        ),
        reverse=True,
    )
    recommended = ranked[0] if ranked else None
    return {
        "recommendedProfile": recommended.resolved_profile if recommended else None,
        "ranked": [item.to_payload() for item in ranked],
    }


def _normalize_chunk_ids(ids: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in ids:
        chunk_id = str(raw or "").strip()
        if not chunk_id or chunk_id in seen:
            continue
        seen.add(chunk_id)
        out.append(chunk_id)
    return tuple(out)
