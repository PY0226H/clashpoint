from __future__ import annotations

from dataclasses import dataclass

ERROR_JUDGE_TIMEOUT = "judge_timeout"
ERROR_RAG_UNAVAILABLE = "rag_unavailable"
ERROR_MODEL_OVERLOAD = "model_overload"
ERROR_CONSISTENCY_CONFLICT = "consistency_conflict"

VALID_RUNTIME_ERROR_CODES = {
    ERROR_JUDGE_TIMEOUT,
    ERROR_RAG_UNAVAILABLE,
    ERROR_MODEL_OVERLOAD,
    ERROR_CONSISTENCY_CONFLICT,
}


def normalize_runtime_error_code(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    if value in VALID_RUNTIME_ERROR_CODES:
        return value
    return ERROR_MODEL_OVERLOAD


def classify_openai_failure(reason: str | None) -> str:
    text = str(reason or "").strip().lower()
    if not text:
        return ERROR_MODEL_OVERLOAD
    if "timeout" in text or "timed out" in text:
        return ERROR_JUDGE_TIMEOUT
    if "status=408" in text or "status=504" in text:
        return ERROR_JUDGE_TIMEOUT
    if "status=429" in text or "rate limit" in text:
        return ERROR_MODEL_OVERLOAD
    if "status=500" in text or "status=502" in text or "status=503" in text:
        return ERROR_MODEL_OVERLOAD
    if "overload" in text or "capacity" in text:
        return ERROR_MODEL_OVERLOAD
    return ERROR_MODEL_OVERLOAD


def classify_rag_failure(reason: str | None) -> str:
    text = str(reason or "").strip().lower()
    if not text:
        return ERROR_RAG_UNAVAILABLE
    if "timeout" in text or "timed out" in text:
        return ERROR_JUDGE_TIMEOUT
    if "status=408" in text or "status=504" in text:
        return ERROR_JUDGE_TIMEOUT
    if "unavailable" in text or "connection" in text:
        return ERROR_RAG_UNAVAILABLE
    if "milvus" in text or "redis" in text:
        return ERROR_RAG_UNAVAILABLE
    return ERROR_RAG_UNAVAILABLE


@dataclass(frozen=True)
class JudgeRuntimeError(RuntimeError):
    code: str
    message: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", normalize_runtime_error_code(self.code))
        RuntimeError.__init__(self, self.message)


def extract_runtime_error_code(err: Exception) -> str:
    if isinstance(err, JudgeRuntimeError):
        return err.code
    return classify_openai_failure(str(err))
