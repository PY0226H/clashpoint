from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable

CallbackReportFn = Callable[[int, dict[str, Any]], Awaitable[None]]
SleepFn = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class DispatchRuntimeConfig:
    process_delay_ms: int
    judge_style_mode: str
    runtime_retry_max_attempts: int = 2
    retry_backoff_ms: int = 200
    compliance_block_enabled: bool = True


@dataclass(frozen=True)
class RagTopicContext:
    title: str
    category: str
    description: str
    stance_pro: str
    stance_con: str
    context_seed: str | None = None


@dataclass(frozen=True)
class RagMessageContext:
    message_id: int
    side: str
    content: str
    created_at: datetime | None = None
    speaker_tag: str | None = None
    user_id: int | None = None


@dataclass(frozen=True)
class RuntimeRagRequest:
    topic: RagTopicContext
    messages: list[RagMessageContext]
    retrieval_profile: str = "hybrid_v1"
