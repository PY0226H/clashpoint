from __future__ import annotations

import math
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

DEFAULT_FALLBACK_ENCODING = "o200k_base"
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]")


@dataclass(frozen=True)
class EncodingResolution:
    encoding_name: str
    estimated: bool


@dataclass(frozen=True)
class TruncateResult:
    text: str
    original_tokens: int
    final_tokens: int
    clipped: bool
    encoding_name: str
    estimated: bool


@dataclass(frozen=True)
class TokenSegment:
    segment_id: str
    text: str
    priority: int = 100
    required: bool = False


@dataclass(frozen=True)
class PackedSegment:
    segment_id: str
    text: str
    original_tokens: int
    final_tokens: int
    included: bool
    clipped: bool
    required: bool
    priority: int
    reason: str | None = None


@dataclass(frozen=True)
class PackedSegmentsResult:
    segments: list[PackedSegment]
    total_tokens: int
    budget_tokens: int
    clipped: bool
    strategy: str
    encoding_name: str
    estimated: bool

    def segment_map(self) -> dict[str, str]:
        return {
            row.segment_id: row.text
            for row in self.segments
            if row.included and row.text
        }

    def clip_summary(self) -> dict[str, object]:
        included_ids: list[str] = []
        omitted_ids: list[str] = []
        clipped_ids: list[str] = []
        for row in self.segments:
            if row.included:
                included_ids.append(row.segment_id)
            else:
                omitted_ids.append(row.segment_id)
            if row.clipped:
                clipped_ids.append(row.segment_id)
        return {
            "strategy": self.strategy,
            "encoding": self.encoding_name,
            "estimated": self.estimated,
            "budgetTokens": self.budget_tokens,
            "totalTokens": self.total_tokens,
            "clipped": self.clipped,
            "includedSegmentIds": included_ids,
            "omittedSegmentIds": omitted_ids,
            "clippedSegmentIds": clipped_ids,
        }


def _safe_text(value: str | None) -> str:
    return str(value or "")


@lru_cache(maxsize=64)
def _resolve_tiktoken_encoding(model: str, fallback_encoding: str):
    try:
        import tiktoken  # type: ignore
    except Exception:
        return None
    model_name = str(model or "").strip()
    fallback_name = str(fallback_encoding or DEFAULT_FALLBACK_ENCODING).strip() or DEFAULT_FALLBACK_ENCODING
    if model_name:
        try:
            return tiktoken.encoding_for_model(model_name)
        except Exception:
            pass
    try:
        return tiktoken.get_encoding(fallback_name)
    except Exception:
        return None


def resolve_encoding(model: str, fallback_encoding: str = DEFAULT_FALLBACK_ENCODING) -> EncodingResolution:
    encoding = _resolve_tiktoken_encoding(model, fallback_encoding)
    if encoding is None:
        return EncodingResolution(
            encoding_name=str(fallback_encoding or DEFAULT_FALLBACK_ENCODING),
            estimated=True,
        )
    return EncodingResolution(
        encoding_name=str(getattr(encoding, "name", fallback_encoding) or fallback_encoding),
        estimated=False,
    )


def _fallback_count_tokens(text: str) -> int:
    units = 0
    for token in _TOKEN_RE.findall((text or "").lower()):
        token = token.strip()
        if not token:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]", token):
            units += 1
            continue
        units += max(1, int(math.ceil(len(token) / 4.0)))
    if units == 0 and text.strip():
        return 1
    return units


def count_tokens(model: str, text: str, fallback_encoding: str = DEFAULT_FALLBACK_ENCODING) -> int:
    normalized = _safe_text(text)
    encoding = _resolve_tiktoken_encoding(model, fallback_encoding)
    if encoding is None:
        return _fallback_count_tokens(normalized)
    try:
        return len(encoding.encode(normalized))
    except Exception:
        return _fallback_count_tokens(normalized)


def _fallback_truncate_to_tokens(text: str, max_tokens: int) -> str:
    if max_tokens <= 0:
        return ""
    if _fallback_count_tokens(text) <= max_tokens:
        return text
    low = 0
    high = len(text)
    best = ""
    while low <= high:
        mid = (low + high) // 2
        candidate = text[:mid]
        token_count = _fallback_count_tokens(candidate)
        if token_count <= max_tokens:
            best = candidate
            low = mid + 1
        else:
            high = mid - 1
    return best


def truncate_text_to_tokens(
    model: str,
    text: str,
    max_tokens: int,
    fallback_encoding: str = DEFAULT_FALLBACK_ENCODING,
) -> TruncateResult:
    normalized = _safe_text(text)
    budget = max(0, int(max_tokens))
    original_tokens = count_tokens(model, normalized, fallback_encoding=fallback_encoding)
    resolution = resolve_encoding(model, fallback_encoding=fallback_encoding)
    if budget <= 0 or not normalized:
        return TruncateResult(
            text="",
            original_tokens=original_tokens,
            final_tokens=0,
            clipped=bool(normalized),
            encoding_name=resolution.encoding_name,
            estimated=resolution.estimated,
        )
    if original_tokens <= budget:
        return TruncateResult(
            text=normalized,
            original_tokens=original_tokens,
            final_tokens=original_tokens,
            clipped=False,
            encoding_name=resolution.encoding_name,
            estimated=resolution.estimated,
        )

    encoding = _resolve_tiktoken_encoding(model, fallback_encoding)
    if encoding is not None:
        try:
            encoded = encoding.encode(normalized)
            decoded = encoding.decode(encoded[:budget])
            final_tokens = count_tokens(model, decoded, fallback_encoding=fallback_encoding)
            return TruncateResult(
                text=decoded,
                original_tokens=original_tokens,
                final_tokens=final_tokens,
                clipped=True,
                encoding_name=resolution.encoding_name,
                estimated=resolution.estimated,
            )
        except Exception:
            pass

    fallback_text = _fallback_truncate_to_tokens(normalized, budget)
    final_tokens = _fallback_count_tokens(fallback_text)
    return TruncateResult(
        text=fallback_text,
        original_tokens=original_tokens,
        final_tokens=final_tokens,
        clipped=fallback_text != normalized,
        encoding_name=resolution.encoding_name,
        estimated=True,
    )


def pack_segments_with_budget(
    model: str,
    segments: Iterable[TokenSegment],
    budget: int,
    strategy: str = "priority",
    fallback_encoding: str = DEFAULT_FALLBACK_ENCODING,
) -> PackedSegmentsResult:
    budget_tokens = max(0, int(budget))
    rows = list(segments)
    indexed = list(enumerate(rows))
    ranked = sorted(indexed, key=lambda pair: (pair[1].priority, pair[0]))

    packed: list[PackedSegment] = []
    consumed = 0
    clipped_any = False
    resolution = resolve_encoding(model, fallback_encoding=fallback_encoding)

    for _, row in ranked:
        text = _safe_text(row.text)
        original_tokens = count_tokens(model, text, fallback_encoding=fallback_encoding)
        remaining = max(0, budget_tokens - consumed)
        if not text:
            packed.append(
                PackedSegment(
                    segment_id=row.segment_id,
                    text="",
                    original_tokens=0,
                    final_tokens=0,
                    included=False,
                    clipped=False,
                    required=row.required,
                    priority=row.priority,
                    reason="empty",
                )
            )
            continue

        if remaining <= 0:
            packed.append(
                PackedSegment(
                    segment_id=row.segment_id,
                    text="",
                    original_tokens=original_tokens,
                    final_tokens=0,
                    included=False,
                    clipped=False,
                    required=row.required,
                    priority=row.priority,
                    reason="budget_exhausted",
                )
            )
            continue

        truncated = truncate_text_to_tokens(
            model,
            text,
            remaining,
            fallback_encoding=fallback_encoding,
        )
        if truncated.final_tokens <= 0 or not truncated.text:
            packed.append(
                PackedSegment(
                    segment_id=row.segment_id,
                    text="",
                    original_tokens=original_tokens,
                    final_tokens=0,
                    included=False,
                    clipped=False,
                    required=row.required,
                    priority=row.priority,
                    reason="budget_exhausted",
                )
            )
            continue

        consumed += truncated.final_tokens
        clipped_any = clipped_any or truncated.clipped
        packed.append(
            PackedSegment(
                segment_id=row.segment_id,
                text=truncated.text,
                original_tokens=original_tokens,
                final_tokens=truncated.final_tokens,
                included=True,
                clipped=truncated.clipped,
                required=row.required,
                priority=row.priority,
                reason=None if not truncated.clipped else "truncated_to_budget",
            )
        )

    index_map = {seg.segment_id: idx for idx, seg in indexed}
    packed.sort(key=lambda row: index_map.get(row.segment_id, 10**9))
    return PackedSegmentsResult(
        segments=packed,
        total_tokens=consumed,
        budget_tokens=budget_tokens,
        clipped=clipped_any or any(not row.included for row in packed if row.original_tokens > 0),
        strategy=strategy,
        encoding_name=resolution.encoding_name,
        estimated=resolution.estimated,
    )
