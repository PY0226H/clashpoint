from __future__ import annotations

from dataclasses import dataclass

DEFAULT_RETRIEVAL_PROFILE = "hybrid_v1"


@dataclass(frozen=True)
class RetrievalProfile:
    name: str
    hybrid_enabled: bool
    rerank_enabled: bool
    hybrid_rrf_k: int
    hybrid_vector_limit_multiplier: int
    hybrid_lexical_limit_multiplier: int
    rerank_query_weight: float
    rerank_base_weight: float


_PROFILE_PRESETS: dict[str, RetrievalProfile] = {
    "hybrid_v1": RetrievalProfile(
        name="hybrid_v1",
        hybrid_enabled=True,
        rerank_enabled=True,
        hybrid_rrf_k=60,
        hybrid_vector_limit_multiplier=1,
        hybrid_lexical_limit_multiplier=2,
        rerank_query_weight=0.7,
        rerank_base_weight=0.3,
    ),
    "hybrid_recall_v1": RetrievalProfile(
        name="hybrid_recall_v1",
        hybrid_enabled=True,
        rerank_enabled=False,
        hybrid_rrf_k=90,
        hybrid_vector_limit_multiplier=2,
        hybrid_lexical_limit_multiplier=3,
        rerank_query_weight=0.65,
        rerank_base_weight=0.35,
    ),
    "hybrid_precision_v1": RetrievalProfile(
        name="hybrid_precision_v1",
        hybrid_enabled=True,
        rerank_enabled=True,
        hybrid_rrf_k=40,
        hybrid_vector_limit_multiplier=1,
        hybrid_lexical_limit_multiplier=2,
        rerank_query_weight=0.82,
        rerank_base_weight=0.18,
    ),
    "lexical_fast_v1": RetrievalProfile(
        name="lexical_fast_v1",
        hybrid_enabled=False,
        rerank_enabled=False,
        hybrid_rrf_k=60,
        hybrid_vector_limit_multiplier=1,
        hybrid_lexical_limit_multiplier=1,
        rerank_query_weight=0.7,
        rerank_base_weight=0.3,
    ),
}

_PROFILE_ALIASES = {
    "hybrid_default": "hybrid_v1",
    "hybrid_recall": "hybrid_recall_v1",
    "hybrid_precision": "hybrid_precision_v1",
    "lexical_fast": "lexical_fast_v1",
}


def resolve_retrieval_profile(raw: str | None) -> tuple[RetrievalProfile, str | None]:
    value = (raw or "").strip().lower()
    if not value:
        return _PROFILE_PRESETS[DEFAULT_RETRIEVAL_PROFILE], None

    name = _PROFILE_ALIASES.get(value, value)
    profile = _PROFILE_PRESETS.get(name)
    if profile is not None:
        return profile, None
    return _PROFILE_PRESETS[DEFAULT_RETRIEVAL_PROFILE], "unknown_profile"
